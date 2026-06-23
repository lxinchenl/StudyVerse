"""Tool handler: propose a course outline without generating resources."""

from __future__ import annotations

from typing import Any


async def course_workflow_propose(*, user_id: str, topic: str, course_id: str = "db-principles") -> dict[str, Any]:
    from app.agents.course_proposal_card import build_proposal_card
    from app.core.dependencies import get_llm_provider, get_memory_service
    from app.agents.course_workflow_agent import propose_course_plan

    plan = await propose_course_plan(
        llm=get_llm_provider(),
        memory=get_memory_service(),
        user_id=user_id,
        topic=topic.strip(),
        course_id=course_id.strip() or "db-principles",
    )
    modules = plan.get("modules") or []
    lines = [f"《{plan.get('course_title')}》— {plan.get('summary', '')}"]
    for i, mod in enumerate(modules, start=1):
        lines.append(f"{i}. {mod.get('title')}（约{mod.get('estimated_minutes')}分钟）— {mod.get('objective')}")
    lines.append("确认后将按讲次由编排 Agent 自主决定资源类型、数量与学习顺序")
    return {
        "ok": True,
        "proposal": plan,
        "card": build_proposal_card(plan, topic.strip()),
        "summary": "\n".join(lines),
        "ask_user": "请在对话卡片上确认、编辑或取消；用户点击同意后系统将自动执行 course-workflow。",
    }
