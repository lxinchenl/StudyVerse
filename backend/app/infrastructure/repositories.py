import json
from pathlib import Path
from typing import Any

from app.infrastructure.document_parser import extract_text
from app.infrastructure.material_catalog import CourseCatalog
from app.interfaces.contracts import ChunkRepository, GraphRepository


class FileChunkRepository(ChunkRepository):
    """Build retrieval chunks from all courses under data/courses/."""

    def __init__(self, catalog: CourseCatalog, cache_dir: Path):
        self.catalog = catalog
        self.cache_dir = cache_dir
        self._chunks: list[dict[str, Any]] | None = None

    def _cache_path(self) -> Path:
        return self.cache_dir / "course_material_chunks.json"

    def list_chunks(self) -> list[dict[str, Any]]:
        if self._chunks is not None:
            return self._chunks

        cache_path = self._cache_path()
        if cache_path.exists():
            self._chunks = json.loads(cache_path.read_text(encoding="utf-8"))
            return self._chunks

        chunks: list[dict[str, Any]] = []
        for course in self.catalog.list_courses():
            for material in self.catalog.list_materials(course.id):
                try:
                    text, page = extract_text(material.path)
                except Exception:
                    continue
                if not text.strip():
                    continue
                chunks.append(
                    {
                        "chunk_id": material.id,
                        "course_id": material.course_id,
                        "doc_id": material.chapter_key,
                        "text": text,
                        "source_path": material.relative_path,
                        "page_number": page,
                        "title": material.title,
                        "order": 1,
                        "modality": material.doc_type,
                    }
                )

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        self._chunks = chunks
        return chunks

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        return next((c for c in self.list_chunks() if c.get("chunk_id") == chunk_id), None)


class FileGraphRepository(GraphRepository):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._graph: dict[str, Any] | None = None

    def get_graph(self) -> dict[str, Any]:
        if self._graph is not None:
            return self._graph
        path = self.data_dir / "subgraphs.json"
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        edge_idx = 0
        for subgraph in raw:
            for label in subgraph.get("nodes", []):
                node_id = label
                if node_id not in nodes:
                    nodes[node_id] = {"id": node_id, "label": label, "type": "KnowledgePoint"}
            for edge in subgraph.get("edges", []):
                edges.append(
                    {
                        "id": f"e{edge_idx}",
                        "source": edge["source"],
                        "target": edge["target"],
                        "relation": edge.get("relation", "related_to"),
                    }
                )
                edge_idx += 1
        node_list = list(nodes.values())
        for i, node in enumerate(node_list):
            node["x"] = 80 + (i % 8) * 100
            node["y"] = 80 + (i // 8) * 90
        self._graph = {"nodes": node_list, "edges": edges}
        return self._graph


class QuestionRepository:
    """Load practice questions from course questions.json and generated exercise bundles."""

    def __init__(self, courses_dir: Path, generated_dir: Path | None = None):
        self.courses_dir = courses_dir
        self.generated_dir = generated_dir or (courses_dir.parent / "generated_resources" / "exercises")
        self._questions: list[dict[str, Any]] | None = None

    def invalidate_cache(self) -> None:
        self._questions = None

    def list_questions(self) -> list[dict[str, Any]]:
        if self._questions is not None:
            return self._questions
        items: list[dict[str, Any]] = []
        items.extend(self._load_course_questions())
        items.extend(self._load_generated_questions())
        self._questions = items
        return items

    def _load_course_questions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not self.courses_dir.exists():
            return items
        for course_dir in sorted(p for p in self.courses_dir.iterdir() if p.is_dir()):
            qpath = course_dir / "questions.json"
            if not qpath.exists():
                continue
            course_id = course_dir.name
            meta_path = course_dir / "course.json"
            title = course_id
            if meta_path.exists():
                title = json.loads(meta_path.read_text(encoding="utf-8")).get("title", course_id)
            resource_id = f"res-ex-{course_id}"
            for i, row in enumerate(json.loads(qpath.read_text(encoding="utf-8"))):
                items.append(self._normalize_row(row, i, resource_id, f"{title} 练习题"))
        return items

    def _load_generated_questions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not self.generated_dir.exists():
            return items
        for bundle_dir in sorted(p for p in self.generated_dir.iterdir() if p.is_dir()):
            qpath = bundle_dir / "questions.json"
            meta_path = bundle_dir / "meta.json"
            if not qpath.exists():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            resource_id = str(meta.get("resource_id") or bundle_dir.name)
            title = str(meta.get("title") or "Agent 练习题")
            for i, row in enumerate(json.loads(qpath.read_text(encoding="utf-8"))):
                items.append(self._normalize_row(row, i, resource_id, title))
        return items

    @staticmethod
    def _normalize_row(row: dict[str, Any], index: int, resource_id: str, resource_title: str) -> dict[str, Any]:
        grading = str(row.get("grading_type") or "standard").strip().lower()
        if grading not in ("standard", "rubric"):
            grading = "standard"
        return {
            "id": row.get("id", f"{resource_id}-q{index}"),
            "resource_id": resource_id,
            "resource_title": resource_title,
            "topic": row.get("topic", resource_title),
            "difficulty": row.get("difficulty", "medium"),
            "question": row["question"],
            "standard_answer": row.get("answer", row.get("standard_answer", "")),
            "grading_type": grading,
            "rubric": row.get("rubric", ""),
        }

    def get_by_resource(self, resource_id: str) -> list[dict[str, Any]]:
        return [q for q in self.list_questions() if q["resource_id"] == resource_id]

    def save_generated_set(
        self,
        *,
        resource_id: str,
        user_id: str,
        title: str,
        topic: str,
        questions: list[dict[str, Any]],
    ) -> Path:
        bundle_dir = self.generated_dir / resource_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "meta.json").write_text(
            json.dumps(
                {
                    "resource_id": resource_id,
                    "user_id": user_id,
                    "title": title,
                    "topic": topic,
                    "question_count": len(questions),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (bundle_dir / "questions.json").write_text(
            json.dumps(questions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.invalidate_cache()
        return bundle_dir
