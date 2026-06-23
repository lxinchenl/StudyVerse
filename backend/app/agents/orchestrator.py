import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable
from uuid import uuid4

from app.agents.main_agent import MainAgent
from app.agents.path_agent import PathPlanningAgent
from app.agents.course_workflow_agent import CourseWorkflowAgent
from app.agents.registry import EXPERT_AGENTS
from app.agents.resources import (
    CodeLabAgent,
    ExerciseAgent,
    MindmapAgent,
    NoteAgent,
    VideoAgent,
)
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.safety_agent import SafetyReviewAgent
from app.interfaces.contracts import BaseAgent, MemoryService
from app.services.chat_store import build_assistant_record, build_user_record
from app.services.material_context import preload_material_context

EventSink = Callable[[dict[str, Any]], Awaitable[None]]


class AgentOrchestrator:
    def __init__(
        self,
        main_agent: MainAgent,
        retrieval_agent: RetrievalAgent,
        exercise_agent: ExerciseAgent,
        note_agent: NoteAgent,
        mindmap_agent: MindmapAgent,
        video_agent: VideoAgent,
        code_lab_agent: CodeLabAgent,
        path_agent: PathPlanningAgent,
        course_workflow_agent: CourseWorkflowAgent,
        safety_agent: SafetyReviewAgent,
        memory: MemoryService,
    ):
        self.main_agent = main_agent
        self.memory = memory
        self._experts: dict[str, BaseAgent] = {
            retrieval_agent.name: retrieval_agent,
            exercise_agent.name: exercise_agent,
            note_agent.name: note_agent,
            mindmap_agent.name: mindmap_agent,
            video_agent.name: video_agent,
            code_lab_agent.name: code_lab_agent,
            path_agent.name: path_agent,
            course_workflow_agent.name: course_workflow_agent,
            safety_agent.name: safety_agent,
        }

    async def chat(
        self,
        *,
        user_id: str,
        message: str,
        course_id: str,
        document_id: str | None = None,
        course_workflow_action: str | None = None,
        course_proposal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._execute_chat(
            user_id=user_id,
            message=message,
            course_id=course_id,
            document_id=document_id,
            course_workflow_action=course_workflow_action,
            course_proposal=course_proposal,
        )

    async def chat_stream(
        self,
        *,
        user_id: str,
        message: str,
        course_id: str,
        document_id: str | None = None,
        course_workflow_action: str | None = None,
        course_proposal: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def event_sink(event: dict[str, Any]) -> None:
            await queue.put(event)

        async def runner() -> None:
            try:
                result = await self._execute_chat(
                    user_id=user_id,
                    message=message,
                    course_id=course_id,
                    document_id=document_id,
                    event_sink=event_sink,
                    course_workflow_action=course_workflow_action,
                    course_proposal=course_proposal,
                )
                await queue.put({"type": "done", "result": result})
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

    async def _execute_chat(
        self,
        *,
        user_id: str,
        message: str,
        course_id: str,
        document_id: str | None = None,
        event_sink: EventSink | None = None,
        course_workflow_action: str | None = None,
        course_proposal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "user_id": user_id,
            "message": message,
            "course_id": course_id,
            "document_id": document_id,
            "expert_outputs": [],
            "traces": [],
            "me": self.memory.get_me(user_id),
            "course_workflow_action": course_workflow_action,
        }
        if course_proposal is not None:
            context["course_proposal"] = course_proposal
        if event_sink is not None:
            context["event_sink"] = event_sink
            await event_sink({"type": "status", "message": "主 Agent 开始 ReAct 推理…"})

        preload_material_context(context, self.memory)
        answer = await self.main_agent.react_loop(context, self._experts)

        if event_sink is not None:
            await event_sink({"type": "status", "message": "推理完成，正在整理回答…"})

        now = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
        user_rec = build_user_record(msg_id=f"msg-{uuid4().hex[:8]}", content=message, timestamp=now)
        assistant_rec = build_assistant_record(
            msg_id=f"msg-{uuid4().hex[:8]}",
            content=answer,
            timestamp=now,
            context=context,
        )
        self.memory.append_chat_turn(user_id, user_rec, assistant_rec)
        profile = self.memory.get_profile(user_id)

        plan_tasks = []
        for i, step in enumerate(context.get("react_steps") or [], start=1):
            if step.get("action") != "call_expert":
                continue
            expert = step.get("expert", "")
            plan_tasks.append(
                {
                    "id": f"react-{i}",
                    "name": EXPERT_AGENTS.get(expert, expert),
                    "agent": expert,
                    "status": "done",
                    "parallel": False,
                    "input_summary": step.get("thought", "")[:80],
                    "output_summary": step.get("observation", "")[:120],
                }
            )

        self.memory.save_working_memory(
            user_id,
            {
                "planner_tasks": plan_tasks,
                "traces": context["traces"],
                "react_steps": context.get("react_steps", []),
            },
        )

        return {"answer": answer, "traces": context["traces"], "profile": profile, "context": context}
