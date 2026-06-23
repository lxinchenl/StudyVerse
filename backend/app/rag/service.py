import json
from pathlib import Path

from app.interfaces.contracts import Retriever


class CourseKnowledgeBase:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self._documents: list[dict[str, str]] | None = None

    def load_documents(self) -> list[dict[str, str]]:
        if self._documents is not None:
            return self._documents
        if not self.data_path.exists():
            self._documents = []
            return self._documents
        data = json.loads(self.data_path.read_text(encoding="utf-8"))
        docs: list[dict[str, str]] = []
        for chapter in data.get("chapters", []):
            for section in chapter.get("sections", []):
                docs.append(
                    {
                        "id": section["id"],
                        "title": f"{chapter['title']} - {section['title']}",
                        "content": section["content"],
                        "source": f"{data.get('course_name', '课程知识库')} / {chapter['title']}",
                    }
                )
        self._documents = docs
        return docs


class KeywordRetriever(Retriever):
    """Small local retriever used before a vector DB is configured."""

    def __init__(self, knowledge_base: CourseKnowledgeBase):
        self.knowledge_base = knowledge_base

    async def search(self, query: str, *, top_k: int = 4) -> list[dict[str, str]]:
        docs = self.knowledge_base.load_documents()
        query_terms = {term for term in query.lower().replace("，", " ").replace("。", " ").split() if term}

        def score(doc: dict[str, str]) -> int:
            haystack = f"{doc['title']} {doc['content']}".lower()
            return sum(1 for term in query_terms if term in haystack)

        ranked = sorted(docs, key=score, reverse=True)
        selected = ranked[:top_k] if ranked else []
        return selected or docs[:top_k]

