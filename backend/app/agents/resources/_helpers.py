from typing import Any


def retrieval_basis(context: dict[str, Any], *, max_chars: int = 500) -> str:
    chunks = context.get("retrieval", {}).get("chunks", [])
    if not chunks:
        return ""
    parts: list[str] = []
    remaining = max_chars
    for i, chunk in enumerate(chunks, 1):
        text = (chunk.get("text") or "").strip()
        if not text or remaining <= 0:
            continue
        title = chunk.get("title") or f"资料{i}"
        snippet = text[:remaining]
        parts.append(f"【{title}】\n{snippet}")
        remaining -= len(snippet)
    return "\n\n".join(parts)
