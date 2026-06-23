"""Normalize Mermaid mindmap source for frontend rendering."""

from __future__ import annotations

import re


def normalize_mindmap(source: str, *, root_label: str | None = None) -> str:
    text = source.strip()
    text = re.sub(r"^```(?:mermaid)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    if not text.lower().startswith("mindmap"):
        label = root_label or "主题"
        text = f"mindmap\n  root(({label}))\n{text}"
    lines = [line.rstrip() for line in text.splitlines()]
    if not lines:
        label = root_label or "主题"
        return f"mindmap\n  root(({label}))"
    return "\n".join(lines)
