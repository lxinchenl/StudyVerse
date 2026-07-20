"""Shared prompt fragments for main-agent ReAct and context preview."""

from __future__ import annotations

import json
from typing import Any


def format_me_block(me: Any) -> str:
    if isinstance(me, dict) and me:
        return "【助手人设 me】\n" + json.dumps(me, ensure_ascii=False, indent=2)
    text = str(me or "").strip()
    return f"【助手人设 me】\n{text}" if text else ""


def compose_llm_prompt_preview(*, system_text: str, user_prompt_text: str) -> str:
    parts: list[str] = []
    if system_text.strip():
        parts.append("=== System ===")
        parts.append(system_text.strip())
    if user_prompt_text.strip():
        parts.append("=== User ===")
        parts.append(user_prompt_text.strip())
    return "\n\n".join(parts)
