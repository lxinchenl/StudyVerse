from typing import Any

from app.interfaces.contracts import ChunkRepository, Retriever


class RetrievalAgentPipeline(Retriever):
    """Fixed retrieval pipeline: normalize -> filter -> vector-like keyword -> merge -> pack."""

    def __init__(self, chunk_repo: ChunkRepository):
        self.chunk_repo = chunk_repo

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        course_id: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        query_terms = {t for t in query.lower().replace("，", " ").split() if len(t) > 1}
        chunks = self.chunk_repo.list_chunks()
        if course_id:
            chunks = [c for c in chunks if c.get("course_id") == course_id]
        if document_id:
            chunks = [c for c in chunks if c.get("chunk_id") == document_id or c.get("doc_id") == document_id]

        def score(chunk: dict[str, Any]) -> float:
            text = f"{chunk.get('title', '')} {chunk.get('text', '')}".lower()
            return float(sum(1 for t in query_terms if t in text))

        ranked = sorted(chunks, key=score, reverse=True)[:top_k]
        packed = [
            {
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("doc_id"),
                "title": c.get("title"),
                "text": c.get("text"),
                "source": c.get("source_path"),
                "score": score(c),
            }
            for c in ranked
        ]
        return {
            "query": query,
            "course_id": course_id,
            "chunks": packed,
            "citations": [{"chunk_id": p["chunk_id"], "source": p["source"]} for p in packed],
        }
