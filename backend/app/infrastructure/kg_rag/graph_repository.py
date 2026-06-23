from pathlib import Path
from typing import Any

from app.infrastructure.kg_rag.neo4j_store import Neo4jStore
from app.infrastructure.repositories import FileGraphRepository
from app.interfaces.contracts import GraphRepository


class HybridGraphRepository(GraphRepository):
    """Neo4j live graph first, legacy subgraphs.json as fallback."""

    def __init__(self, neo4j: Neo4jStore | None, legacy_dir: Path):
        self.neo4j = neo4j
        self.legacy = FileGraphRepository(legacy_dir)
        self._graph: dict[str, Any] | None = None

    def get_graph(self) -> dict[str, Any]:
        if self._graph is not None:
            return self._graph
        if self.neo4j and self.neo4j.is_available():
            graph = self.neo4j.export_graph()
            if graph.get("nodes"):
                self._graph = graph
                return graph
        self._graph = self.legacy.get_graph()
        return self._graph

    def backend_info(self) -> dict[str, Any]:
        neo4j_ok = bool(self.neo4j and self.neo4j.is_available())
        return {
            "graph_backend": "neo4j" if neo4j_ok else "legacy_json",
            "neo4j_connected": neo4j_ok,
        }
