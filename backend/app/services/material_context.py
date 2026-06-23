"""Unified course material basis: vector retrieval, document read, or stored memory."""

from __future__ import annotations

from typing import Any

from app.interfaces.contracts import MemoryService

RESOURCE_EXPERTS = frozenset(
    {"mindmap-agent", "video-agent", "note-agent", "code-lab-agent"}
)


def expert_requires_material(expert_name: str, step: dict[str, Any] | None = None) -> bool:
    if expert_name in RESOURCE_EXPERTS:
        return True
    if expert_name == "exercise-agent":
        block = (step or {}).get("exercise") if isinstance((step or {}).get("exercise"), dict) else {}
        mode = str(block.get("mode") or "search").strip().lower()
        return mode == "generate"
    if expert_name == "code-lab-agent":
        block = (step or {}).get("code_lab") if isinstance((step or {}).get("code_lab"), dict) else {}
        mode = str(block.get("mode") or "search").strip().lower()
        return mode == "generate"
    return False


def chunk_count(context: dict[str, Any]) -> int:
    return len((context.get("retrieval") or {}).get("chunks") or [])


def has_material_basis(context: dict[str, Any], memory: MemoryService | None = None) -> bool:
    if chunk_count(context) > 0:
        return True
    if memory is None:
        return False
    stored = memory.get_stored_material_context(context.get("user_id", ""))
    return bool(stored and stored.get("chunks"))


def preload_material_context(context: dict[str, Any], memory: MemoryService) -> None:
    if chunk_count(context) > 0:
        return
    stored = memory.get_stored_material_context(context["user_id"])
    if stored and stored.get("chunks"):
        context["retrieval"] = stored
        context["material_from_memory"] = True


def ensure_material_basis(context: dict[str, Any], memory: MemoryService) -> tuple[bool, str]:
    if chunk_count(context) > 0:
        return True, ""
    stored = memory.get_stored_material_context(context["user_id"])
    if stored and stored.get("chunks"):
        context["retrieval"] = stored
        context["material_from_memory"] = True
        n = len(stored["chunks"])
        return True, f"已复用短期记忆中的 {n} 条课程资料"
    return (
        False,
        "须先获取课程资料：call_expert retrieval-agent（点状检索）或 call_tool course-document-read（按章/文件阅读）；"
        "也可使用本轮已获取的资料。",
    )


def apply_document_read(context: dict[str, Any], result: dict[str, Any]) -> None:
    chunks = result.get("chunks") or []
    if not chunks:
        return
    retrieval = context.setdefault("retrieval", {})
    existing = list(retrieval.get("chunks") or [])
    seen = {str(c.get("chunk_id")) for c in existing if c.get("chunk_id")}
    for chunk in chunks:
        cid = str(chunk.get("chunk_id") or "")
        if cid and cid in seen:
            continue
        existing.append(chunk)
        if cid:
            seen.add(cid)
    retrieval["chunks"] = existing
    types = set(retrieval.get("source_types") or [])
    types.add("document_read")
    retrieval["source_types"] = sorted(types)
    if result.get("queries"):
        retrieval["queries"] = result["queries"]
    if result.get("entities"):
        retrieval["entities"] = result["entities"]


def material_basis_summary(context: dict[str, Any], memory: MemoryService | None = None) -> str:
    n = chunk_count(context)
    if n:
        src = (context.get("retrieval") or {}).get("source_types") or []
        from_mem = "（含短期记忆复用）" if context.get("material_from_memory") else ""
        return f"当前已有课程资料 {n} 条，来源={','.join(src) or 'unknown'}{from_mem}。"
    if memory and has_material_basis(context, memory):
        return "短期记忆中存在上一轮课程资料，调用资源专家时将自动复用。"
    return "当前尚无课程资料；生成资源前须先检索或阅读文档。"
