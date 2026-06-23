from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache
def get_embedder():
    from app.infrastructure.kg_rag.embedder import QueryEmbedder

    s = get_settings()
    return QueryEmbedder(s.embed_model_path)


@lru_cache
def get_chroma_store():
    from app.infrastructure.kg_rag.chroma_store import ChromaStore

    s = get_settings()
    return ChromaStore(s.chroma_dir, s.chroma_collection, get_embedder())


@lru_cache
def get_neo4j_store():
    from app.infrastructure.kg_rag.neo4j_store import Neo4jStore

    s = get_settings()
    return Neo4jStore(s.neo4j_uri, s.neo4j_username, s.neo4j_password)
