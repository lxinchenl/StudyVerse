import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.schemas import (
    ChapterOut,
    CourseOut,
    CourseResourceRefOut,
    DocumentOut,
    ExerciseOut,
    ExerciseResultOut,
    ExerciseSubmitResponse,
    GraphEdgeOut,
    GraphNodeOut,
    KnowledgeGraphMetaOut,
    KnowledgeGraphOut,
    LearningCourseDetailOut,
    LearningCourseSummaryOut,
    LearningModuleOut,
    LearningPathStepOut,
    PlannerTaskOut,
    ResourceOut,
    UserProfileOut,
    WorkbenchOut,
)
from app.infrastructure.document_parser import extract_text
from app.infrastructure.material_catalog import CourseCatalog, MaterialFile
from app.infrastructure.memory_service import FileMemoryService
from app.infrastructure.repositories import FileGraphRepository, QuestionRepository


class CourseService:
    def __init__(self, catalog: CourseCatalog):
        self.catalog = catalog
        self._content_cache: dict[str, tuple[str, int | None]] = {}

    def list_courses(self, user_id: str, memory: FileMemoryService) -> list[CourseOut]:
        result: list[CourseOut] = []
        for course in self.catalog.list_courses():
            chapters = self.catalog.list_chapters(course.id)
            docs = self.catalog.list_materials(course.id)
            progress = self._course_progress(course.id, user_id, memory)
            last_studied_at = self._course_last_studied_at(course.id, user_id, memory)
            result.append(
                CourseOut(
                    id=course.id,
                    title=course.title,
                    description=course.description,
                    progress=progress,
                    last_studied_at=last_studied_at,
                    chapter_count=len(chapters),
                    document_count=len(docs),
                )
            )
        return result

    def get_course(self, course_id: str) -> CourseOut | None:
        course = self.catalog.get_course(course_id)
        if not course:
            return None
        chapters = self.catalog.list_chapters(course_id)
        docs = self.catalog.list_materials(course_id)
        return CourseOut(
            id=course.id,
            title=course.title,
            description=course.description,
            progress=0,
            last_studied_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            chapter_count=len(chapters),
            document_count=len(docs),
        )

    def list_chapters(self, course_id: str) -> list[ChapterOut]:
        if not self.catalog.get_course(course_id):
            return []
        chapters = self.catalog.list_chapters(course_id)
        return [
            ChapterOut(id=c["id"], course_id=course_id, title=c["title"], order=i + 1)
            for i, c in enumerate(chapters)
        ]

    def _material_to_document(
        self,
        material: MaterialFile,
        *,
        include_content: bool = False,
        progress: float = 0.0,
    ) -> DocumentOut:
        content = None
        pages = material.pages
        if include_content:
            content, pages = self._get_content(material)
        return DocumentOut(
            id=material.id,
            course_id=material.course_id,
            chapter_id=material.chapter_key,
            title=material.title,
            type=material.doc_type,
            pages=pages,
            progress=round(float(progress), 1),
            content=content,
            file_name=material.path.name,
            file_url=f"/api/documents/{material.id}/file",
        )

    def _get_content(self, material: MaterialFile) -> tuple[str, int | None]:
        if material.id in self._content_cache:
            return self._content_cache[material.id]
        text, pages = extract_text(material.path)
        self._content_cache[material.id] = (text, pages)
        return text, pages

    def list_documents(self, course_id: str, user_id: str, memory: FileMemoryService) -> list[DocumentOut]:
        rows: list[DocumentOut] = []
        for material in self.catalog.list_materials(course_id):
            doc_progress = self._document_progress(user_id, memory, material.id)
            rows.append(self._material_to_document(material, progress=doc_progress))
        return rows

    def get_document(self, doc_id: str, user_id: str, memory: FileMemoryService) -> DocumentOut | None:
        material = self.catalog.get_material(doc_id)
        if material:
            doc_progress = self._document_progress(user_id, memory, material.id)
            return self._material_to_document(material, include_content=True, progress=doc_progress)
        return None

    def _document_progress(self, user_id: str, memory: FileMemoryService, doc_id: str) -> float:
        row = memory.get_document_learning_progress(user_id, doc_id)
        if not isinstance(row, dict):
            return 0.0
        return float(row.get("progress") or 0.0)

    def _course_progress(self, course_id: str, user_id: str, memory: FileMemoryService) -> float:
        docs = self.catalog.list_materials(course_id)
        if not docs:
            return 0.0
        values = [self._document_progress(user_id, memory, m.id) for m in docs]
        return round(sum(values) / len(values), 1)

    def _course_last_studied_at(self, course_id: str, user_id: str, memory: FileMemoryService) -> str:
        docs = self.catalog.list_materials(course_id)
        days: list[str] = []
        for material in docs:
            row = memory.get_document_learning_progress(user_id, material.id)
            if isinstance(row, dict) and row.get("last_studied_at"):
                days.append(str(row["last_studied_at"]))
        return max(days) if days else ""

    def update_document_progress(
        self,
        user_id: str,
        memory: FileMemoryService,
        doc_id: str,
        *,
        viewed_page: int | None = None,
        total_pages: int | None = None,
        completed: bool = False,
    ) -> dict[str, Any]:
        material = self.catalog.get_material(doc_id)
        if material is None:
            raise ValueError("Document not found")
        page_total = int(total_pages or material.pages or 0) or None
        row = memory.update_document_progress(
            user_id,
            doc_id=doc_id,
            course_id=material.course_id,
            doc_type=material.doc_type,
            viewed_page=viewed_page,
            total_pages=page_total,
            completed=completed,
        )
        return {
            "document_progress": float(row.get("progress") or 0.0),
            "course_progress": self._course_progress(material.course_id, user_id, memory),
            "last_studied_at": str(row.get("last_studied_at") or ""),
        }

    def get_material_path(self, doc_id: str) -> Path | None:
        material = self.catalog.get_material(doc_id)
        return material.path if material else None


class GraphService:
    def __init__(self, graph_repo: FileGraphRepository):
        self.graph_repo = graph_repo

    def get_graph(self) -> KnowledgeGraphOut:
        raw = self.graph_repo.get_graph()
        nodes = raw.get("nodes", [])
        edges = raw.get("edges", [])
        info: dict[str, Any] = {}
        if hasattr(self.graph_repo, "backend_info"):
            info = self.graph_repo.backend_info()
        return KnowledgeGraphOut(
            nodes=[GraphNodeOut(**n) for n in nodes],
            edges=[GraphEdgeOut(**e) for e in edges],
            meta=KnowledgeGraphMetaOut(
                backend=info.get("graph_backend", "unknown"),
                neo4j_connected=info.get("neo4j_connected", False),
                node_count=len(nodes),
                edge_count=len(edges),
            ),
        )


class PracticeService:
    def __init__(self, question_repo: QuestionRepository, memory: FileMemoryService, llm_provider=None):
        self.question_repo = question_repo
        self.memory = memory
        self.llm = llm_provider

    def list_exercise_resources(self) -> list[dict[str, str | int]]:
        grouped: dict[str, dict[str, str | int]] = {}
        for q in self.question_repo.list_questions():
            resource_id = str(q["resource_id"])
            title = str(q["resource_title"])
            updated_at = 0
            # Generated exercise bundles can be ordered by bundle mtime.
            generated_dir = getattr(self.question_repo, "generated_dir", None)
            if generated_dir is not None:
                meta_path = generated_dir / resource_id / "meta.json"
                if meta_path.exists():
                    updated_at = int(meta_path.stat().st_mtime)
            grouped[resource_id] = {"id": resource_id, "title": title, "updated_at": updated_at}
        return list(grouped.values())

    def list_questions(self, resource_id: str) -> list[ExerciseOut]:
        items: list[ExerciseOut] = []
        for q in self.question_repo.get_by_resource(resource_id):
            items.append(
                ExerciseOut(
                    id=q["id"],
                    resource_id=q["resource_id"],
                    resource_title=q["resource_title"],
                    topic=q.get("topic", ""),
                    difficulty=q.get("difficulty", "medium"),
                    question=q["question"],
                    grading_type=q.get("grading_type", "standard"),
                )
            )
        return items

    @staticmethod
    def _score_standard(user_answer: str, standard: str) -> float:
        if not user_answer.strip():
            return 0.0
        ua = user_answer.strip().lower()
        sa = standard.strip().lower()
        if ua == sa:
            return 100.0
        keywords = [w for w in standard.replace("，", " ").replace("。", " ").split() if len(w) >= 2]
        if not keywords:
            return 50.0 if sa in ua or ua in sa else 0.0
        hit = sum(1 for k in keywords if k in user_answer)
        return min(100.0, round(hit / len(keywords) * 100, 1))

    async def _score_rubric(self, question: str, rubric: str, user_answer: str) -> tuple[float, str]:
        if not user_answer.strip():
            return 0.0, "未作答"
        if self.llm is None:
            return 40.0, "开放题已记录，当前未启用 LLM 评分。"
        prompt = (
            f"题目：{question}\n"
            f"评分标准：{rubric}\n"
            f"学生答案：{user_answer}\n\n"
            "请只输出 JSON：{\"score\": 0-100 的数字, \"feedback\": \"一句评语\"}"
        )
        raw = await self.llm.complete(prompt, system="你是严谨的数据库课程阅卷助手，按 rubric 给分。")
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            data = json.loads(raw[start : end + 1])
            score = float(data.get("score", 0))
            score = max(0.0, min(100.0, score))
            feedback = str(data.get("feedback") or "")
            return round(score, 1), feedback
        except Exception:
            return 50.0, "已提交，自动评分暂不可用。"

    async def submit(self, user_id: str, resource_id: str, answers: dict[str, str]) -> ExerciseSubmitResponse:
        questions = {q["id"]: q for q in self.question_repo.get_by_resource(resource_id)}
        results: list[ExerciseResultOut] = []
        attempt_rows: list[dict[str, Any]] = []
        scores: list[float] = []
        wrong_topics: list[str] = []
        for qid, ans in answers.items():
            q = questions.get(qid)
            if not q:
                continue
            grading = q.get("grading_type", "standard")
            feedback = ""
            if grading == "rubric":
                score, feedback = await self._score_rubric(q["question"], q.get("rubric", ""), ans)
                reveal = q.get("rubric") or "（开放题，按评分标准给分）"
            else:
                score = self._score_standard(ans, q.get("standard_answer", ""))
                reveal = q.get("standard_answer", "")
            scores.append(score)
            if score < 60:
                wrong_topics.append(q.get("topic", ""))
            results.append(
                ExerciseResultOut(
                    question_id=qid,
                    score=score,
                    standard_answer=reveal,
                    grading_type=grading,
                    feedback=feedback,
                )
            )
            attempt_rows.append({"question_id": qid, "score": score, "user_answer": ans})
        total = round(sum(scores) / len(scores), 1) if scores else 0.0
        profile = self.memory.get_profile(user_id)
        profile.setdefault("mastery", {})["practice"] = total / 100
        profile["frequent_errors"] = list(set(profile.get("frequent_errors", []) + wrong_topics))[:5]
        self.memory.save_profile(user_id, profile)
        self.memory.record_practice_attempt(user_id, resource_id, attempt_rows)
        return ExerciseSubmitResponse(
            total_score=total,
            results=results,
            profile=profile_to_out(profile),
        )


class CodeLabService:
    def __init__(self, code_lab_repo, memory: FileMemoryService):
        from app.infrastructure.python_sandbox import compare_stdout, run_python

        self.code_lab_repo = code_lab_repo
        self.memory = memory
        self._run_python = run_python
        self._compare_stdout = compare_stdout

    def list_resources(self) -> list[dict[str, str | int]]:
        grouped: dict[str, dict[str, str | int]] = {}
        for c in self.code_lab_repo.list_challenges():
            resource_id = str(c["resource_id"])
            title = str(c.get("resource_title") or "编程练习")
            updated_at = 0
            meta_path = self.code_lab_repo.bundle_dir / resource_id / "meta.json"
            if meta_path.exists():
                updated_at = int(meta_path.stat().st_mtime)
            grouped[resource_id] = {"id": resource_id, "title": title, "updated_at": updated_at}
        return list(grouped.values())

    def list_challenges(self, resource_id: str) -> list:
        from app.domain.schemas import CodeLabChallengeOut

        items: list[CodeLabChallengeOut] = []
        for c in self.code_lab_repo.get_by_resource(resource_id):
            items.append(
                CodeLabChallengeOut(
                    id=c["id"],
                    topic=c.get("topic", ""),
                    difficulty=c.get("difficulty", "medium"),
                    question=c["question"],
                    starter_code=c.get("starter_code", ""),
                    setup_code=c.get("setup_code", ""),
                    language=c.get("language", "python"),
                    hint=c.get("hint", ""),
                )
            )
        return items

    def get_lab_set(self, user_id: str, resource_id: str):
        from app.domain.schemas import CodeLabChallengeOut, CodeLabSetOut

        rows = self.code_lab_repo.get_by_resource(resource_id)
        if not rows:
            return None
        attempts = self.memory.get_practice_attempts(user_id).get(resource_id, {})
        title = str(rows[0].get("resource_title") or "编程练习")
        topic = str(rows[0].get("topic") or "")
        challenges: list[CodeLabChallengeOut] = []
        for c in rows:
            last = attempts.get(c["id"])
            score = last.get("score") if isinstance(last, dict) else None
            status = "unanswered"
            if score is not None:
                status = "passed" if score >= 60 else "failed"
            challenges.append(
                CodeLabChallengeOut(
                    id=c["id"],
                    topic=c.get("topic", ""),
                    difficulty=c.get("difficulty", "medium"),
                    question=c["question"],
                    starter_code=c.get("starter_code", ""),
                    setup_code=c.get("setup_code", ""),
                    language=c.get("language", "python"),
                    hint=c.get("hint", ""),
                    attempt_status=status,
                    last_score=score,
                )
            )
        return CodeLabSetOut(
            resource_id=resource_id,
            title=title,
            topic=topic,
            summary=f"共 {len(challenges)} 道 Python 编程题 · stdout 沙箱判题",
            challenges=challenges,
        )

    def run_challenge(self, resource_id: str, challenge_id: str, code: str):
        from app.domain.schemas import CodeLabRunResponse
        from app.infrastructure.code_lab_script import prepare_submitted_code

        challenge = self._get_challenge(resource_id, challenge_id)
        setup = challenge.get("setup_code", "")
        prepared = prepare_submitted_code(setup=setup, code=code)
        result = self._run_python(setup=setup, code=prepared)
        return CodeLabRunResponse(
            ok=bool(result.get("ok")) and not result.get("error"),
            stdout=str(result.get("stdout") or ""),
            stderr=str(result.get("stderr") or "") or str(result.get("error") or ""),
            exit_code=int(result.get("exit_code") or -1),
            error=str(result.get("error") or ""),
        )

    async def submit(self, user_id: str, resource_id: str, answers: dict[str, str]):
        from app.domain.schemas import CodeLabResultOut, CodeLabSubmitResponse

        challenges = {c["id"]: c for c in self.code_lab_repo.get_by_resource(resource_id)}
        results: list[CodeLabResultOut] = []
        attempt_rows: list[dict[str, Any]] = []
        scores: list[float] = []

        from app.infrastructure.code_lab_script import prepare_submitted_code

        for cid, code in answers.items():
            challenge = challenges.get(cid)
            if not challenge:
                continue
            setup = challenge.get("setup_code", "")
            ref = self._run_python(setup=setup, code=challenge.get("solution_code", ""))
            prepared = prepare_submitted_code(setup=setup, code=code)
            user_run = self._run_python(setup=setup, code=prepared)
            ref_out = str(ref.get("stdout") or "")
            user_out = str(user_run.get("stdout") or "")
            passed = (
                bool(ref.get("ok"))
                and bool(user_run.get("ok"))
                and self._compare_stdout(user_out, ref_out)
            )
            score = 100.0 if passed else 0.0
            feedback = "输出与参考答案一致，通过。" if passed else "输出不一致或未成功运行，请检查逻辑与打印格式。"
            if user_run.get("error"):
                feedback = str(user_run.get("error"))
            elif user_run.get("stderr"):
                feedback = str(user_run.get("stderr"))[:240]
            scores.append(score)
            results.append(
                CodeLabResultOut(
                    challenge_id=cid,
                    score=score,
                    passed=passed,
                    expected_stdout=ref_out[:1200],
                    actual_stdout=user_out[:1200],
                    stderr=str(user_run.get("stderr") or "")[:500],
                    feedback=feedback,
                )
            )
            attempt_rows.append({"question_id": cid, "score": score, "user_answer": code[:4000]})

        total = round(sum(scores) / len(scores), 1) if scores else 0.0
        self.memory.record_practice_attempt(user_id, resource_id, attempt_rows)
        profile = self.memory.get_profile(user_id)
        return CodeLabSubmitResponse(
            total_score=total,
            results=results,
            profile=profile_to_out(profile),
        )

    def _get_challenge(self, resource_id: str, challenge_id: str) -> dict[str, Any]:
        for c in self.code_lab_repo.get_by_resource(resource_id):
            if c["id"] == challenge_id:
                return c
        raise ValueError(f"未找到题目 {challenge_id}")


class ResourceService:
    def __init__(self, resources_dir: Path, llm_provider):
        self.resources_dir = resources_dir
        self.llm = llm_provider
        self.resources_dir.mkdir(parents=True, exist_ok=True)

    def _user_file(self, user_id: str) -> Path:
        return self.resources_dir / f"{user_id}.json"

    def _explainer_dir(self, resource_id: str) -> Path:
        return self.resources_dir / "explainer" / resource_id

    def list_resources(self, user_id: str) -> list[ResourceOut]:
        path = self._user_file(user_id)
        if not path.exists():
            return []
        return [ResourceOut(**row) for row in json.loads(path.read_text(encoding="utf-8"))]

    def get_resource(self, user_id: str, resource_id: str) -> ResourceOut | None:
        for item in self.list_resources(user_id):
            if item.id == resource_id:
                return item
        return None

    def resolve_explainer_bundle(self, play_token: str) -> Path | None:
        for meta_path in (self.resources_dir / "explainer").glob("*/meta.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if meta.get("play_token") == play_token:
                bundle = meta_path.parent
                if bundle.is_dir():
                    return bundle
        return None

    def resolve_note_bundle(self, resource_id: str) -> Path | None:
        if not resource_id.startswith("note-"):
            return None
        bundle = self.resources_dir / "note" / resource_id
        if bundle.is_dir() and (bundle / "note.json").exists():
            return bundle
        return None

    def register_explainer_video(
        self,
        user_id: str,
        *,
        resource_id: str,
        play_token: str,
        title: str,
        summary: str,
        topic: str,
        scene_count: int,
    ) -> ResourceOut:
        player_url = f"/api/explainer/play/{play_token}/index.html"
        meta = {
            "user_id": user_id,
            "resource_id": resource_id,
            "play_token": play_token,
            "title": title,
            "topic": topic,
            "scene_count": scene_count,
        }
        bundle_dir = self._explainer_dir(resource_id)
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        item = ResourceOut(
            id=resource_id,
            type="video_script",
            title=title,
            summary=summary,
            content=player_url,
            topic=topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            player_url=player_url,
            scene_count=scene_count,
        )
        existing = self.list_resources(user_id)
        existing = [r for r in existing if r.id != resource_id]
        all_items = [item] + existing
        self._user_file(user_id).write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item

    def register_mindmap(
        self,
        user_id: str,
        *,
        resource_id: str,
        title: str,
        topic: str,
        summary: str,
        mermaid_source: str,
    ) -> ResourceOut:
        content = f"```mermaid\n{mermaid_source}\n```"
        item = ResourceOut(
            id=resource_id,
            type="mindmap",
            title=title,
            summary=summary,
            content=content,
            topic=topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        existing = self.list_resources(user_id)
        existing = [r for r in existing if r.id != resource_id]
        all_items = [item] + existing
        self._user_file(user_id).write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item

    def register_exercise_set(
        self,
        user_id: str,
        *,
        resource_id: str,
        title: str,
        topic: str,
        summary: str,
        question_count: int,
    ) -> ResourceOut:
        item = ResourceOut(
            id=resource_id,
            type="exercise",
            title=title,
            summary=summary,
            content=f"/practice?resource={resource_id}",
            topic=topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        existing = self.list_resources(user_id)
        existing = [r for r in existing if r.id != resource_id]
        all_items = [item] + existing
        self._user_file(user_id).write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item

    def register_note(
        self,
        user_id: str,
        *,
        resource_id: str,
        title: str,
        topic: str,
        summary: str,
        markdown: str,
    ) -> ResourceOut:
        item = ResourceOut(
            id=resource_id,
            type="note",
            title=title,
            summary=summary,
            content=markdown,
            topic=topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        existing = self.list_resources(user_id)
        existing = [r for r in existing if r.id != resource_id]
        all_items = [item] + existing
        self._user_file(user_id).write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item

    def register_code_lab_set(
        self,
        user_id: str,
        *,
        resource_id: str,
        title: str,
        topic: str,
        summary: str,
        challenge_count: int,
    ) -> ResourceOut:
        preview = f"# {title}\n\n共 {challenge_count} 道 Python 编程题。在对话卡片或资源库中编写代码、运行并提交判题。"
        item = ResourceOut(
            id=resource_id,
            type="code_lab",
            title=title,
            summary=summary,
            content=preview,
            topic=topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        existing = self.list_resources(user_id)
        existing = [r for r in existing if r.id != resource_id]
        all_items = [item] + existing
        self._user_file(user_id).write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item

    async def generate(self, user_id: str, topic: str, types: list[str], course_id: str) -> list[ResourceOut]:
        created: list[ResourceOut] = []
        for rtype in types:
            content = await self.llm.complete(f"为课程「{course_id}」话题「{topic}」生成 {rtype} 类型学习资源")
            item = ResourceOut(
                id=f"res-{uuid4().hex[:8]}",
                type=rtype,
                title=f"{topic}-{rtype}",
                summary=f"Agent 生成的 {rtype} 资源",
                content=content,
                topic=topic,
                created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
            created.append(item)
        existing = self.list_resources(user_id)
        all_items = existing + created
        self._user_file(user_id).write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return created

    def delete_resource(self, user_id: str, resource_id: str) -> bool:
        path = self._user_file(user_id)
        if not path.exists():
            return False
        rows = json.loads(path.read_text(encoding="utf-8"))
        target = next((row for row in rows if row.get("id") == resource_id), None)
        if target is None:
            return False
        remaining = [row for row in rows if row.get("id") != resource_id]
        path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cleanup_resource_files(resource_id, str(target.get("type", "")))
        return True

    def _cleanup_resource_files(self, resource_id: str, resource_type: str) -> None:
        bundle_dirs: list[Path] = []
        if resource_type == "video_script":
            bundle_dirs.append(self._explainer_dir(resource_id))
        elif resource_type == "mindmap":
            bundle_dirs.append(self.resources_dir / "mindmap" / resource_id)
        elif resource_type == "exercise":
            bundle_dirs.append(self.resources_dir / "exercises" / resource_id)
        elif resource_type == "note":
            bundle_dirs.append(self.resources_dir / "note" / resource_id)
        elif resource_type == "code_lab":
            bundle_dirs.append(self.resources_dir / "code_lab" / resource_id)
        for bundle_dir in bundle_dirs:
            if bundle_dir.is_dir():
                shutil.rmtree(bundle_dir, ignore_errors=True)


class PathService:
    def __init__(self, memory: FileMemoryService):
        self.memory = memory
        from app.core.config import get_settings

        self.users_dir = get_settings().users_dir

    def _load(self, user_id: str) -> list[dict[str, Any]]:
        from app.infrastructure.learning_path_store import load_courses

        return load_courses(self.users_dir, user_id)

    def list_courses(self, user_id: str) -> list[LearningCourseSummaryOut]:
        courses = self._load(user_id)
        result: list[LearningCourseSummaryOut] = []
        for course in courses:
            modules = course.get("modules") or []
            done = sum(1 for m in modules if m.get("status") == "done")
            total = len(modules) or 1
            result.append(
                LearningCourseSummaryOut(
                    id=str(course.get("id") or ""),
                    title=str(course.get("title") or "定制课"),
                    topic=str(course.get("topic") or ""),
                    summary=str(course.get("summary") or ""),
                    status=str(course.get("status") or "in_progress"),
                    module_count=len(modules),
                    progress=round(done / total, 2),
                    created_at=str(course.get("created_at") or ""),
                )
            )
        return result

    def get_course(self, user_id: str, course_id: str) -> LearningCourseDetailOut | None:
        from app.infrastructure.learning_path_store import get_course

        raw = get_course(self.users_dir, user_id, course_id)
        if raw is None:
            return None
        modules: list[LearningModuleOut] = []
        for mod in raw.get("modules") or []:
            refs = [
                CourseResourceRefOut(
                    type=str(r.get("type") or ""),
                    resource_id=str(r.get("resource_id") or ""),
                    title=str(r.get("title") or ""),
                    order=int(r.get("order") or idx),
                    learning_order_reason=str(r.get("learning_order_reason") or ""),
                )
                for idx, r in enumerate(sorted(
                    mod.get("resources") or [],
                    key=lambda x: int(x.get("order") or 0),
                ), start=1)
            ]
            modules.append(
                LearningModuleOut(
                    id=str(mod.get("id") or ""),
                    title=str(mod.get("title") or ""),
                    objective=str(mod.get("objective") or ""),
                    status=str(mod.get("status") or "pending"),
                    estimated_minutes=int(mod.get("estimated_minutes") or 45),
                    chapter_key=str(mod.get("chapter_key") or ""),
                    resources=refs,
                )
            )
        return LearningCourseDetailOut(
            id=str(raw.get("id") or ""),
            title=str(raw.get("title") or ""),
            topic=str(raw.get("topic") or ""),
            summary=str(raw.get("summary") or ""),
            status=str(raw.get("status") or "in_progress"),
            created_at=str(raw.get("created_at") or ""),
            modules=modules,
        )

    def save_course(self, user_id: str, course: dict[str, Any]) -> dict[str, Any]:
        from app.infrastructure.learning_path_store import append_course

        return append_course(self.users_dir, user_id, course)

    def update_course(self, user_id: str, course_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        from app.infrastructure.learning_path_store import update_course

        return update_course(self.users_dir, user_id, course_id, patch)

    def get_path(self, user_id: str) -> list[LearningPathStepOut]:
        """Legacy flat steps — from latest learning course modules."""
        courses = self._load(user_id)
        if not courses:
            profile = self.memory.get_profile(user_id)
            weak_points = profile.get("weak_points", [])
            if not weak_points:
                return []
            weak = weak_points[0]
            return [
                LearningPathStepOut(
                    id="step-1",
                    title=f"补齐：{weak}",
                    objective="理解核心概念",
                    status="in_progress",
                    estimated_minutes=35,
                    resources=[],
                ),
            ]
        latest = courses[0]
        steps: list[LearningPathStepOut] = []
        for mod in latest.get("modules") or []:
            refs = mod.get("resources") or []
            steps.append(
                LearningPathStepOut(
                    id=str(mod.get("id") or ""),
                    title=str(mod.get("title") or ""),
                    objective=str(mod.get("objective") or ""),
                    status=str(mod.get("status") or "pending"),
                    estimated_minutes=int(mod.get("estimated_minutes") or 45),
                    resources=[str(r.get("resource_id") or "") for r in refs if r.get("resource_id")],
                )
            )
        return steps


def profile_to_out(profile: dict[str, Any]) -> UserProfileOut:
    return UserProfileOut(
        student_id=profile.get("student_id", ""),
        major=profile.get("major", ""),
        course=profile.get("course", ""),
        goal=profile.get("goal", ""),
        recent_topics=profile.get("recent_topics", []),
        weak_points=profile.get("weak_points", []),
        frequent_errors=profile.get("frequent_errors", []),
        preferences=profile.get("preferences", []),
        mastery=profile.get("mastery", {}),
    )
