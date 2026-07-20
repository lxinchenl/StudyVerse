from typing import Any

from app.infrastructure.kg_rag.hybrid_retriever import extract_containment_terms
from app.interfaces.contracts import ChunkRepository, Retriever


class RetrievalAgentPipeline(Retriever):
    """Fixed retrieval pipeline: normalize -> filter -> containment keyword -> merge -> pack."""

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
        q = " ".join(str(query or "").lower().split()).strip()
        terms = extract_containment_terms(q)
        chunks = self.chunk_repo.list_chunks()
        if course_id:
            chunks = [c for c in chunks if c.get("course_id") == course_id]
        if document_id:
            chunks = [c for c in chunks if c.get("chunk_id") == document_id or c.get("doc_id") == document_id]

        def score(chunk: dict[str, Any]) -> float:
            title = str(chunk.get("title") or "").lower()
            text = f"{title} {chunk.get('text') or ''}".lower()
            total = float(sum(weight for term, weight in terms.items() if term in text))
            if title and len(title) >= 2 and title in q:
                total += 8.0 + float(len(title))
            return total

        scored = [(score(c), c) for c in chunks]
        ranked = sorted((pair for pair in scored if pair[0] > 0), key=lambda p: p[0], reverse=True)[
            :top_k
        ]
        packed = [
            {
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("doc_id"),
                "title": c.get("title"),
                "text": c.get("text"),
                "source": c.get("source_path"),
                "score": s,
            }
            for s, c in ranked
        ]
        return {
            "query": query,
            "course_id": course_id,
            "chunks": packed,
            "citations": [{"chunk_id": p["chunk_id"], "source": p["source"]} for p in packed],
        }
