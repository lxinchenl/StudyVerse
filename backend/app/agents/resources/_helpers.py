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


def session_dialogue_basis(context: dict[str, Any]) -> str:
    dialogue = context.get("expert_dialogue") or []
    lines: list[str] = []
    for row in dialogue:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        role = "用户" if row.get("role") == "user" else "助手"
        time = f"[{row.get('time')}] " if row.get("time") else ""
        lines.append(f"{time}{role}: {content}")
    return "\n".join(lines)


def explicit_memory_basis(context: dict[str, Any]) -> str:
    memory = context.get("explicit_memory") or []
    lines: list[str] = []
    for item in memory:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"- [{item.get('type', 'memory')}] {content}")
    return "\n".join(lines)


def append_session_dialogue_basis(basis: str, context: dict[str, Any]) -> str:
    memory = explicit_memory_basis(context)
    dialogue = session_dialogue_basis(context)
    blocks: list[str] = []
    if memory:
        blocks.append(f"显式长期记忆 memory：\n{memory}")
    if dialogue:
        blocks.append(f"近期会话上下文（近 3 轮，仅用户发言和助手最终回复）：\n{dialogue}")
    extra = "\n\n".join(blocks)
    if not extra:
        return basis
    if not basis.strip():
        return extra
    return f"{basis}\n\n{extra}"
