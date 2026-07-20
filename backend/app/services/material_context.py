"""Unified course material basis: vector retrieval, document read, or stored memory."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.interfaces.contracts import LLMProvider, MemoryService
from app.services.material_summary_agent import MaterialSummaryAgent

RESOURCE_EXPERTS = frozenset(
    {"mindmap-agent", "video-agent", "note-agent", "code-lab-agent"}
)
MAX_SEARCH_CHUNKS = 6
MAX_DOCUMENT_CHUNKS = 6
MAX_MATERIAL_CHARS = 10000
SUMMARY_TARGET_CHARS = 5000


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


def _chunk_text_len(chunk: dict[str, Any]) -> int:
    return len(str(chunk.get("text") or ""))


def _materials_char_count(retrieval: dict[str, Any]) -> int:
    return sum(_chunk_text_len(c) for c in (retrieval.get("chunks") or []) if isinstance(c, dict))


def _source_type(chunk: dict[str, Any]) -> str:
    source_type = str(chunk.get("source_type") or "").strip()
    if source_type:
        return source_type
    source = str(chunk.get("source") or "").lower()
    if "chapter" in source or "course" in source:
        return "course_material"
    return "course_material"


def _split_buckets(retrieval: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    document_chunks = list(retrieval.get("document_chunks") or [])
    search_chunks = list(retrieval.get("search_chunks") or [])
    if document_chunks or search_chunks:
        return document_chunks, search_chunks

    for chunk in retrieval.get("chunks") or []:
        if not isinstance(chunk, dict):
            continue
        source_type = _source_type(chunk)
        if source_type == "document_read":
            document_chunks.append(chunk)
        elif source_type.startswith("material_summary"):
            # 已摘要场景，保留在 search 桶避免丢失可回答依据。
            search_chunks.append(chunk)
        else:
            search_chunks.append(chunk)
    return document_chunks, search_chunks


def _dedupe_chunks(chunks: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        cid = str(chunk.get("chunk_id") or "")
        if cid and cid in seen_ids:
            continue
        if cid:
            seen_ids.add(cid)
        deduped.append(chunk)
    return deduped[-limit:] if limit > 0 else deduped


def _rebuild_retrieval(retrieval: dict[str, Any]) -> None:
    document_chunks, search_chunks = _split_buckets(retrieval)
    retrieval["document_chunks"] = _dedupe_chunks(document_chunks, MAX_DOCUMENT_CHUNKS)
    retrieval["search_chunks"] = _dedupe_chunks(search_chunks, MAX_SEARCH_CHUNKS)

    combined = list(retrieval["search_chunks"]) + list(retrieval["document_chunks"])
    retrieval["chunks"] = combined

    source_types = {_source_type(c) for c in combined if isinstance(c, dict)}
    retrieval["source_types"] = sorted(source_types)
    retrieval["merge_boundary"] = {
        "search_chunks": len(retrieval["search_chunks"]),
        "document_chunks": len(retrieval["document_chunks"]),
        "max_search_chunks": MAX_SEARCH_CHUNKS,
        "max_document_chunks": MAX_DOCUMENT_CHUNKS,
    }


def merge_retrieval_search_result(context: dict[str, Any], result: dict[str, Any]) -> None:
    retrieval = context.setdefault("retrieval", {})
    retrieval.update({k: v for k, v in result.items() if k != "chunks"})
    retrieval["search_chunks"] = list(result.get("chunks") or [])
    _rebuild_retrieval(retrieval)


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
        _rebuild_retrieval(context["retrieval"])
        context["material_from_memory"] = True


def ensure_material_basis(context: dict[str, Any], memory: MemoryService) -> tuple[bool, str]:
    if chunk_count(context) > 0:
        return True, ""
    stored = memory.get_stored_material_context(context["user_id"])
    if stored and stored.get("chunks"):
        context["retrieval"] = stored
        _rebuild_retrieval(context["retrieval"])
        context["material_from_memory"] = True
        n = len((context.get("retrieval") or {}).get("chunks") or [])
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
    normalized = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        row = dict(chunk)
        row["source_type"] = "document_read"
        normalized.append(row)
    retrieval["document_chunks"] = list(retrieval.get("document_chunks") or []) + normalized
    if result.get("queries"):
        retrieval["queries"] = result["queries"]
    if result.get("entities"):
        retrieval["entities"] = result["entities"]
    _rebuild_retrieval(retrieval)


async def maybe_summarize_materials(
    context: dict[str, Any],
    llm: LLMProvider,
    *,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> bool:
    retrieval = context.get("retrieval")
    if not isinstance(retrieval, dict):
        return False
    _rebuild_retrieval(retrieval)
    total_chars = _materials_char_count(retrieval)
    if total_chars <= MAX_MATERIAL_CHARS:
        return False

    document_chunks = list(retrieval.get("document_chunks") or [])
    search_chunks = list(retrieval.get("search_chunks") or [])
    doc_chars = sum(_chunk_text_len(c) for c in document_chunks)
    search_chars = sum(_chunk_text_len(c) for c in search_chunks)
    if doc_chars + search_chars <= 0:
        return False

    if doc_chars + search_chars <= SUMMARY_TARGET_CHARS:
        doc_budget = doc_chars or 0
        search_budget = search_chars or 0
    else:
        doc_budget = max(0, int(SUMMARY_TARGET_CHARS * doc_chars / (doc_chars + search_chars)))
        search_budget = SUMMARY_TARGET_CHARS - doc_budget

    n_chunks = len(document_chunks) + len(search_chunks)
    if on_progress:
        await on_progress(
            f"资料约 {total_chars} 字（{n_chunks} 条），正在并行摘要到约 {SUMMARY_TARGET_CHARS} 字…"
        )

    summary_agent = MaterialSummaryAgent(llm)
    jobs = []
    if document_chunks and doc_budget > 0:
        jobs.append(("document_chunks", document_chunks, doc_budget))
    if search_chunks and search_budget > 0:
        jobs.append(("search_chunks", search_chunks, search_budget))

    compressed = await asyncio.gather(
        *[
            summary_agent.compress_chunks(chunks, max_total_chars=budget)
            for _, chunks, budget in jobs
        ]
    )
    for (key, _, _), rows in zip(jobs, compressed):
        retrieval[key] = rows

    _rebuild_retrieval(retrieval)
    retrieval["summarized"] = {
        "trigger_chars": total_chars,
        "target_chars": SUMMARY_TARGET_CHARS,
        "agent": MaterialSummaryAgent.name,
        "mode": "per_chunk_parallel",
        "chunk_count": len(retrieval.get("chunks") or []),
    }
    return True


def clear_material_context(context: dict[str, Any]) -> int:
    retrieval = context.get("retrieval")
    prev = len((retrieval or {}).get("chunks") or []) if isinstance(retrieval, dict) else 0
    context.pop("retrieval", None)
    context.pop("material_from_memory", None)
    return prev


def material_basis_summary(context: dict[str, Any], memory: MemoryService | None = None) -> str:
    n = chunk_count(context)
    if n:
        retrieval = context.get("retrieval") or {}
        src = retrieval.get("source_types") or []
        from_mem = "（含短期记忆复用）" if context.get("material_from_memory") else ""
        boundary = retrieval.get("merge_boundary") or {}
        boundary_desc = ""
        if boundary:
            boundary_desc = (
                f"；分桶(search={boundary.get('search_chunks', 0)}/{boundary.get('max_search_chunks', MAX_SEARCH_CHUNKS)}, "
                f"document={boundary.get('document_chunks', 0)}/{boundary.get('max_document_chunks', MAX_DOCUMENT_CHUNKS)})"
            )
        return f"当前已有课程资料 {n} 条，来源={','.join(src) or 'unknown'}{from_mem}{boundary_desc}。"
    if memory and has_material_basis(context, memory):
        return "短期记忆中存在上一轮课程资料，调用资源专家时将自动复用。"
    return "当前尚无课程资料；生成资源前须先检索或阅读文档。"
