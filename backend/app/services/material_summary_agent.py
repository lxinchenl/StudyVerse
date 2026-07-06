from __future__ import annotations

from typing import Any

from app.interfaces.contracts import LLMProvider

_PER_CHUNK_SUMMARY_SYSTEM = """你是资料摘要 Agent。将单条课程资料压缩为可用于问答的摘要。
要求：
1) 仅保留事实、定义、规则、示例，不要扩写
2) 只输出摘要正文，不要 JSON、不要 markdown 标题
3) 严格控制在指定字数以内
"""


class MaterialSummaryAgent:
    """Compress each material chunk in place while preserving bucket boundaries."""

    name = "material-summary-agent"
    role = "资料摘要 Agent"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def compress_one(self, chunk: dict[str, Any], max_chars: int) -> dict[str, Any]:
        text = str(chunk.get("text") or "").strip()
        if not text or len(text) <= max_chars:
            return dict(chunk)

        title = str(chunk.get("title") or chunk.get("chunk_id") or "资料")
        prompt = (
            f"资料标题：{title}\n\n"
            f"资料正文：\n{text[:14000]}\n\n"
            f"请压缩到不超过 {max_chars} 个中文字符。"
        )
        raw = (await self.llm.complete(prompt, system=_PER_CHUNK_SUMMARY_SYSTEM)).strip()
        if not raw:
            raw = text[:max_chars]

        out = dict(chunk)
        out["text"] = raw[:max_chars]
        source_type = str(chunk.get("source_type") or "course_material").strip()
        if source_type == "document_read":
            out["source_type"] = "material_summary_document_read"
        elif source_type.startswith("material_summary"):
            out["source_type"] = source_type
        else:
            out["source_type"] = "material_summary_search"
        return out

    async def compress_chunks(
        self,
        chunks: list[dict[str, Any]],
        *,
        max_total_chars: int,
    ) -> list[dict[str, Any]]:
        if not chunks:
            return []

        weights = [max(1, len(str(chunk.get("text") or ""))) for chunk in chunks]
        weight_sum = sum(weights)
        compressed: list[dict[str, Any]] = []

        for chunk, weight in zip(chunks, weights):
            share = max(120, int(max_total_chars * weight / weight_sum))
            compressed.append(await self.compress_one(chunk, share))

        return compressed
