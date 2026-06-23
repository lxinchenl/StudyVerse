"""ReAct driver for note-agent — intent routing + material pipeline via tools."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.agents.resources.note_design import (
    CONVERSATION_NOTE_SYSTEM,
    INTENT_SYSTEM,
    MATERIAL_NOTE_SYSTEM,
    NOTE_REACT_SYSTEM,
    build_conversation_note_prompt,
    build_intent_prompt,
    build_material_note_prompt,
    build_react_prompt,
    parse_intent,
    parse_note_output,
    parse_react_action,
)
from app.infrastructure.note_assets import build_image_catalog_from_process
from app.infrastructure.note_process import apply_vision_to_process, serialize_process_for_llm
from app.interfaces.contracts import LLMProvider, MemoryService
from app.tools.executor import invoke_tool

MAX_NOTE_REACT_STEPS = 12
NoteProgressFn = Callable[[dict[str, Any]], Awaitable[None]]


async def run_note_react(
    *,
    llm: LLMProvider,
    memory: MemoryService,
    context: dict[str, Any],
    agent_name: str,
    trace_fn,
    progress_fn: NoteProgressFn | None = None,
) -> dict[str, Any]:
    user_id = context["user_id"]
    message = str(context.get("message") or "")
    course_id = str(context.get("course_id") or "")
    conversation = memory.get_recent_conversation(user_id, limit=20)

    intent_raw = await llm.complete(
        build_intent_prompt(message=message, conversation=conversation),
        system=INTENT_SYSTEM,
    )
    try:
        intent = parse_intent(intent_raw)
    except ValueError:
        intent = {
            "mode": "conversation",
            "title_hint": "学习笔记",
            "topic": message[:40],
            "chapter_key": "",
            "material_id": "",
            "course_hint": "",
            "rationale": "意图解析失败，默认按对话整理",
        }

    react_steps: list[dict[str, Any]] = []

    async def _record_step(step: dict[str, Any]) -> None:
        react_steps.append(step)
        if progress_fn is not None:
            await progress_fn(step)

    await _record_step(
        {
            "step": 1,
            "thought": intent.get("rationale", ""),
            "action": "analyze_intent",
            "observation": f"模式={intent['mode']}，标题={intent.get('title_hint')}",
            "status": "done",
        }
    )

    if intent["mode"] == "conversation":
        await _record_step(
            {
                "step": 2,
                "thought": "对话模式，整理 Markdown",
                "action": "compose_notes",
                "observation": "执行中…",
                "status": "running",
            }
        )
        payload = await _compose_conversation_notes(
            llm=llm,
            message=message,
            conversation=conversation,
            intent=intent,
        )
        await _record_step(
            {
                "step": 2,
                "thought": "对话模式，直接整理 Markdown",
                "action": "compose_notes",
                "observation": f"已生成 {len(payload['markdown'])} 字笔记",
                "status": "done",
            }
        )
        return {
            "payload": payload,
            "intent": intent,
            "react_steps": react_steps,
            "trace": trace_fn("对话模式生成结构化笔记"),
        }

    process: dict[str, Any] | None = None
    observations: list[str] = [f"意图：material，{intent.get('rationale', '')}"]
    notes_composed = False
    payload: dict[str, Any] | None = None
    catalog_cache: dict[str, Any] | None = None

    try:
        catalog_cache = await invoke_tool(
            "course-catalog-list",
            agent_context={**context, "course_id": course_id},
        )
        chapters = catalog_cache.get("chapters") or []
        if not intent.get("chapter_key") and chapters:
            hint = _match_chapter_from_hint(intent, message, chapters)
            if hint:
                intent["chapter_key"] = hint
        observations.append(
            "预加载目录 → "
            + _format_catalog_observation(
                catalog_cache,
                chapter_key=str(intent.get("chapter_key") or ""),
            )[:800]
        )
    except Exception as exc:
        observations.append(f"预加载目录失败：{exc}")

    format_doc = ""
    try:
        from app.skills.loader import get_skill_loader

        format_doc = get_skill_loader().load_doc("tutorial-to-notes", "format")
    except Exception:
        format_doc = "要点式 Markdown，每条概念后跟 例："

    for step_idx in range(2, MAX_NOTE_REACT_STEPS + 1):
        await _record_step(
            {
                "step": step_idx,
                "thought": "",
                "action": "plan_next",
                "observation": "规划下一步…",
                "status": "running",
            }
        )
        prompt = build_react_prompt(
            intent=intent,
            message=message,
            observations=observations,
            process_summary=process.get("summary", "") if process else "",
            conversation=conversation,
        )
        raw = await llm.complete(prompt, system=NOTE_REACT_SYSTEM)
        action = parse_react_action(raw)
        if not action:
            raw = await llm.complete(prompt + "\n\n输出无效，请严格 JSON。", system=NOTE_REACT_SYSTEM)
            action = parse_react_action(raw)
        if not action:
            observations.append("格式错误，跳过本轮")
            continue

        thought = str(action.get("thought") or "")[:200]
        action_name = str(action.get("action") or "").strip().lower()
        obs = ""

        await _record_step(
            {
                "step": step_idx,
                "thought": thought,
                "action": action_name,
                "observation": "执行中…",
                "status": "running",
            }
        )

        if action_name == "list_catalog":
            try:
                if catalog_cache is None:
                    catalog_cache = await invoke_tool(
                        "course-catalog-list",
                        agent_context={**context, "course_id": course_id},
                    )
                    chapters = catalog_cache.get("chapters") or []
                    if not intent.get("chapter_key") and chapters:
                        hint = _match_chapter_from_hint(intent, message, chapters)
                        if hint:
                            intent["chapter_key"] = hint
                obs = _format_catalog_observation(
                    catalog_cache or {},
                    chapter_key=str(intent.get("chapter_key") or ""),
                )
                if intent.get("chapter_key"):
                    obs += f"；下一步请 extract_material，chapter_key={intent['chapter_key']}"
                elif catalog_cache is not None:
                    obs += "；请根据目录中的 chapter_key 调用 extract_material"
            except Exception as exc:
                obs = f"目录失败：{exc}"

        elif action_name == "extract_material":
            kwargs: dict[str, Any] = {}
            ck = str(action.get("chapter_key") or intent.get("chapter_key") or "").strip()
            mid = str(action.get("material_id") or intent.get("material_id") or "").strip()
            if mid:
                kwargs["material_id"] = mid
            elif ck:
                kwargs["chapter_key"] = ck
            else:
                obs = "请指定 chapter_key 或 material_id，可先 list_catalog"
            if kwargs:
                try:
                    process = await invoke_tool(
                        "note-material-extract",
                        agent_context={**context, "course_id": course_id},
                        **kwargs,
                    )
                    obs = process.get("summary", "提取完成")
                except Exception as exc:
                    obs = f"提取失败：{exc}"

        elif action_name == "vision_analyze":
            if not process:
                obs = "请先 extract_material"
            else:
                pending = [
                    (page, img)
                    for page in process.get("pages") or []
                    for img in (page.get("images") or [])
                    if img.get("status") == "待理解"
                ]
                if not pending:
                    obs = "无待理解图片"
                else:
                    analyzed = 0
                    for page, img in pending[:8]:
                        try:
                            result = await invoke_tool(
                                "doubao-vision-analyze",
                                image_path=img["path"],
                                page_text=str(page.get("text") or ""),
                            )
                            if result.get("ok") and result.get("analysis"):
                                apply_vision_to_process(process["pages"], img["id"], result["analysis"])
                                analyzed += 1
                        except Exception:
                            img["status"] = "跳过（视觉失败）"
                    process["pending_images"] = sum(
                        1
                        for p in process.get("pages") or []
                        for i in (p.get("images") or [])
                        if i.get("status") == "待理解"
                    )
                    obs = f"已分析 {analyzed}/{len(pending)} 张图"

        elif action_name == "analyze_structure":
            if not process:
                obs = "请先 extract_material"
            else:
                try:
                    struct = await invoke_tool("note-structure-analyze", pages=process.get("pages") or [])
                    process["structure_report"] = struct.get("report", "")
                    obs = f"识别 {struct.get('section_count', 0)} 个大节、{struct.get('subsection_count', 0)} 个小节"
                except Exception as exc:
                    obs = f"结构分析失败：{exc}"

        elif action_name == "compose_notes":
            if not process:
                obs = "请先 extract_material"
            else:
                blob = serialize_process_for_llm(process)
                mat_prompt = build_material_note_prompt(
                    message=message,
                    conversation=conversation,
                    intent=intent,
                    process_blob=blob,
                    format_doc=format_doc,
                    image_catalog=build_image_catalog_from_process(process),
                )
                raw_note = await llm.complete(mat_prompt, system=MATERIAL_NOTE_SYSTEM)
                payload = parse_note_output(
                    raw_note,
                    fallback_title=str(intent.get("title_hint") or "学习笔记"),
                    fallback_topic=str(intent.get("topic") or message[:40]),
                )
                notes_composed = True
                obs = f"已生成《{payload['title']}》共 {len(payload['markdown'])} 字"

        elif action_name == "finish":
            if payload:
                obs = "完成"
                await _record_step(
                    {"step": step_idx, "thought": thought, "action": action_name, "observation": obs, "status": "done"}
                )
                break
            obs = "尚未 compose_notes，请先 compose_notes"

        await _record_step(
            {"step": step_idx, "thought": thought, "action": action_name, "observation": obs, "status": "done"}
        )
        observations.append(f"{action_name} → {obs}")

        if notes_composed and action_name in ("compose_notes", "finish"):
            break

    if not payload and process:
        blob = serialize_process_for_llm(process)
        raw_note = await llm.complete(
            build_material_note_prompt(
                message=message,
                conversation=conversation,
                intent=intent,
                process_blob=blob,
                format_doc=format_doc,
                image_catalog=build_image_catalog_from_process(process),
            ),
            system=MATERIAL_NOTE_SYSTEM,
        )
        payload = parse_note_output(
            raw_note,
            fallback_title=str(intent.get("title_hint") or "学习笔记"),
            fallback_topic=str(intent.get("topic") or message[:40]),
        )
        await _record_step(
            {
                "step": len(react_steps) + 1,
                "thought": "轮次用尽，强制生成",
                "action": "compose_notes",
                "observation": "fallback compose",
            }
        )

    if not payload:
        payload = await _compose_conversation_notes(
            llm=llm,
            message=message,
            conversation=conversation,
            intent=intent,
        )

    context["note_process"] = process
    context["note_intent"] = intent
    return {
        "payload": payload,
        "intent": intent,
        "react_steps": react_steps,
        "trace": trace_fn(
            f"{'资料' if intent['mode'] == 'material' else '对话'}模式生成《{payload['title']}》"
        ),
    }


async def _compose_conversation_notes(
    *,
    llm: LLMProvider,
    message: str,
    conversation: list[dict[str, Any]],
    intent: dict[str, Any],
) -> dict[str, Any]:
    prompt = build_conversation_note_prompt(message=message, conversation=conversation, intent=intent)
    raw = await llm.complete(prompt, system=CONVERSATION_NOTE_SYSTEM)
    return parse_note_output(
        raw,
        fallback_title=str(intent.get("title_hint") or "对话笔记"),
        fallback_topic=str(intent.get("topic") or message[:40]),
    )


def _format_catalog_observation(result: dict[str, Any], *, chapter_key: str = "") -> str:
    lines = [str(result.get("summary") or "目录加载完成")]
    for ch in result.get("chapters") or []:
        key = str(ch.get("chapter_key") or "")
        title = str(ch.get("chapter_title") or key)
        count = ch.get("material_count", 0)
        marker = " ← 目标章节" if chapter_key and key == chapter_key else ""
        lines.append(f"  {key}: {title}（{count} 个文件）{marker}")
    return "\n".join(lines)[:2400]


def _topic_needles(intent: dict[str, Any], message: str) -> list[str]:
    blob = f"{message} {intent.get('topic', '')} {intent.get('title_hint', '')}"
    blob = re.sub(r"[，。；、？！,.;!?]", " ", blob)
    needles: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"[\u4e00-\u9fff]{2,}", blob):
        for piece in (raw, raw.replace("章节", "").replace("笔记", "").strip()):
            if len(piece) >= 2 and piece not in seen:
                seen.add(piece)
                needles.append(piece)
    needles.sort(key=len, reverse=True)
    return needles


def _match_chapter_from_hint(intent: dict[str, Any], message: str, chapters: list[dict[str, Any]]) -> str:
    blob = f"{message} {intent.get('topic', '')} {intent.get('course_hint', '')} {intent.get('title_hint', '')}"
    m = re.search(r"第\s*(\d+)\s*章", blob)
    if m:
        key = f"ch{m.group(1)}"
        if any(c.get("chapter_key") == key for c in chapters):
            return key

    for ch in chapters:
        title = str(ch.get("chapter_title") or "")
        if title and title in blob:
            return str(ch.get("chapter_key") or "")

    best_key = ""
    best_score = 0
    for ch in chapters:
        title = str(ch.get("chapter_title") or "")
        title_core = re.sub(r"^第\s*\d+\s*章\s*", "", title).strip()
        for needle in _topic_needles(intent, message):
            if needle in title or needle in title_core or title_core in needle:
                score = len(needle)
                if score > best_score:
                    best_score = score
                    best_key = str(ch.get("chapter_key") or "")
    return best_key
