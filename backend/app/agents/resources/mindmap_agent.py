from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.agents.resources._helpers import retrieval_basis
from app.agents.resources.mindmap_design import (
    MINDMAP_SYSTEM,
    build_mindmap_prompt,
    parse_mindmap_payload,
)
from app.core.config import get_settings
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.services.app_services import ResourceService


class MindmapAgent(BaseAgent):
    """思维导图 Agent — Mermaid mindmap + 资源库注册。"""

    name = "mindmap-agent"
    role = "思维导图 Agent"
    skill_id = "mindmap-mermaid"

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
        basis = retrieval_basis(context, max_chars=2500)
        profile = context.get("profile") or self.memory.get_profile(user_id)
        conversation = self.memory.get_recent_conversation(user_id, limit=8)
        prompt = build_mindmap_prompt(
            message=context.get("message", ""),
            basis=basis,
            profile=profile,
            conversation=conversation,
        )

        raw = await self.llm.complete(prompt, system=MINDMAP_SYSTEM)
        try:
            payload = parse_mindmap_payload(raw)
        except ValueError:
            raw = await self.llm.complete(
                prompt + "\n\n上次 JSON 无效，请严格输出合法 JSON，mermaid 以 mindmap 开头。",
                system=MINDMAP_SYSTEM,
            )
            payload = parse_mindmap_payload(raw)

        mermaid = await self.invoke_tool(
            "mermaid-mindmap-render",
            source=payload["mermaid"],
            root_label=payload.get("topic") or payload.get("title"),
        )

        resource_id = f"mindmap-{uuid.uuid4().hex[:10]}"
        bundle_dir = self.resources_dir / "mindmap" / resource_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "mindmap.mmd").write_text(mermaid, encoding="utf-8")
        (bundle_dir / "mindmap.json").write_text(
            json.dumps({**payload, "mermaid": mermaid, "resource_id": resource_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        title = str(payload["title"])
        topic = str(payload["topic"])
        summary = str(payload["summary"])
        resource_item = self.resource_service.register_mindmap(
            user_id=user_id,
            resource_id=resource_id,
            title=title,
            topic=topic,
            summary=summary,
            mermaid_source=mermaid,
        )

        mindmap_card = {
            "resource_id": resource_id,
            "title": title,
            "topic": topic,
            "summary": summary,
            "mermaid_source": mermaid,
        }
        context.setdefault("mindmaps", []).append(mindmap_card)
        context.setdefault("generated_resources", []).append(
            {
                "type": "mindmap",
                "resource_id": resource_id,
                "title": title,
                "topic": topic,
                "summary": summary,
                "mermaid_source": mermaid,
                "skill": self.skill_ref(),
                "skill_id": self.skill_id,
            }
        )
        note = f"已生成思维导图《{title}》，Mermaid 可交互渲染。resource={resource_id}"
        context.setdefault("expert_outputs", []).append(note)
        return {
            "content": mermaid,
            "resource_type": "mindmap",
            "resource_id": resource_id,
            "mermaid_source": mermaid,
            "trace": self.trace(note),
            **mindmap_card,
        }
