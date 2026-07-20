"""Normalize Mermaid mindmap source for frontend rendering.

LLM-generated mindmaps often include characters that Mermaid 11 rejects
(parentheses, arrows, Greek letters, etc.). This module sanitizes labels so
the frontend does not show "Syntax error in text".
"""

from __future__ import annotations

import re

# Characters that commonly break Mermaid mindmap node parsing when unquoted.
_NEEDS_QUOTE = re.compile(
    r"""[()\[\]{}<>|&;@\\/#`"'→←⇒⇐↔θΘαβγδμσλ·•…—–]|^\d|[:：]|vs\.?""",
    re.IGNORECASE,
)

_ROOT_PATTERNS = (
    re.compile(r"^(\s*)root\(\((.*)\)\)\s*$"),
    re.compile(r"^(\s*)root\[(.*)\]\s*$"),
    re.compile(r"^(\s*)root\((.*)\)\s*$"),
)


def _quote_label(label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return '""'
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text
    # Prefer single quotes inside to avoid breaking the outer quotes.
    escaped = text.replace('"', "'").replace("\n", " ").strip()
    if _NEEDS_QUOTE.search(escaped) or " " in escaped:
        return f'"{escaped}"'
    return escaped


def _sanitize_root_line(indent: str, inner: str, style: str) -> str:
    safe = str(inner or "").strip().replace('"', "'").replace("\n", " ")
    if style == "round":
        # root((label)) — avoid nested )) by stripping them from label
        safe = safe.replace("))", ").").replace("((", "(")
        return f"{indent}root(({safe}))"
    if style == "square":
        safe = safe.replace("]", "").replace("[", "")
        return f"{indent}root[{safe}]"
    safe = safe.replace(")", "").replace("(", "")
    return f"{indent}root({safe})"


def _sanitize_line(line: str) -> str | None:
    raw = line.rstrip()
    if not raw.strip():
        return None
    # Keep the diagram header
    if raw.strip().lower() == "mindmap":
        return "mindmap"

    m = re.match(r"^(\s*)(.*)$", raw)
    if not m:
        return None
    indent, body = m.group(1), m.group(2).strip()
    # Normalize tabs → 2 spaces; keep relative depth via leading whitespace length.
    if "\t" in indent:
        indent = indent.replace("\t", "  ")
    # Clamp odd indent to even spaces (Mermaid mindmap expects 2-space steps).
    spaces = len(indent.replace("\t", "  "))
    if spaces % 2 == 1:
        spaces += 1
    indent = " " * spaces

    for pattern, style in zip(_ROOT_PATTERNS, ("round", "square", "paren")):
        root_match = pattern.match(f"{indent}{body}")
        if root_match:
            return _sanitize_root_line(indent, root_match.group(2), style)

    # Already a shaped node: id((text)) / id[text] / id(text)
    shaped = re.match(r"^([A-Za-z_][\w-]*)(\(\(.*\)\)|\[.*\]|\(.*\))$", body)
    if shaped:
        return f"{indent}{body}"

    return f"{indent}{_quote_label(body)}"


def normalize_mindmap(source: str, *, root_label: str | None = None) -> str:
    text = (source or "").strip()
    text = re.sub(r"^```(?:mermaid)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    if not text.lower().startswith("mindmap"):
        label = (root_label or "主题").strip() or "主题"
        text = f"mindmap\n  root(({label}))\n{text}"

    out: list[str] = []
    for line in text.splitlines():
        sanitized = _sanitize_line(line)
        if sanitized is not None:
            out.append(sanitized)

    if not out or out[0].strip().lower() != "mindmap":
        label = (root_label or "主题").strip() or "主题"
        return f"mindmap\n  root(({label}))"

    # Ensure there is at least a root node
    if len(out) == 1:
        label = (root_label or "主题").strip() or "主题"
        out.append(f"  root(({label}))")

    return "\n".join(out)
