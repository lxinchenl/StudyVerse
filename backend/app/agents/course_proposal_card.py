"""Structured course proposal card for chat confirmation UI."""

from __future__ import annotations

from typing import Any


def build_proposal_card(
    proposal: dict[str, Any],
    topic: str,
    *,
    status: str = "pending",
) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    for idx, mod in enumerate(proposal.get("modules") or [], start=1):
        if not isinstance(mod, dict):
            continue
        modules.append(
            {
                "id": str(mod.get("id") or f"mod-{idx}"),
                "title": str(mod.get("title") or f"第{idx}讲").strip(),
                "objective": str(mod.get("objective") or "").strip(),
                "chapter_key": str(mod.get("chapter_key") or "").strip(),
                "estimated_minutes": int(mod.get("estimated_minutes") or 45),
                "topics": [str(t).strip() for t in (mod.get("topics") or []) if str(t).strip()],
            }
        )
    return {
        "kind": "course_proposal",
        "status": status,
        "topic": str(topic or proposal.get("topic") or "").strip(),
        "course_title": str(proposal.get("course_title") or "定制系统课").strip(),
        "summary": str(proposal.get("summary") or "").strip(),
        "modules": modules,
    }


def normalize_client_proposal(raw: dict[str, Any] | None, *, fallback_topic: str = "") -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"course_title": "定制系统课", "summary": "", "topic": fallback_topic, "modules": []}
    modules: list[dict[str, Any]] = []
    for idx, mod in enumerate(raw.get("modules") or [], start=1):
        if not isinstance(mod, dict):
            continue
        modules.append(
            {
                "id": str(mod.get("id") or f"mod-{idx}"),
                "title": str(mod.get("title") or f"第{idx}讲").strip(),
                "objective": str(mod.get("objective") or "掌握本讲核心内容").strip(),
                "chapter_key": str(mod.get("chapter_key") or mod.get("chapterKey") or "").strip(),
                "estimated_minutes": int(mod.get("estimated_minutes") or mod.get("estimatedMinutes") or 45),
                "topics": [str(t).strip() for t in (mod.get("topics") or []) if str(t).strip()],
                "status": "pending",
                "resources": [],
            }
        )
    topic = str(raw.get("topic") or fallback_topic or "").strip()
    return {
        "course_title": str(raw.get("course_title") or raw.get("courseTitle") or "定制系统课").strip(),
        "summary": str(raw.get("summary") or "").strip(),
        "topic": topic,
        "modules": modules,
    }


def proposal_card_reply(card: dict[str, Any]) -> str:
    title = str(card.get("course_title") or "定制系统课")
    count = len(card.get("modules") or [])
    return (
        f"已为你编排《{title}》（共 {count} 讲）。"
        f"请在下方卡片中查看、编辑大纲，确认后将按讲次自动生成资源并同步到学习路径。"
    )
