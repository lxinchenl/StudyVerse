from pathlib import Path
from typing import Any

import chromadb


class ChromaStore:
    """Read-only adapter for local Chroma persistent store."""

    def __init__(self, chroma_dir: Path, collection_name: str, embedder):
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        self.embedder = embedder
        self._client: chromadb.ClientAPI | None = None
        self._collection = None
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        if not self.chroma_dir.exists():
            self._available = False
            return False
        try:
            self._open()
            self._available = self._collection.count() > 0
        except Exception:
            self._available = False
        return self._available

    def count(self) -> int:
        if not self.is_available():
            return 0
        return self._collection.count()

    def search(self, query: str, *, top_k: int = 8) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        embedding = self.embedder.embed_query(query)
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict[str, Any]] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for chunk_id, text, meta, distance in zip(ids, docs, metas, distances):
            item = dict(meta or {})
            item["chunk_id"] = chunk_id
            item["text"] = text
            item["distance"] = distance
            item["score"] = max(0.0, 1.0 - float(distance))
            hits.append(item)
        return hits

    def _open(self) -> None:
        if self._collection is not None:
            return
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self._collection = self._client.get_or_create_collection(name=self.collection_name)
