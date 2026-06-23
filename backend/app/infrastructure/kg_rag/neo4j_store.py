import re
from typing import Any

from neo4j import GraphDatabase

_ENTITY_SPLIT = re.compile(r"[，。；、？！,.;!?\\s]+")


class Neo4jStore:
    """Read-only adapter for existing kg_rag_demo Neo4j graph."""

    def __init__(self, uri: str, username: str, password: str):
        self.uri = uri
        self.username = username
        self.password = password
        self._driver = None
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        if not self.password:
            self._available = False
            return False
        try:
            driver = self._get_driver()
            with driver.session() as session:
                session.run("RETURN 1").single()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def query_relations(self, entity_names: list[str], *, max_hops: int = 1, limit: int = 8) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        names = [n.strip() for n in entity_names if n.strip()]
        if not names:
            return []
        hops = max(1, min(max_hops, 2))
        rel_pattern = f"*1..{hops}"
        query = """
        UNWIND $entity_names AS query_entity
        MATCH (e:Entity)
        WHERE e.name = query_entity OR e.name CONTAINS query_entity OR query_entity CONTAINS e.name
        WITH DISTINCT query_entity, e,
             CASE
                WHEN e.name = query_entity THEN 0
                WHEN e.name CONTAINS query_entity THEN 1
                ELSE 2
             END AS score
        ORDER BY score ASC, size(e.name) ASC
        WITH collect({query_entity: query_entity, matched_entity: e.name})[..$entity_limit] AS matched
        UNWIND matched AS item
        MATCH path=(e:Entity {name: item.matched_entity})-[:RELATED_TO__REL_HOP__]-(neighbor:Entity)
        WITH item, relationships(path) AS rels, length(path) AS hop
        UNWIND rels AS r
        RETURN DISTINCT item.query_entity AS query_entity,
               item.matched_entity AS matched_entity,
               startNode(r).name AS source,
               endNode(r).name AS target,
               r.type AS relation,
               r.evidence AS evidence,
               r.source_path AS source_path,
               r.title AS title,
               hop AS path_hops
        LIMIT $result_limit
        """
        query = query.replace("__REL_HOP__", rel_pattern)
        with self._get_driver().session() as session:
            rows = session.run(
                query,
                entity_names=names,
                entity_limit=5,
                result_limit=limit,
            )
            return [row.data() for row in rows]

    def export_graph(self, *, node_limit: int = 200, edge_limit: int = 400) -> dict[str, Any]:
        if not self.is_available():
            return {"nodes": [], "edges": []}
        node_query = """
        MATCH (e:Entity)
        RETURN DISTINCT e.name AS name
        LIMIT $limit
        """
        edge_query = """
        MATCH (s:Entity)-[r:RELATED_TO]->(t:Entity)
        RETURN s.name AS source, t.name AS target, coalesce(r.type, 'related_to') AS relation
        LIMIT $limit
        """
        with self._get_driver().session() as session:
            node_rows = session.run(node_query, limit=node_limit)
            names = [r["name"] for r in node_rows if r.get("name")]
            edge_rows = session.run(edge_query, limit=edge_limit)
            edges_raw = [r.data() for r in edge_rows]

        nodes: dict[str, dict[str, Any]] = {}
        for name in names:
            nodes[name] = {
                "id": name,
                "label": name,
                "type": "KnowledgePoint",
            }
        edges: list[dict[str, Any]] = []
        for idx, row in enumerate(edges_raw):
            src, tgt = row.get("source"), row.get("target")
            if not src or not tgt:
                continue
            if src not in nodes:
                nodes[src] = {"id": src, "label": src, "type": "KnowledgePoint"}
            if tgt not in nodes:
                nodes[tgt] = {"id": tgt, "label": tgt, "type": "KnowledgePoint"}
            edges.append(
                {
                    "id": f"e{idx}",
                    "source": src,
                    "target": tgt,
                    "relation": row.get("relation", "related_to"),
                }
            )
        return {"nodes": list(nodes.values()), "edges": edges}

    @staticmethod
    def extract_entities(query: str, *, limit: int = 5) -> list[str]:
        parts = [p.strip() for p in _ENTITY_SPLIT.split(query) if len(p.strip()) >= 2]
        seen: set[str] = set()
        result: list[str] = []
        for part in parts:
            if part in seen:
                continue
            seen.add(part)
            result.append(part)
            if len(result) >= limit:
                break
        return result

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        return self._driver

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None
