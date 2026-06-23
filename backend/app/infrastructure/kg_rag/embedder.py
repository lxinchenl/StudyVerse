from functools import lru_cache
from pathlib import Path

from app.core.config import ROOT, get_settings


def resolve_embed_model_path(spec: str) -> str:
    raw = (spec or "").strip()
    if not raw:
        return raw
    candidate = Path(raw)
    if candidate.is_absolute() and candidate.is_dir():
        return str(candidate)
    rooted = ROOT / raw
    if rooted.is_dir():
        return str(rooted)
    if "/" not in raw:
        return raw
    parts = raw.split("/")
    if len(parts) != 2:
        return raw
    cache_root = ROOT / "kg_rag_demo" / "model" / f"models--{parts[0]}--{parts[1]}"
    snapshots = cache_root / "snapshots"
    if not snapshots.is_dir():
        return raw
    ref = cache_root / "refs" / "main"
    if ref.is_file():
        commit = ref.read_text(encoding="utf-8").strip()
        snap = snapshots / commit
        if snap.is_dir():
            return str(snap)
    for child in sorted(snapshots.iterdir()):
        if child.is_dir():
            return str(child)
    return raw


class QueryEmbedder:
    """Lazy local embedder for Chroma queries (same model family as kg_rag_demo)."""

    def __init__(self, model_path: str):
        self.model_path = resolve_embed_model_path(model_path)
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_path)

    def embed_query(self, text: str) -> list[float]:
        self._load()
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()
