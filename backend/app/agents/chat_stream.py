"""Serialize chat stream events for SSE."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.material_context import material_basis_summary
from app.services.reader_context import reader_context_summary
from app.agents.prompt_blocks import compose_llm_prompt_preview


def serialize_react_step(step: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "step": step.get("step"),
        "thought": str(step.get("thought") or "").strip(),
        "action": str(step.get("action") or "").strip(),
        "expert": step.get("expert"),
        "tool": step.get("tool"),
        "skill": step.get("skill"),
        "observation": str(step.get("observation") or "").strip(),
        "status": str(step.get("status") or "done"),
    }
    if step.get("exercise"):
        out["exercise"] = step["exercise"]
    if step.get("code_lab"):
        out["code_lab"] = step["code_lab"]
    return out


def pack_main_agent_context(context: dict[str, Any]) -> dict[str, Any]:
    profile = context.get("profile") or {}
    message = str(context.get("message") or "")
    steps = context.get("react_steps") or []
    step_idx = len(steps) + 1 if steps else 1

    lines = [
        f"用户消息：{message}",
        f"当前课程：{profile.get('course', '') or '未设置'}",
        f"用户目标：{profile.get('goal', '') or '未知'}",
        f"近期主题：{', '.join(profile.get('recent_topics', [])) or '无'}",
        f"薄弱点：{', '.join(profile.get('weak_points', [])) or '未知'}",
        f"练习常错：{', '.join(profile.get('frequent_errors', [])) or '无'}",
        f"当前是第 {step_idx} 轮 ReAct。",
        material_basis_summary(context, None),
    ]

    explicit_memory = context.get("explicit_memory") or []
    if explicit_memory:
        lines.append("\n【显式长期记忆 memory】")
        for item in explicit_memory:
            lines.append(f"- [{item.get('type', 'memory')}] {item.get('content', '')}")

    session_dialogue = context.get("session_dialogue") or []
    if session_dialogue:
        lines.append("\n【今日会话上下文（仅用户发言和助手最终回复，不含 Thought/Observation/工具输出）】")
        for row in session_dialogue:
            role = "用户" if row.get("role") == "user" else "助手"
            time = f"[{row.get('time')}] " if row.get("time") else ""
            lines.append(f"{time}{role}: {row.get('content', '')}")

    if context.get("profile_gather"):
        from app.infrastructure.profile_tools import format_profile_memory_digest

        lines.append(
            format_profile_memory_digest(
                user_id=str(context.get("user_id") or ""),
                course_id=str(context.get("course_id") or ""),
                gather=context.get("profile_gather"),
            )
        )

    reader_note = reader_context_summary(context)
    if reader_note:
        lines.append(f"\n{reader_note}")

    if context.get("course_proposal") and not context.get("course_confirmed"):
        title = str(context["course_proposal"].get("course_title") or "定制课")
        lines.append(
            f"\n已有待确认课程提案《{title}》，请引导用户在对话卡片上确认；不要自行 call_expert 或 call_skill"
        )

    if steps:
        lines.append("\n历史 Observation：")
        for prev in steps:
            lines.append(
                f"- Step {prev.get('step')}: thought={prev.get('thought')} "
                f"action={prev.get('action')} "
                f"observation={prev.get('observation', '(无)')}"
            )
        search = context.get("exercise_search")
        if isinstance(search, dict) and search.get("matched_count") is not None:
            lines.append(
                f"\n练习题查找摘要：matched={search.get('matched_count')} "
                f"needs_generate={search.get('needs_generate')} "
                f"unanswered={search.get('unanswered')} wrong={search.get('wrong')}"
            )

    lines.append("\n请输出本轮 JSON。")
    user_prompt_text = "\n".join(lines)
    system_text = str(context.get("main_agent_system_text") or "").strip()
    prompt_text = compose_llm_prompt_preview(
        system_text=system_text,
        user_prompt_text=user_prompt_text,
    )

    retrieval = context.get("retrieval") if isinstance(context.get("retrieval"), dict) else {}
    chunks = []
    for i, chunk in enumerate(retrieval.get("chunks") or [], 1):
        if not isinstance(chunk, dict):
            continue
        chunks.append(
            {
                "index": i,
                "chunk_id": chunk.get("chunk_id"),
                "title": chunk.get("title"),
                "source_type": chunk.get("source_type"),
                "source": chunk.get("source"),
                "score": chunk.get("score"),
                "text": str(chunk.get("text") or "")[:1600],
            }
        )

    return {
        "step": step_idx,
        "updated_at": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
        "message": message,
        "system_text": system_text,
        "user_prompt_text": user_prompt_text,
        "prompt_text": prompt_text or user_prompt_text,
        "me": context.get("me") or {},
        "explicit_memory": explicit_memory,
        "session_dialogue": session_dialogue,
        "material_summary": material_basis_summary(context, None),
        "retrieval": {
            "queries": retrieval.get("queries") or [],
            "entities": retrieval.get("entities") or [],
            "source_types": retrieval.get("source_types") or [],
            "merge_boundary": retrieval.get("merge_boundary"),
            "summarized": retrieval.get("summarized"),
            "chunks": chunks,
        },
        "react_steps": [serialize_react_step(s) for s in steps],
    }


def pack_progress_event(context: dict[str, Any]) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "progress",
        "react_steps": [serialize_react_step(s) for s in context.get("react_steps") or []],
        "traces": list(context.get("traces") or []),
        "main_context": pack_main_agent_context(context),
    }
    card = context.get("course_proposal_card")
    if isinstance(card, dict) and card.get("kind") == "course_proposal":
        event["course_proposal_card"] = card
    sets = context.get("exercise_sets")
    if sets:
        event["exercise_sets"] = sets
    mindmaps = context.get("mindmaps")
    if mindmaps:
        event["mindmaps"] = mindmaps
    from app.services.chat_store import pack_code_labs, pack_notes

    notes = pack_notes(context)
    if notes:
        event["notes"] = [n.model_dump() for n in notes]
    code_labs = pack_code_labs(context)
    if code_labs:
        event["code_lab_sets"] = [s.model_dump() for s in code_labs]
    return event
