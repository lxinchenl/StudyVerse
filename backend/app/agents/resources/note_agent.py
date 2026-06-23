from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.agents.resources.note_react import run_note_react
from app.core.config import get_settings
from app.infrastructure.note_assets import finalize_note_markdown, prepare_note_image_assets
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.services.app_services import ResourceService


class NoteAgent(BaseAgent):
    """笔记 Agent — ReAct 意图路由 + 对话/资料双模式（tutorial-to-notes 改编）。"""

    name = "note-agent"
    role = "笔记 Agent"
    skill_id = "tutorial-to-notes"

    def __init__(
        self,
        llm: LLMProvider,
        resource_service: ResourceService,
        memory: MemoryService,
        resources_dir: Path | None = None,
    ):
        self.llm = llm
        self.resource_service = resource_service
        self.memory = memory
        self.resources_dir = resources_dir or get_settings().resources_dir

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        # 笔记 Agent 自行解析资料，不依赖外部 retrieval-agent 预检索
        context.pop("retrieval", None)

        async def _progress(step: dict) -> None:
            from app.agents.chat_stream import pack_progress_event

            entry = {
                "step": step.get("step"),
                "thought": step.get("thought", ""),
                "action": f"note:{step.get('action', '')}",
                "observation": step.get("observation", ""),
                "expert": self.name,
                "status": step.get("status", "done"),
            }
            steps = context.setdefault("react_steps", [])
            step_num = entry.get("step")
            replaced = False
            if step_num is not None:
                for idx, existing in enumerate(steps):
                    if existing.get("step") == step_num and existing.get("expert") == self.name:
                        steps[idx] = entry
                        replaced = True
                        break
            if not replaced:
                steps.append(entry)
            sink = context.get("event_sink")
            if sink is not None:
                await sink(pack_progress_event(context))

        result = await run_note_react(
            llm=self.llm,
            memory=self.memory,
            context=context,
            agent_name=self.name,
            trace_fn=self.trace,
            progress_fn=_progress,
        )
        payload = result["payload"]
        intent = result.get("intent") or {}
        process = context.get("note_process")

        resource_id = f"note-{uuid.uuid4().hex[:10]}"
        bundle_dir = self.resources_dir / "note" / resource_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        assets = prepare_note_image_assets(process, bundle_dir / "images")
        markdown = finalize_note_markdown(payload["markdown"], assets)
        payload = {**payload, "markdown": markdown}

        meta = {
            **payload,
            "resource_id": resource_id,
            "mode": intent.get("mode", "conversation"),
            "intent": intent,
            "image_assets": assets,
        }
        (bundle_dir / "note.md").write_text(payload["markdown"], encoding="utf-8")
        (bundle_dir / "note.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resource_item = self.resource_service.register_note(
            user_id=user_id,
            resource_id=resource_id,
            title=payload["title"],
            topic=payload["topic"],
            summary=payload["summary"],
            markdown=payload["markdown"],
        )

        note_card = {
            "resource_id": resource_id,
            "title": payload["title"],
            "topic": payload["topic"],
            "summary": payload["summary"],
            "markdown": payload["markdown"],
            "mode": intent.get("mode"),
        }
        context["generated_note"] = payload["markdown"]
        context.setdefault("notes", []).append(note_card)
        context.setdefault("generated_resources", []).append(
            {
                "type": "note",
                "resource_id": resource_id,
                "title": payload["title"],
                "topic": payload["topic"],
                "summary": payload["summary"],
                "markdown": payload["markdown"],
                "skill": self.skill_ref(),
                "skill_id": self.skill_id,
                "mode": intent.get("mode"),
            }
        )
        trace = result.get("trace") or {}
        summary = trace.get("summary") if isinstance(trace, dict) else str(trace)
        context.setdefault("expert_outputs", []).append(summary or f"已生成笔记《{payload['title']}》")

        return {
            "content": payload["markdown"],
            "resource_type": "note",
            "resource_id": resource_id,
            "title": resource_item.title,
            "mode": intent.get("mode"),
            "trace": result.get("trace"),
        }
