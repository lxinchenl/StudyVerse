from typing import Any

from app.infrastructure.kg_rag.chroma_store import ChromaStore
from app.infrastructure.kg_rag.neo4j_store import Neo4jStore
from app.interfaces.contracts import ChunkRepository, Retriever


class HybridRetrievalPipeline(Retriever):
    """
    Plan-driven retrieval:
    - vector/keyword search uses rewritten queries from MainAgent plan (not raw user message)
    - graph search uses plan entities directly (no query entity extraction)
    """

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        chroma: ChromaStore | None = None,
        neo4j: Neo4jStore | None = None,
    ):
        self.chunk_repo = chunk_repo
        self.chroma = chroma
        self.neo4j = neo4j

    async def search(
        self,
        query: str = "",
        *,
        queries: list[str] | None = None,
        entities: list[str] | None = None,
        top_k: int = 5,
        course_id: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        query_list = self._normalize_queries(queries, query)
        entity_list = self._normalize_entities(entities)
        boost_text = " ".join(query_list)

        combined: dict[str, dict[str, Any]] = {}
        keyword_any = False
        vector_any = False

        for q in query_list:
            normalized = " ".join(q.strip().split())
            keyword_hits = self._keyword_search(
                normalized, top_k=max(top_k, 8), course_id=course_id, document_id=document_id
            )
            if keyword_hits:
                keyword_any = True

            vector_hits: list[dict[str, Any]] = []
            if self.chroma and self.chroma.is_available():
                vector_hits = self.chroma.search(normalized, top_k=max(top_k, 8))
                if vector_hits:
                    vector_any = True

            merged = self._merge_hits(keyword_hits, vector_hits, query=boost_text)
            for hit in merged:
                chunk_id = str(hit.get("chunk_id", ""))
                if not chunk_id:
                    continue
                if chunk_id not in combined or hit.get("score", 0) > combined[chunk_id].get("score", 0):
                    combined[chunk_id] = hit

        ranked = sorted(combined.values(), key=lambda row: row.get("score", 0), reverse=True)
        ranked = self._apply_scope(ranked, course_id, document_id)
        chunks = self._pack_chunks(ranked, top_k=top_k)

        kg_context: list[dict[str, Any]] = []
        if self.neo4j and self.neo4j.is_available() and entity_list:
            kg_context = self.neo4j.query_relations(entity_list, max_hops=1, limit=8)

        source_types: list[str] = []
        if keyword_any:
            source_types.append("course_material")
        if vector_any:
            source_types.append("chroma")
        if not source_types:
            source_types.append("none")

        return {
            "query": query,
            "queries": query_list,
            "entities": entity_list,
            "course_id": course_id,
            "document_scope": document_id,
            "chunks": chunks,
            "kg_context": kg_context,
            "citations": [{"chunk_id": c["chunk_id"], "source": c.get("source", "")} for c in chunks],
            "source_types": source_types,
        }

    @staticmethod
    def _normalize_queries(queries: list[str] | None, fallback: str) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in queries or []:
            text = " ".join(str(item).strip().split())
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        if not result:
            text = " ".join(fallback.strip().split())
            if text:
                result.append(text)
        return result

    @staticmethod
    def _normalize_entities(entities: list[str] | None) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in entities or []:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    def _keyword_search(
        self,
        query: str,
        *,
        top_k: int,
        course_id: str | None,
        document_id: str | None,
    ) -> list[dict[str, Any]]:
        terms = {t for t in query.lower().replace("，", " ").split() if len(t) > 1}
        rows = self.chunk_repo.list_chunks()
        rows = self._apply_scope_rows(rows, course_id, document_id)

        def score(row: dict[str, Any]) -> float:
            text = f"{row.get('title', '')} {row.get('text', '')}".lower()
            return float(sum(1 for t in terms if t in text))

        ranked = sorted(rows, key=score, reverse=True)[:top_k]
        return [
            {
                "chunk_id": r.get("chunk_id"),
                "course_id": r.get("course_id"),
                "doc_id": r.get("doc_id"),
                "title": r.get("title"),
                "text": r.get("text"),
                "source_path": r.get("source_path"),
                "score": score(r),
            }
            for r in ranked
            if score(r) > 0
        ]

    @staticmethod
    def _merge_hits(
        keyword_hits: list[dict[str, Any]],
        vector_hits: list[dict[str, Any]],
        *,
        query: str,
    ) -> list[dict[str, Any]]:
        terms = {
            t
            for t in query.lower().replace("，", " ").replace("？", " ").replace("?", " ").split()
            if len(t) > 1
        }
        combined: dict[str, dict[str, Any]] = {}

        def boost(hit: dict[str, Any]) -> dict[str, Any]:
            item = dict(hit)
            score = float(item.get("score", 0))
            title = str(item.get("title", "")).lower()
            path = str(item.get("source_path", "")).lower()
            for term in terms:
                if term in title or term in path:
                    score += 5.0
            item["score"] = score
            return item

        for hit in [boost(h) for h in keyword_hits] + vector_hits:
            chunk_id = str(hit.get("chunk_id", ""))
            if not chunk_id:
                continue
            if chunk_id not in combined or hit.get("score", 0) > combined[chunk_id].get("score", 0):
                combined[chunk_id] = hit

        return sorted(combined.values(), key=lambda row: row.get("score", 0), reverse=True)

    @staticmethod
    def _apply_scope(hits: list[dict[str, Any]], course_id: str | None, document_id: str | None) -> list[dict[str, Any]]:
        if document_id:
            return [
                h
                for h in hits
                if h.get("chunk_id") == document_id
                or h.get("doc_id") == document_id
                or document_id in str(h.get("source_path", ""))
            ]
        if course_id:
            scoped = [h for h in hits if h.get("course_id") == course_id]
            if scoped:
                return scoped
            return hits
        return hits

    @staticmethod
    def _apply_scope_rows(rows: list[dict[str, Any]], course_id: str | None, document_id: str | None) -> list[dict[str, Any]]:
        if document_id:
            return [
                r
                for r in rows
                if r.get("chunk_id") == document_id
                or r.get("doc_id") == document_id
                or document_id in str(r.get("source_path", ""))
            ]
        if course_id:
            return [r for r in rows if r.get("course_id") == course_id]
        return rows

    @staticmethod
    def _pack_chunks(hits: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        packed: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            chunk_id = str(hit.get("chunk_id", ""))
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            packed.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": hit.get("doc_id"),
                    "title": hit.get("title", chunk_id),
                    "text": hit.get("text", ""),
                    "source": hit.get("source_path", ""),
                    "score": float(hit.get("score", hit.get("distance", 0) or 0)),
                }
            )
            if len(packed) >= top_k:
                break
        return packed
