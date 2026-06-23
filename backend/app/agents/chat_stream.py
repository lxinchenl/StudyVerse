"""Serialize chat stream events for SSE."""

from __future__ import annotations

from typing import Any


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


def pack_progress_event(context: dict[str, Any]) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "progress",
        "react_steps": [serialize_react_step(s) for s in context.get("react_steps") or []],
        "traces": list(context.get("traces") or []),
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
