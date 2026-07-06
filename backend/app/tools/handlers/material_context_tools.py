from __future__ import annotations

from typing import Any


def clear_loaded_material_context(*, retrieval: dict[str, Any] | None = None) -> dict[str, Any]:
    """Clear in-memory loaded materials for the current ReAct round."""
    previous = len((retrieval or {}).get("chunks") or [])
    if isinstance(retrieval, dict):
        retrieval.clear()
    return {
        "ok": True,
        "cleared_chunks": previous,
        "summary": f"已清空当前上下文中的课程资料（{previous} 条）",
    }
