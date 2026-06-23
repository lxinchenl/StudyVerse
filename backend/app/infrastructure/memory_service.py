import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.interfaces.contracts import MemoryService


def _today() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


class FileMemoryService(MemoryService):
    """Per-user memory stored under data/users/{user_id}/."""

    def __init__(self, users_dir: Path):
        self.users_dir = users_dir

    def _user_dir(self, user_id: str) -> Path:
        path = self.users_dir / user_id
        path.mkdir(parents=True, exist_ok=True)
        (path / "memory").mkdir(exist_ok=True)
        (path / "conversation_memory").mkdir(exist_ok=True)
        return path

    def get_profile(self, user_id: str) -> dict[str, Any]:
        defaults = {
            "student_id": user_id,
            "major": "",
                "course": "",
            "goal": "",
            "recent_topics": [],
            "weak_points": [],
            "frequent_errors": [],
            "preferences": [],
            "mastery": {},
        }
        path = self._user_dir(user_id) / "user_profile.json"
        if not path.exists():
            return defaults
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**defaults, **data, "student_id": user_id}

    def save_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        path = self._user_dir(user_id) / "user_profile.json"
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_me(self, user_id: str) -> dict[str, Any]:
        path = self._user_dir(user_id) / "me.json"
        if not path.exists():
            return {"role": "高校课程学习助手", "tone": "耐心清晰", "boundaries": "基于课程资料回答"}
        return json.loads(path.read_text(encoding="utf-8"))

    def _conversation_path(self, user_id: str) -> Path:
        return self._user_dir(user_id) / "conversation_memory" / f"{_today()}.json"

    def _load_conversation_day(self, user_id: str) -> dict[str, Any]:
        path = self._conversation_path(user_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"date": _today(), "student_id": user_id, "messages": [], "summary": ""}

    def _save_conversation_day(self, user_id: str, data: dict[str, Any]) -> None:
        path = self._conversation_path(user_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_conversation(self, user_id: str, role: str, content: str) -> None:
        data = self._load_conversation_day(user_id)
        data["messages"].append(
            {
                "time": datetime.now(timezone.utc).astimezone().strftime("%H:%M"),
                "role": role,
                "content": content,
            }
        )
        self._save_conversation_day(user_id, data)

    def append_chat_turn(
        self,
        user_id: str,
        user_message: dict[str, Any],
        assistant_message: dict[str, Any],
    ) -> None:
        data = self._load_conversation_day(user_id)
        data["messages"].append(user_message)
        data["messages"].append(assistant_message)
        self._save_conversation_day(user_id, data)

    def get_recent_conversation(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        conv_dir = self._user_dir(user_id) / "conversation_memory"
        files = sorted(conv_dir.glob("*.json"), reverse=True)
        messages: list[dict[str, Any]] = []
        for file in files:
            data = json.loads(file.read_text(encoding="utf-8"))
            messages.extend(data.get("messages", []))
            if len(messages) >= limit:
                break
        return messages[-limit:]

    def search_memory(self, user_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        mem_dir = self._user_dir(user_id) / "memory"
        hits: list[dict[str, Any]] = []
        for file in mem_dir.glob("*.json"):
            item = json.loads(file.read_text(encoding="utf-8"))
            if query.lower() in item.get("content", "").lower():
                hits.append(item)
        return hits[:limit]

    def add_memory(self, user_id: str, content: str, *, memory_type: str = "event") -> None:
        mem_dir = self._user_dir(user_id) / "memory"
        item_id = f"mem_{int(datetime.now(timezone.utc).timestamp())}"
        item = {
            "id": item_id,
            "type": memory_type,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (mem_dir / f"{item_id}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_working_memory(self, user_id: str) -> dict[str, Any]:
        path = self._user_dir(user_id) / "working_memory.json"
        if not path.exists():
            return {"planner_tasks": [], "traces": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_working_memory(self, user_id: str, data: dict[str, Any]) -> None:
        path = self._user_dir(user_id) / "working_memory.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear_conversation(self, user_id: str) -> None:
        conv_dir = self._user_dir(user_id) / "conversation_memory"
        for file in conv_dir.glob("*.json"):
            file.unlink(missing_ok=True)

    def get_stored_material_context(self, user_id: str) -> dict[str, Any] | None:
        messages = self.get_recent_conversation(user_id, limit=30)
        for row in reversed(messages):
            if row.get("role") != "assistant":
                continue
            retrieval = row.get("retrieval")
            if isinstance(retrieval, dict) and retrieval.get("chunks"):
                return retrieval
        return None

    def clear_short_term_memory(self, user_id: str) -> None:
        working_path = self._user_dir(user_id) / "working_memory.json"
        working_path.write_text(
            json.dumps({"planner_tasks": [], "traces": [], "react_steps": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        mem_dir = self._user_dir(user_id) / "memory"
        for file in mem_dir.glob("*.json"):
            file.unlink(missing_ok=True)

    def _practice_attempts_path(self, user_id: str) -> Path:
        return self._user_dir(user_id) / "practice_attempts.json"

    def get_practice_attempts(self, user_id: str) -> dict[str, dict[str, dict[str, Any]]]:
        path = self._practice_attempts_path(user_id)
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def record_practice_attempt(
        self,
        user_id: str,
        resource_id: str,
        results: list[dict[str, Any]],
    ) -> None:
        store = self.get_practice_attempts(user_id)
        bucket = store.setdefault(resource_id, {})
        now = datetime.now(timezone.utc).isoformat()
        for row in results:
            qid = str(row.get("question_id", ""))
            if not qid:
                continue
            bucket[qid] = {
                "score": row.get("score", 0),
                "answer": row.get("user_answer", ""),
                "updated_at": now,
            }
        self._practice_attempts_path(user_id).write_text(
            json.dumps(store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _reading_progress_path(self, user_id: str) -> Path:
        return self._user_dir(user_id) / "reading_progress.json"

    def get_learning_progress(self, user_id: str) -> dict[str, Any]:
        defaults: dict[str, Any] = {"documents": {}}
        path = self._reading_progress_path(user_id)
        if not path.exists():
            return defaults
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return defaults
        if not isinstance(data, dict):
            return defaults
        documents = data.get("documents")
        if not isinstance(documents, dict):
            data["documents"] = {}
        return {**defaults, **data}

    def _save_learning_progress(self, user_id: str, data: dict[str, Any]) -> None:
        self._reading_progress_path(user_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_document_learning_progress(self, user_id: str, doc_id: str) -> dict[str, Any] | None:
        docs = self.get_learning_progress(user_id).get("documents") or {}
        row = docs.get(doc_id)
        return row if isinstance(row, dict) else None

    def update_document_progress(
        self,
        user_id: str,
        *,
        doc_id: str,
        course_id: str,
        doc_type: str,
        viewed_page: int | None = None,
        total_pages: int | None = None,
        completed: bool = False,
    ) -> dict[str, Any]:
        store = self.get_learning_progress(user_id)
        documents = store.setdefault("documents", {})
        if not isinstance(documents, dict):
            documents = {}
            store["documents"] = documents
        previous = documents.get(doc_id) if isinstance(documents.get(doc_id), dict) else {}

        prev_progress = float(previous.get("progress") or 0.0)
        prev_max_page = int(previous.get("max_viewed_page") or 0)
        prev_total_pages = int(previous.get("total_pages") or 0)
        prev_completed = bool(previous.get("completed"))

        next_total_pages = max(int(total_pages or 0), prev_total_pages)
        next_max_page = max(prev_max_page, int(viewed_page or 0))
        next_progress = prev_progress

        if doc_type in {"pdf", "docx"}:
            next_progress = 100.0
        elif doc_type == "pptx":
            denominator = max(next_total_pages, 1)
            ppt_progress = min(100.0, max(0.0, round(next_max_page / denominator * 100, 1)))
            next_progress = max(prev_progress, ppt_progress)
        elif completed:
            next_progress = 100.0

        if completed:
            next_progress = 100.0

        next_progress = min(100.0, max(prev_progress, next_progress))
        next_completed = prev_completed or completed or next_progress >= 100.0

        next_record = {
            "course_id": course_id,
            "doc_type": doc_type,
            "progress": round(next_progress, 1),
            "max_viewed_page": next_max_page,
            "total_pages": next_total_pages,
            "completed": next_completed,
            "last_studied_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d"),
        }
        documents[doc_id] = next_record
        self._save_learning_progress(user_id, store)
        return next_record
