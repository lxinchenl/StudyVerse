from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        ...

class ChunkRepository(ABC):
    @abstractmethod
    def list_chunks(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        ...


class GraphRepository(ABC):
    @abstractmethod
    def get_graph(self) -> dict[str, Any]:
        ...


class Retriever(ABC):
    @abstractmethod
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
        ...


class MemoryService(ABC):
    @abstractmethod
    def get_profile(self, user_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def save_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def get_me(self, user_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def append_conversation(self, user_id: str, role: str, content: str) -> None:
        ...

    @abstractmethod
    def append_chat_turn(
        self,
        user_id: str,
        user_message: dict[str, Any],
        assistant_message: dict[str, Any],
    ) -> None:
        ...

    @abstractmethod
    def get_recent_conversation(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def add_memory(self, user_id: str, content: str, *, memory_type: str = "event") -> None:
        ...

    @abstractmethod
    def get_working_memory(self, user_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def save_working_memory(self, user_id: str, data: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def get_stored_material_context(self, user_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def clear_conversation(self, user_id: str) -> None:
        ...

    @abstractmethod
    def clear_short_term_memory(self, user_id: str) -> None:
        ...

    @abstractmethod
    def get_learning_progress(self, user_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_document_learning_progress(self, user_id: str, doc_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
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
        ...


class BaseAgent(ABC):
    name: str
    role: str
    skill_id: str | None = None
    """Optional bound skill package id (e.g. ``explainer-video-html`` for VideoAgent)."""

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        ...

    def trace(self, summary: str, status: str = "done") -> dict[str, Any]:
        return {"agent": self.name, "role": self.role, "summary": summary, "status": status}

    def tool_context(self) -> dict[str, Any]:
        """Extra kwargs injected into ``invoke_tool`` (see tool.json ``context_keys``)."""
        return {}

    def _skill_loader(self):
        from app.skills.loader import get_skill_loader

        return get_skill_loader()

    def _tool_registry(self):
        from app.tools.registry import get_tool_registry

        return get_tool_registry()

    def _resolve_skill_id(self, skill_id: str | None = None) -> str:
        sid = skill_id or self.skill_id
        if not sid:
            raise ValueError(f"{self.name} has no skill_id")
        return sid

    def load_skill_manifest(self, skill_id: str | None = None) -> dict[str, Any]:
        return self._skill_loader().load_manifest(self._resolve_skill_id(skill_id))

    def load_prompt(self, prompt_key: str, *, skill_id: str | None = None, fallback: str = "") -> str:
        """Load optional prompt file shipped with a skill package (not agent system prompts)."""
        sid = skill_id or self.skill_id
        if not sid:
            return fallback
        try:
            return self._skill_loader().load_prompt(sid, prompt_key)
        except (FileNotFoundError, KeyError, ValueError):
            return fallback

    def load_skill_doc(self, doc_key: str, *, skill_id: str | None = None) -> str:
        return self._skill_loader().load_doc(self._resolve_skill_id(skill_id), doc_key)

    def skill_ref(self, skill_id: str | None = None) -> str:
        sid = skill_id or self.skill_id
        if not sid:
            return ""
        try:
            return self._skill_loader().skill_ref(sid)
        except FileNotFoundError:
            return f"skills/{sid}/SKILL.md"

    def list_skills(self) -> list[dict[str, Any]]:
        return self._skill_loader().list_skills()

    def list_tools(self) -> list[dict[str, Any]]:
        return self._tool_registry().list_tools()

    def get_tool_manifest(self, tool_id: str) -> dict[str, Any]:
        return self._tool_registry().get_tool(tool_id)

    async def invoke_tool(
        self,
        tool_id: str,
        *,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        from app.tools.executor import invoke_tool

        merged_context = {**self.tool_context(), **(context or {})}
        return await invoke_tool(tool_id, agent_context=merged_context, **kwargs)

    async def run_skill(
        self,
        skill_id: str,
        context: dict[str, Any],
        *,
        experts: dict[str, "BaseAgent"] | None = None,
    ) -> dict[str, Any]:
        manifest = self.load_skill_manifest(skill_id)
        agent_name = manifest.get("agent")
        if experts and agent_name:
            expert = experts.get(str(agent_name))
            if expert is not None:
                result = await expert.run(context)
                result.setdefault("skill_id", skill_id)
                return result
        return {
            "skill_id": skill_id,
            "manifest": manifest,
            "prompt_keys": list((manifest.get("prompts") or {}).keys()),
            "note": (
                f"skill `{skill_id}` loaded; expert `{agent_name}` not available"
                if agent_name
                else f"skill `{skill_id}` loaded (no bound agent)"
            ),
        }