"""Resource Studio orchestrator — MsgHub LLM discussion, generation, archive events."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable
from uuid import uuid4

from app.agents.registry import EXPERT_AGENTS
from app.agents.resources import (
    CodeLabAgent,
    ExerciseAgent,
    MindmapAgent,
    NoteAgent,
    VideoAgent,
)
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.studio_hub import StudioHubSession, TYPE_LABELS
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.services.app_services import ResourceService
from app.services.material_context import preload_material_context

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

TYPE_TO_AGENT: dict[str, str] = {
    "exercise": "exercise-agent",
    "note": "note-agent",
    "mindmap": "mindmap-agent",
    "video_script": "video-agent",
    "code_lab": "code-lab-agent",
}

AGENT_ROLES: dict[str, str] = {
    "inquiry-desk": "询问员",
    "inquiry-agent": "询问员",
    "data-archivist": "数据管理员",
    "retrieval-agent": EXPERT_AGENTS["retrieval-agent"],
    **{k: EXPERT_AGENTS.get(k, k) for k in TYPE_TO_AGENT.values()},
}


class ResourceStudioOrchestrator:
    def __init__(
        self,
        retrieval_agent: RetrievalAgent,
        exercise_agent: ExerciseAgent,
        note_agent: NoteAgent,
        mindmap_agent: MindmapAgent,
        video_agent: VideoAgent,
        code_lab_agent: CodeLabAgent,
        resource_service: ResourceService,
        memory: MemoryService,
        llm: LLMProvider,
    ):
        self.memory = memory
        self.resource_service = resource_service
        self.llm = llm
        self._experts: dict[str, BaseAgent] = {
            retrieval_agent.name: retrieval_agent,
            exercise_agent.name: exercise_agent,
            note_agent.name: note_agent,
            mindmap_agent.name: mindmap_agent,
            video_agent.name: video_agent,
            code_lab_agent.name: code_lab_agent,
        }

    async def generate_stream(
        self,
        *,
        user_id: str,
        topic: str,
        types: list[str],
        course_id: str,
        clarification: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def emit(event: dict[str, Any]) -> None:
            await queue.put(event)

        async def runner() -> None:
            try:
                result = await self._run_pipeline(
                    user_id=user_id,
                    topic=topic,
                    types=types,
                    course_id=course_id,
                    clarification=clarification,
                    emit=emit,
                )
                await queue.put({"type": "done", "resources": result})
            except Exception as exc:
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            await task

    def _hub_members(self, types: list[str]) -> list[str]:
        members = ["retrieval-agent"]
        for rtype in types:
            aid = TYPE_TO_AGENT.get(rtype)
            if aid and aid not in members:
                members.append(aid)
        return members

    def _producer_ids(self, types: list[str]) -> list[str]:
        ids: list[str] = []
        for rtype in types:
            aid = TYPE_TO_AGENT.get(rtype)
            if aid and aid not in ids:
                ids.append(aid)
        return ids

    async def _run_pipeline(
        self,
        *,
        user_id: str,
        topic: str,
        types: list[str],
        course_id: str,
        clarification: str | None,
        emit: EventSink,
    ) -> list[dict[str, Any]]:
        effective_topic = topic.strip()
        if clarification and clarification.strip():
            effective_topic = f"{topic.strip()}（补充：{clarification.strip()}）"

        members = self._hub_members(types)
        producer_ids = self._producer_ids(types)
        agents = self._initial_agent_states(members)
        await emit({"type": "agent_status", "agents": agents})
        await emit({"type": "hub_open", "members": members, "topic": topic.strip()})
        await asyncio.sleep(0.05)

        context: dict[str, Any] = {
            "user_id": user_id,
            "message": effective_topic,
            "course_id": course_id,
            "expert_outputs": [],
            "traces": [],
            "me": self.memory.get_me(user_id),
            "profile": self.memory.get_profile(user_id),
        }
        if clarification and clarification.strip():
            context["user_clarification_provided"] = True
            context["clarification_note"] = f"用户补充：{clarification.strip()}"

        preload_material_context(context, self.memory)

        session = StudioHubSession(
            llm=self.llm,
            retrieval_agent=self._experts["retrieval-agent"],
            experts=self._experts,
            memory=self.memory,
            agent_roles=AGENT_ROLES,
            ts_fn=self._ts,
        )

        completed, created = await session.run(
            user_id=user_id,
            topic=effective_topic,
            types=types,
            context=context,
            producer_ids=producer_ids,
            agents=agents,
            emit=emit,
            hub=self._hub,
            set_agent=self._set_agent,
            persist_resource=self._persist_resource,
        )

        if not completed:
            await self._set_all_idle(agents, emit)
            return []

        await emit({"type": "hub_close"})
        await self._set_all_idle(agents, emit)
        return created

    async def _persist_resource(
        self,
        user_id: str,
        rtype: str,
        topic: str,
        context: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        if rtype == "mindmap" and context.get("mindmaps"):
            card = context["mindmaps"][-1]
            resources = self.resource_service.list_resources(user_id)
            match = next((r for r in resources if r.id == card["resource_id"]), None)
            return match.model_dump() if match else None

        if rtype == "video_script":
            for card in reversed(context.get("generated_resources") or []):
                if card.get("type") == "video_script" and card.get("resource_id"):
                    resources = self.resource_service.list_resources(user_id)
                    match = next((r for r in resources if r.id == card["resource_id"]), None)
                    return match.model_dump() if match else None

        if rtype == "exercise" and context.get("exercise_sets"):
            card = context["exercise_sets"][-1]
            resources = self.resource_service.list_resources(user_id)
            match = next((r for r in resources if r.id == card["resource_id"]), None)
            return match.model_dump() if match else None

        if rtype == "note" and context.get("notes"):
            card = context["notes"][-1]
            resources = self.resource_service.list_resources(user_id)
            match = next((r for r in resources if r.id == card["resource_id"]), None)
            return match.model_dump() if match else None

        if rtype == "code_lab" and context.get("code_lab_sets"):
            card = context["code_lab_sets"][-1]
            resources = self.resource_service.list_resources(user_id)
            match = next((r for r in resources if r.id == card["resource_id"]), None)
            return match.model_dump() if match else None

        content = (
            context.get("generated_note")
            or result.get("content")
            or str(result.get("trace", ""))
        )
        from app.domain.schemas import ResourceOut

        item = ResourceOut(
            id=f"res-{uuid4().hex[:8]}",
            type=rtype,
            title=f"{topic[:24]}-{rtype}",
            summary=f"工作室生成的 {TYPE_LABELS.get(rtype, rtype)} 资源",
            content=content if isinstance(content, str) else str(content),
            topic=topic,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        existing = self.resource_service.list_resources(user_id)
        path = self.resource_service._user_file(user_id)
        all_items = [item] + existing
        path.write_text(
            json.dumps([i.model_dump() for i in all_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item.model_dump()

    def _initial_agent_states(self, hub_members: list[str]) -> list[dict[str, Any]]:
        """办公室全员状态；仅 hub 成员参与当前会话。"""
        roster = [
            "inquiry-desk",
            "data-archivist",
            "retrieval-agent",
            *TYPE_TO_AGENT.values(),
        ]
        agents: list[dict[str, Any]] = []
        for aid in roster:
            in_hub = aid in hub_members
            agents.append(
                {
                    "id": aid,
                    "status": "idle" if in_hub else "inactive",
                    "role": AGENT_ROLES.get(aid, aid),
                    "in_hub": in_hub,
                }
            )
        return agents

    async def _set_agent(
        self,
        agents: list[dict[str, Any]],
        agent_id: str,
        status: str,
        emit: EventSink,
    ) -> None:
        for a in agents:
            if a["id"] == agent_id:
                a["status"] = status
                break
        await emit({"type": "agent_status", "agents": agents})

    async def _set_all_idle(self, agents: list[dict[str, Any]], emit: EventSink) -> None:
        for a in agents:
            if a.get("in_hub"):
                a["status"] = "idle"
            else:
                a["status"] = "inactive"
        await emit({"type": "agent_status", "agents": agents})

    async def _hub(
        self,
        emit: EventSink,
        agent_id: str,
        content: str,
        timestamp: str,
        *,
        kind: str = "speak",
    ) -> None:
        await emit({
            "type": "hub",
            "message": {
                "id": f"hub-{uuid4().hex[:8]}",
                "agent": agent_id,
                "role": AGENT_ROLES.get(agent_id, agent_id),
                "content": content,
                "timestamp": timestamp,
                "kind": kind,
            },
        })

    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).astimezone().strftime("%H:%M")
