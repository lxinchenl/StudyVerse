"""Pack chat payloads for API responses and conversation persistence."""

from __future__ import annotations

from typing import Any

from app.agents.chat_stream import serialize_react_step
from app.domain.schemas import (
    ChatMessageOut,
    CodeLabChallengeOut,
    CodeLabSetOut,
    CourseProposalCardOut,
    ExerciseQuestionOut,
    ExerciseSetOut,
    ExplainerVideoOut,
    MindmapOut,
    NoteOut,
)


def pack_explainer_videos(context: dict | None) -> list[ExplainerVideoOut]:
    if not context:
        return []
    videos: list[ExplainerVideoOut] = []
    for item in context.get("generated_resources") or []:
        if item.get("type") != "video_script":
            continue
        player_url = item.get("player_url")
        if not player_url:
            continue
        videos.append(
            ExplainerVideoOut(
                resource_id=str(item.get("resource_id", "")),
                title=str(item.get("title") or "讲解视频"),
                summary=str(item.get("summary") or "")[:200],
                player_url=str(player_url),
                scene_count=int(item.get("scene_count") or 0),
            )
        )
    return videos


def pack_exercise_sets(context: dict | None) -> list[ExerciseSetOut]:
    if not context:
        return []
    packed: list[ExerciseSetOut] = []
    for item in context.get("exercise_sets") or []:
        if not isinstance(item, dict) or not item.get("resource_id"):
            continue
        questions = [
            ExerciseQuestionOut(**q)
            for q in (item.get("questions") or [])
            if isinstance(q, dict) and q.get("id")
        ]
        packed.append(
            ExerciseSetOut(
                resource_id=str(item["resource_id"]),
                title=str(item.get("title") or "练习题"),
                topic=str(item.get("topic") or ""),
                summary=str(item.get("summary") or "")[:240],
                questions=questions,
            )
        )
    return packed


def pack_notes(context: dict | None) -> list[NoteOut]:
    if not context:
        return []
    packed: list[NoteOut] = []
    seen: set[str] = set()
    fallback_markdown = str(context.get("generated_note") or "")

    for item in context.get("notes") or []:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("resource_id") or "")
        if not rid or rid in seen:
            continue
        markdown = str(item.get("markdown") or fallback_markdown or "").strip()
        if not markdown:
            continue
        seen.add(rid)
        packed.append(
            NoteOut(
                resource_id=rid,
                title=str(item.get("title") or "学习笔记"),
                topic=str(item.get("topic") or ""),
                summary=str(item.get("summary") or "")[:240],
                markdown=markdown,
            )
        )

    for item in context.get("generated_resources") or []:
        if item.get("type") != "note":
            continue
        rid = str(item.get("resource_id") or "")
        if not rid or rid in seen:
            continue
        markdown = str(item.get("markdown") or fallback_markdown or "").strip()
        if not markdown:
            continue
        seen.add(rid)
        packed.append(
            NoteOut(
                resource_id=rid,
                title=str(item.get("title") or "学习笔记"),
                topic=str(item.get("topic") or ""),
                summary=str(item.get("summary") or "")[:240],
                markdown=markdown,
            )
        )
    return packed


def pack_code_labs(context: dict | None) -> list[CodeLabSetOut]:
    if not context:
        return []
    packed: list[CodeLabSetOut] = []
    seen: set[str] = set()
    for item in context.get("code_lab_sets") or []:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("resource_id") or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        challenges = [
            CodeLabChallengeOut(
                id=str(c.get("id") or ""),
                topic=str(c.get("topic") or ""),
                difficulty=str(c.get("difficulty") or "medium"),
                question=str(c.get("question") or ""),
                starter_code=str(c.get("starter_code") or ""),
                setup_code=str(c.get("setup_code") or ""),
                language=str(c.get("language") or "python"),
                hint=str(c.get("hint") or ""),
                attempt_status=c.get("attempt_status"),
                last_score=c.get("last_score"),
            )
            for c in (item.get("challenges") or [])
            if isinstance(c, dict) and c.get("id")
        ]
        if not challenges:
            continue
        packed.append(
            CodeLabSetOut(
                resource_id=rid,
                title=str(item.get("title") or "编程练习"),
                topic=str(item.get("topic") or ""),
                summary=str(item.get("summary") or "")[:240],
                challenges=challenges,
            )
        )
    return packed


def pack_mindmaps(context: dict | None) -> list[MindmapOut]:
    if not context:
        return []
    packed: list[MindmapOut] = []
    seen: set[str] = set()
    for item in context.get("mindmaps") or []:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("resource_id") or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        mermaid = str(item.get("mermaid_source") or item.get("mermaid") or "").strip()
        if not mermaid:
            continue
        packed.append(
            MindmapOut(
                resource_id=rid,
                title=str(item.get("title") or "思维导图"),
                topic=str(item.get("topic") or ""),
                summary=str(item.get("summary") or "")[:240],
                mermaid_source=mermaid,
            )
        )
    for item in context.get("generated_resources") or []:
        if item.get("type") != "mindmap":
            continue
        rid = str(item.get("resource_id") or "")
        if not rid or rid in seen:
            continue
        mermaid = str(item.get("mermaid_source") or "").strip()
        if not mermaid:
            continue
        seen.add(rid)
        packed.append(
            MindmapOut(
                resource_id=rid,
                title=str(item.get("title") or "思维导图"),
                topic=str(item.get("topic") or ""),
                summary=str(item.get("summary") or "")[:240],
                mermaid_source=mermaid,
            )
        )
    return packed


def pack_react_steps(context: dict | None) -> list[dict[str, Any]]:
    if not context:
        return []
    packed: list[dict[str, Any]] = []
    for step in context.get("react_steps") or []:
        if not isinstance(step, dict):
            continue
        packed.append(serialize_react_step(step))
    return packed


def pack_retrieval(retrieval: dict | None) -> dict | None:
    if not retrieval:
        return None
    return {
        "query": retrieval.get("query"),
        "queries": retrieval.get("queries", []),
        "entities": retrieval.get("entities", []),
        "source_types": retrieval.get("source_types", []),
        "chunks": [
            {
                "chunk_id": c.get("chunk_id"),
                "title": c.get("title"),
                "text": (c.get("text") or "")[:500],
                "source": c.get("source"),
                "score": c.get("score"),
            }
            for c in retrieval.get("chunks", [])
        ],
        "kg_context": retrieval.get("kg_context", [])[:5],
    }


def pack_course_proposal_card(context: dict | None) -> CourseProposalCardOut | None:
    if not context:
        return None
    card = context.get("course_proposal_card")
    if not isinstance(card, dict) or card.get("kind") != "course_proposal":
        return None
    try:
        return CourseProposalCardOut(**card)
    except Exception:
        return None


def chat_message_out_from_context(
    *,
    msg_id: str,
    role: str,
    content: str,
    timestamp: str,
    context: dict | None = None,
) -> ChatMessageOut:
    ctx = context or {}
    return ChatMessageOut(
        id=msg_id,
        role=role,
        content=content,
        timestamp=timestamp,
        agent_traces=list(ctx.get("traces") or []),
        react_steps=pack_react_steps(ctx),
        retrieval=pack_retrieval(ctx.get("retrieval")),
        explainer_videos=pack_explainer_videos(ctx),
        exercise_sets=pack_exercise_sets(ctx),
        mindmaps=pack_mindmaps(ctx),
        notes=pack_notes(ctx),
        code_lab_sets=pack_code_labs(ctx),
        course_proposal_card=pack_course_proposal_card(ctx),
    )


def build_user_record(*, msg_id: str, content: str, timestamp: str) -> dict[str, Any]:
    return {"id": msg_id, "time": timestamp, "role": "user", "content": content}


def build_assistant_record(
    *,
    msg_id: str,
    content: str,
    timestamp: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    proposal_card = pack_course_proposal_card(context)
    return {
        "id": msg_id,
        "time": timestamp,
        "role": "assistant",
        "content": content,
        "react_steps": pack_react_steps(context),
        "agent_traces": list(context.get("traces") or []),
        "retrieval": pack_retrieval(context.get("retrieval")),
        "explainer_videos": [v.model_dump() for v in pack_explainer_videos(context)],
        "exercise_sets": [s.model_dump() for s in pack_exercise_sets(context)],
        "mindmaps": [m.model_dump() for m in pack_mindmaps(context)],
        "notes": [n.model_dump() for n in pack_notes(context)],
        "code_lab_sets": [s.model_dump() for s in pack_code_labs(context)],
        "course_proposal_card": proposal_card.model_dump() if proposal_card else None,
    }


def chat_message_out_from_record(row: dict[str, Any], *, fallback_id: str) -> ChatMessageOut:
    explainer = [
        ExplainerVideoOut(**v)
        for v in (row.get("explainer_videos") or [])
        if isinstance(v, dict) and v.get("resource_id")
    ]
    exercises = [
        ExerciseSetOut(
            resource_id=str(item["resource_id"]),
            title=str(item.get("title") or "练习题"),
            topic=str(item.get("topic") or ""),
            summary=str(item.get("summary") or "")[:240],
            questions=[
                ExerciseQuestionOut(**q)
                for q in (item.get("questions") or [])
                if isinstance(q, dict) and q.get("id")
            ],
        )
        for item in (row.get("exercise_sets") or [])
        if isinstance(item, dict) and item.get("resource_id")
    ]
    mindmaps = [
        MindmapOut(**m)
        for m in (row.get("mindmaps") or [])
        if isinstance(m, dict) and m.get("resource_id")
    ]
    notes = [
        NoteOut(**n)
        for n in (row.get("notes") or [])
        if isinstance(n, dict) and n.get("resource_id") and n.get("markdown")
    ]
    code_lab_sets = [
        CodeLabSetOut(
            resource_id=str(item["resource_id"]),
            title=str(item.get("title") or "编程练习"),
            topic=str(item.get("topic") or ""),
            summary=str(item.get("summary") or "")[:240],
            challenges=[
                CodeLabChallengeOut(**c)
                for c in (item.get("challenges") or [])
                if isinstance(c, dict) and c.get("id")
            ],
        )
        for item in (row.get("code_lab_sets") or [])
        if isinstance(item, dict) and item.get("resource_id")
    ]
    return ChatMessageOut(
        id=str(row.get("id") or fallback_id),
        role=str(row.get("role") or "user"),
        content=str(row.get("content") or ""),
        timestamp=str(row.get("time") or ""),
        agent_traces=list(row.get("agent_traces") or []),
        react_steps=list(row.get("react_steps") or []),
        retrieval=row.get("retrieval"),
        explainer_videos=explainer,
        exercise_sets=exercises,
        mindmaps=mindmaps,
        notes=notes,
        code_lab_sets=code_lab_sets,
        course_proposal_card=(
            CourseProposalCardOut(**row["course_proposal_card"])
            if isinstance(row.get("course_proposal_card"), dict)
            else None
        ),
    )
