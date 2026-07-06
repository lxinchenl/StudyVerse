from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.agents.chat_stream import pack_main_agent_context
from app.agents.orchestrator import AgentOrchestrator
from app.core.config import get_settings
from app.core.http_utils import inline_content_disposition
from app.infrastructure.kg_rag import get_chroma_store, get_neo4j_store
from app.api.deps import require_user_id
from app.core.dependencies import (
    get_course_service,
    get_graph_repo,
    get_graph_service,
    get_llm_config_service,
    get_llm_provider,
    get_memory_service,
    get_code_lab_service,
    get_orchestrator,
    get_path_service,
    get_practice_service,
    get_question_repo,
    get_resource_service,
    get_resource_studio,
    get_auth_service,
    reload_llm_dependencies,
)
from app.domain.schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessageOut,
    CourseOut,
    ChapterOut,
    DocumentOut,
    DocumentProgressOut,
    DocumentProgressUpdateRequest,
    ExerciseOut,
    ExerciseSubmitRequest,
    ExerciseSubmitResponse,
    CodeLabRunRequest,
    CodeLabRunResponse,
    CodeLabSetOut,
    CodeLabSubmitRequest,
    CodeLabSubmitResponse,
    KnowledgeGraphOut,
    LearningPathStepOut,
    LearningCourseSummaryOut,
    LearningCourseDetailOut,
    ResourceGenerateRequest,
    ResourceOut,
    UserOut,
    UserLoginRequest,
    UserRegisterRequest,
    UserUploadOut,
    UserProfileOut,
    WorkbenchOut,
    PlannerTaskOut,
    LLMConfigOut,
    LLMConfigUpdate,
    LLMTestResponse,
)
from app.services.app_services import profile_to_out
from app.services.material_context import preload_material_context
from app.services.chat_store import (
    chat_message_out_from_record,
    pack_course_proposal_card,
    pack_exercise_sets,
    pack_explainer_videos,
    pack_code_labs,
    pack_mindmaps,
    pack_notes,
    pack_react_steps,
    pack_retrieval,
)

router = APIRouter()


def _resolve_course_id(user_id: str, course_id: str | None) -> str:
    if course_id:
        return course_id
    courses = get_course_service().list_courses(user_id, get_memory_service())
    if not courses:
        raise HTTPException(status_code=404, detail="No courses available")
    return courses[0].id


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/status")
async def system_status() -> dict:
    chroma = get_chroma_store()
    neo4j = get_neo4j_store()
    graph = get_graph_repo()
    return {
        "chroma": {
            "available": chroma.is_available(),
            "path": str(get_settings().chroma_dir),
            "collection": get_settings().chroma_collection,
            "count": chroma.count(),
        },
        "neo4j": {
            "available": neo4j.is_available(),
            "uri": get_settings().neo4j_uri,
        },
        "graph": graph.backend_info(),
        "retrieval": {
            "pipeline": "hybrid_simplified",
            "vector": "chroma" if chroma.is_available() else "keyword_fallback",
            "graph_hops": 1,
        },
        "llm": get_llm_config_service().public_view(),
    }


@router.get("/system/llm-config", response_model=LLMConfigOut)
async def get_llm_config() -> LLMConfigOut:
    return LLMConfigOut(**get_llm_config_service().public_view())


@router.put("/system/llm-config", response_model=LLMConfigOut)
async def update_llm_config(body: LLMConfigUpdate) -> LLMConfigOut:
    payload = body.model_dump(exclude_unset=True)
    if "api_key" in payload and not str(payload.get("api_key", "")).strip():
        payload.pop("api_key")
    saved = get_llm_config_service().save_config(payload)
    reload_llm_dependencies()
    return LLMConfigOut(**get_llm_config_service().public_view())


@router.post("/system/llm-config/test", response_model=LLMTestResponse)
async def test_llm_config() -> LLMTestResponse:
    cfg = get_llm_config_service().get_config()
    provider = get_llm_provider()
    try:
        preview = await provider.complete("请用一句话介绍你自己。", system="你是数据库课程学习助手。")
        return LLMTestResponse(
            ok=True,
            provider=cfg["provider"],
            model=cfg["model"],
            preview=preview[:500],
        )
    except Exception as exc:
        return LLMTestResponse(
            ok=False,
            provider=cfg["provider"],
            model=cfg["model"],
            preview="",
            error=str(exc),
        )


@router.post("/auth/login", response_model=UserOut)
async def login_user(request: UserLoginRequest) -> UserOut:
    try:
        return get_auth_service().login(request.email, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/auth/register", response_model=UserOut)
async def register_user(request: UserRegisterRequest) -> UserOut:
    try:
        return get_auth_service().register(
            request.name,
            request.email,
            request.password,
            request.major,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/auth/me", response_model=UserOut)
async def auth_me(user_id: str = Depends(require_user_id)) -> UserOut:
    user = get_auth_service().get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.post("/users/uploads", response_model=UserUploadOut)
async def upload_user_file(
    file: UploadFile = File(...),
    user_id: str = Depends(require_user_id),
) -> UserUploadOut:
    uploads_dir = get_settings().users_dir / user_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    original = (file.filename or "upload").strip()
    safe_name = re.sub(r"[^\w.\-]+", "_", Path(original).name)[:200] or "upload"
    dest = uploads_dir / safe_name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        index = 1
        while dest.exists():
            dest = uploads_dir / f"{stem}_{index}{suffix}"
            index += 1

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    dest.write_bytes(content)

    return UserUploadOut(
        filename=dest.name,
        relative_path=f"data/users/{user_id}/uploads/{dest.name}",
        size=len(content),
    )


@router.get("/profile", response_model=UserProfileOut)
async def get_profile(user_id: str = Depends(require_user_id)) -> UserProfileOut:
    profile = get_memory_service().get_profile(user_id)
    return profile_to_out(profile)


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(user_id: str = Depends(require_user_id)) -> list[CourseOut]:
    memory = get_memory_service()
    return get_course_service().list_courses(user_id, memory)


@router.get("/courses/{course_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(course_id: str) -> list[ChapterOut]:
    service = get_course_service()
    if not service.get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return service.list_chapters(course_id)


@router.get("/courses/{course_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    course_id: str,
    user_id: str = Depends(require_user_id),
) -> list[DocumentOut]:
    service = get_course_service()
    if not service.get_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    return service.list_documents(course_id, user_id, get_memory_service())


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    user_id: str = Depends(require_user_id),
) -> DocumentOut:
    doc = get_course_service().get_document(doc_id, user_id, get_memory_service())
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/documents/{doc_id}/progress", response_model=DocumentProgressOut)
async def update_document_progress(
    doc_id: str,
    body: DocumentProgressUpdateRequest,
    user_id: str = Depends(require_user_id),
) -> DocumentProgressOut:
    try:
        data = get_course_service().update_document_progress(
            user_id,
            get_memory_service(),
            doc_id,
            viewed_page=body.viewed_page,
            total_pages=body.total_pages,
            completed=body.completed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentProgressOut(**data)


@router.get("/documents/{doc_id}/file")
async def download_document(doc_id: str):
    path = get_course_service().get_material_path(doc_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    media_type = media_types.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": inline_content_disposition(path.name)},
    )


@router.get("/chat/history", response_model=list[ChatMessageOut])
async def chat_history(
    user_id: str = Depends(require_user_id),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ChatMessageOut]:
    memory = get_memory_service()
    raw = memory.get_recent_conversation(user_id, limit=limit)
    messages: list[ChatMessageOut] = []
    for row in raw:
        messages.append(
            chat_message_out_from_record(row, fallback_id=f"msg-{uuid4().hex[:8]}")
        )
    return messages


@router.delete("/chat/history")
async def clear_chat_history(user_id: str = Depends(require_user_id)) -> dict[str, str]:
    get_memory_service().clear_conversation(user_id)
    return {"status": "ok"}


@router.post("/memory/clear-short-term")
async def clear_short_term_memory(user_id: str = Depends(require_user_id)) -> dict[str, str]:
    get_memory_service().clear_short_term_memory(user_id)
    return {"status": "ok"}


@router.get("/chat/main-context")
async def chat_main_context(
    user_id: str = Depends(require_user_id),
    course_id: str | None = Query(default=None),
) -> dict[str, Any]:
    memory = get_memory_service()
    resolved_course_id = _resolve_course_id(user_id, course_id)
    context: dict[str, Any] = {
        "user_id": user_id,
        "message": "(当前无进行中的 ReAct 轮次)",
        "course_id": resolved_course_id,
        "profile": memory.get_profile(user_id),
        "me": memory.get_me(user_id),
        "explicit_memory": memory.get_explicit_memory_context(user_id),
        "session_dialogue": memory.get_today_dialogue_context(user_id, max_chars=10000),
        "react_steps": [],
        "traces": [],
    }
    preload_material_context(context, memory)
    return pack_main_agent_context(context)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(require_user_id),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    result = await orchestrator.chat(
        user_id=user_id,
        message=request.message,
        course_id=_resolve_course_id(user_id, request.course_id),
        document_id=request.document_id,
        course_workflow_action=request.course_workflow_action,
        course_proposal=request.course_proposal,
    )
    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
    user_msg = ChatMessageOut(
        id=f"msg-{uuid4().hex[:8]}",
        role="user",
        content=request.message,
        timestamp=now,
    )
    assistant_msg = ChatMessageOut(
        id=f"msg-{uuid4().hex[:8]}",
        role="assistant",
        content=result["answer"],
        timestamp=now,
        agent_traces=result.get("traces", []),
        react_steps=pack_react_steps(result.get("context")),
        retrieval=pack_retrieval(result.get("context", {}).get("retrieval")),
        explainer_videos=pack_explainer_videos(result.get("context")),
        exercise_sets=pack_exercise_sets(result.get("context")),
        mindmaps=pack_mindmaps(result.get("context")),
        notes=pack_notes(result.get("context")),
        code_lab_sets=pack_code_labs(result.get("context")),
        course_proposal_card=pack_course_proposal_card(result.get("context")),
    )
    return ChatResponse(
        messages=[user_msg, assistant_msg],
        profile=profile_to_out(result["profile"]),
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(require_user_id),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    course_id = _resolve_course_id(user_id, request.course_id)

    async def event_generator():
        try:
            async for event in orchestrator.chat_stream(
                user_id=user_id,
                message=request.message,
                course_id=course_id,
                document_id=request.document_id,
                course_workflow_action=request.course_workflow_action,
                course_proposal=request.course_proposal,
            ):
                if event.get("type") == "done":
                    result = event["result"]
                    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
                    proposal_card = pack_course_proposal_card(result.get("context"))
                    assistant_id = f"msg-{uuid4().hex[:8]}"
                    assistant_text = str(result["answer"] or "")
                    yield f"data: {json.dumps({'type': 'answer_start', 'message_id': assistant_id}, ensure_ascii=False)}\n\n"
                    chunk_size = 18
                    for idx in range(0, len(assistant_text), chunk_size):
                        delta = assistant_text[idx : idx + chunk_size]
                        if not delta:
                            continue
                        yield f"data: {json.dumps({'type': 'answer_delta', 'delta': delta}, ensure_ascii=False)}\n\n"
                    payload = {
                        "type": "done",
                        "messages": [
                            {
                                "id": f"msg-{uuid4().hex[:8]}",
                                "role": "user",
                                "content": request.message,
                                "timestamp": now,
                            },
                            {
                                "id": assistant_id,
                                "role": "assistant",
                                "content": assistant_text,
                                "timestamp": now,
                                "agent_traces": result.get("traces", []),
                                "react_steps": pack_react_steps(result.get("context")),
                                "retrieval": pack_retrieval(result.get("context", {}).get("retrieval")),
                                "explainer_videos": [
                                    v.model_dump() for v in pack_explainer_videos(result.get("context"))
                                ],
                                "exercise_sets": [
                                    s.model_dump() for s in pack_exercise_sets(result.get("context"))
                                ],
                                "mindmaps": [
                                    m.model_dump() for m in pack_mindmaps(result.get("context"))
                                ],
                                "notes": [
                                    n.model_dump() for n in pack_notes(result.get("context"))
                                ],
                                "code_lab_sets": [
                                    s.model_dump() for s in pack_code_labs(result.get("context"))
                                ],
                                "course_proposal_card": (
                                    proposal_card.model_dump() if proposal_card else None
                                ),
                            },
                        ],
                        "profile": profile_to_out(result["profile"]).model_dump(),
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/knowledge-graph", response_model=KnowledgeGraphOut)
async def knowledge_graph() -> KnowledgeGraphOut:
    return get_graph_service().get_graph()


@router.get("/practice/resources")
async def practice_resources() -> list[dict[str, str | int]]:
    exercises = [
        {**row, "kind": "exercise"} for row in get_practice_service().list_exercise_resources()
    ]
    code_labs = [{**row, "kind": "code_lab"} for row in get_code_lab_service().list_resources()]
    rows = exercises + code_labs
    rows.sort(key=lambda x: int(x.get("updated_at") or 0), reverse=True)
    return rows


@router.get("/practice/questions", response_model=list[ExerciseOut])
async def practice_questions(
    resource_id: str = Query(...),
) -> list[ExerciseOut]:
    return get_practice_service().list_questions(resource_id)


@router.post("/practice/submit", response_model=ExerciseSubmitResponse)
async def practice_submit(
    body: ExerciseSubmitRequest,
    resource_id: str = Query(...),
    user_id: str = Depends(require_user_id),
) -> ExerciseSubmitResponse:
    return await get_practice_service().submit(user_id, resource_id, body.answers)


@router.get("/code-lab/set", response_model=CodeLabSetOut)
async def code_lab_get_set(
    resource_id: str = Query(...),
    user_id: str = Depends(require_user_id),
) -> CodeLabSetOut:
    lab_set = get_code_lab_service().get_lab_set(user_id, resource_id)
    if lab_set is None:
        raise HTTPException(status_code=404, detail="未找到编程题集")
    return lab_set


@router.post("/code-lab/run", response_model=CodeLabRunResponse)
async def code_lab_run(
    body: CodeLabRunRequest,
    resource_id: str = Query(...),
    user_id: str = Depends(require_user_id),
) -> CodeLabRunResponse:
    _ = user_id
    try:
        return get_code_lab_service().run_challenge(resource_id, body.challenge_id, body.code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/code-lab/submit", response_model=CodeLabSubmitResponse)
async def code_lab_submit(
    body: CodeLabSubmitRequest,
    resource_id: str = Query(...),
    user_id: str = Depends(require_user_id),
) -> CodeLabSubmitResponse:
    try:
        return await get_code_lab_service().submit(user_id, resource_id, body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/resources", response_model=list[ResourceOut])
async def list_resources(user_id: str = Depends(require_user_id)) -> list[ResourceOut]:
    return get_resource_service().list_resources(user_id)


@router.get("/resources/{resource_id}", response_model=ResourceOut)
async def get_resource(resource_id: str, user_id: str = Depends(require_user_id)) -> ResourceOut:
    item = get_resource_service().get_resource(user_id, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="未找到资源")
    return item


@router.delete("/resources/{resource_id}")
async def delete_resource(resource_id: str, user_id: str = Depends(require_user_id)) -> dict[str, bool]:
    deleted = get_resource_service().delete_resource(user_id, resource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resource not found")
    get_question_repo().invalidate_cache()
    return {"ok": True}


@router.get("/explainer/play/{play_token}/{file_path:path}")
async def serve_explainer_bundle(play_token: str, file_path: str) -> FileResponse:
    bundle_dir = get_resource_service().resolve_explainer_bundle(play_token)
    if bundle_dir is None:
        raise HTTPException(status_code=404, detail="Explainer not found")

    safe_path = file_path.replace("\\", "/").lstrip("/")
    if ".." in safe_path.split("/"):
        raise HTTPException(status_code=403, detail="Invalid path")

    target = (bundle_dir / safe_path).resolve()
    root = bundle_dir.resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_types = {
        ".html": "text/html; charset=utf-8",
        ".mp3": "audio/mpeg",
        ".json": "application/json; charset=utf-8",
    }
    media_type = media_types.get(target.suffix.lower(), "application/octet-stream")
    return FileResponse(
        target,
        media_type=media_type,
        headers={"Content-Disposition": inline_content_disposition(target.name)},
    )


@router.get("/note/assets/{resource_id}/{filename}")
async def serve_note_asset(resource_id: str, filename: str) -> FileResponse:
    bundle_dir = get_resource_service().resolve_note_bundle(resource_id)
    if bundle_dir is None:
        raise HTTPException(status_code=404, detail="Note not found")

    safe_name = filename.replace("\\", "/").split("/")[-1]
    if not safe_name or ".." in safe_name:
        raise HTTPException(status_code=403, detail="Invalid path")

    target = (bundle_dir / "images" / safe_name).resolve()
    root = (bundle_dir / "images").resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    media_type = media_types.get(target.suffix.lower(), "application/octet-stream")
    return FileResponse(
        target,
        media_type=media_type,
        headers={"Content-Disposition": inline_content_disposition(target.name)},
    )


@router.post("/resources/generate", response_model=list[ResourceOut])
async def generate_resources(
    request: ResourceGenerateRequest,
    user_id: str = Depends(require_user_id),
) -> list[ResourceOut]:
    return await get_resource_service().generate(
        user_id,
        request.topic,
        request.types,
        _resolve_course_id(user_id, request.course_id),
    )


@router.post("/resources/generate/stream")
async def generate_resources_stream(
    request: ResourceGenerateRequest,
    user_id: str = Depends(require_user_id),
) -> StreamingResponse:
    course_id = _resolve_course_id(user_id, request.course_id)
    studio = get_resource_studio()

    async def event_generator():
        try:
            async for event in studio.generate_stream(
                user_id=user_id,
                topic=request.topic,
                types=request.types,
                course_id=course_id,
                clarification=request.clarification,
            ):
                if event.get("type") == "done":
                    payload = {
                        "type": "done",
                        "resources": event.get("resources", []),
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/path", response_model=list[LearningPathStepOut])
async def learning_path(user_id: str = Depends(require_user_id)) -> list[LearningPathStepOut]:
    return get_path_service().get_path(user_id)


@router.get("/path/courses", response_model=list[LearningCourseSummaryOut])
async def list_learning_courses(user_id: str = Depends(require_user_id)) -> list[LearningCourseSummaryOut]:
    return get_path_service().list_courses(user_id)


@router.get("/path/courses/{course_id}", response_model=LearningCourseDetailOut)
async def get_learning_course(course_id: str, user_id: str = Depends(require_user_id)) -> LearningCourseDetailOut:
    detail = get_path_service().get_course(user_id, course_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Learning course not found")
    return detail


@router.get("/workbench", response_model=WorkbenchOut)
async def workbench(user_id: str = Depends(require_user_id)) -> WorkbenchOut:
    data = get_memory_service().get_working_memory(user_id)
    tasks = [PlannerTaskOut(**t) for t in data.get("planner_tasks", [])]
    return WorkbenchOut(tasks=tasks)
