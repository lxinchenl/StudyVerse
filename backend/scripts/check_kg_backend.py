#!/usr/bin/env python3
"""Check Chroma / Neo4j connectivity for edu_agent backend."""

from app.core.config import get_settings
from app.infrastructure.kg_rag import get_chroma_store, get_neo4j_store
from app.infrastructure.kg_rag.graph_repository import HybridGraphRepository


def main() -> None:
    s = get_settings()
    chroma = get_chroma_store()
    neo4j = get_neo4j_store()
    graph = HybridGraphRepository(neo4j, s.kg_data_dir)

    print("=== EduAgent KG Backend Status ===")
    print(f"Chroma path: {s.chroma_dir}")
    print(f"  available: {chroma.is_available()}  count: {chroma.count()}")
    print(f"Neo4j URI: {s.neo4j_uri}")
    print(f"  available: {neo4j.is_available()}")
    print(f"Graph backend: {graph.backend_info()}")

    if chroma.is_available():
        hits = chroma.search("数据库", top_k=2)
        print(f"Sample vector hits: {len(hits)}")
        for h in hits:
            print(f"  - {h.get('chunk_id')} | {h.get('title', '')[:40]}")

    if neo4j.is_available():
        rels = neo4j.query_relations(["数据库"], max_hops=1, limit=3)
        print(f"Sample KG relations: {len(rels)}")


if __name__ == "__main__":
    main()
