"""Stream expert-internal ReAct steps into Resource Studio MsgHub + SSE."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

NOTE_STEP_LABELS: dict[str, str] = {
    "analyze_intent": "分析笔记意图",
    "list_catalog": "查看章节目录",
    "extract_material": "提取课件资料",
    "vision_analyze": "豆包视觉识图",
    "analyze_structure": "分析章节结构",
    "compose_notes": "撰写 Markdown 笔记",
    "finish": "完成笔记生成",
    "plan_next": "规划下一步",
}

COURSE_STEP_LABELS: dict[str, str] = {
    "plan_course": "编排课程大纲",
    "module_react": "讲次自主编排",
    "generate_resource": "按序生成资源",
    "finish_module": "完成本讲编排",
    "orchestrate_module": "LLM 编排本讲资源",
    "save_path": "同步学习路径",
    "plan_next": "规划下一步",
}


def _step_action_key(step: dict[str, Any]) -> str:
    action = str(step.get("action") or "").strip()
    if action.startswith("note:"):
        return action[5:]
    if action.startswith("course:"):
        return action[7:]
    return action


def format_agent_step_message(step: dict[str, Any]) -> str:
    key = _step_action_key(step)
    action = str(step.get("action") or "")
    if action.startswith("course:"):
        label = COURSE_STEP_LABELS.get(key, key or "执行步骤")
    elif action.startswith("note:"):
        label = NOTE_STEP_LABELS.get(key, key or "执行步骤")
    else:
        label = NOTE_STEP_LABELS.get(key, COURSE_STEP_LABELS.get(key, key or "执行步骤"))
    status = str(step.get("status") or "done")
    obs = str(step.get("observation") or "").strip()
    if status == "running":
        return f"▸ {label}…"
    if obs and obs not in ("执行中…", "…"):
        return f"▸ {label} — {obs[:200]}"
    return f"▸ {label}"


def make_studio_agent_sink(
    *,
    agent_id: str,
    emit: EventSink,
    hub: Callable[..., Awaitable[None]],
    ts_fn: Callable[[], str],
) -> EventSink:
    """Wrap chat progress events as studio hub messages + agent_progress SSE."""

    last_emitted: dict[int, tuple[str, str]] = {}

    async def sink(event: dict[str, Any]) -> None:
        if event.get("type") != "progress":
            await emit(event)
            return

        steps = event.get("react_steps") or []
        agent_steps = [
            s
            for s in steps
            if s.get("expert") == agent_id
            or str(s.get("action", "")).startswith("note:")
            or str(s.get("action", "")).startswith("course:")
        ]
        if not agent_steps:
            agent_steps = steps

        await emit(
            {
                "type": "agent_progress",
                "agent_id": agent_id,
                "react_steps": agent_steps,
            }
        )

        for step in agent_steps:
            step_num = int(step.get("step") or 0)
            status = str(step.get("status") or "done")
            obs = str(step.get("observation") or "")
            signature = (status, obs)
            if last_emitted.get(step_num) == signature:
                continue
            last_emitted[step_num] = signature
            await hub(
                emit,
                agent_id,
                format_agent_step_message(step),
                ts_fn(),
                kind="progress",
            )

    return sink
