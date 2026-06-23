from typing import Any

from app.interfaces.contracts import BaseAgent


class PathPlanningAgent(BaseAgent):
    name = "path-agent"
    role = "路径规划 Agent"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        profile = context.get("profile", {})
        weak = profile.get("weak_points", ["核心概念"])[0] if profile.get("weak_points") else "核心概念"
        steps = [
            {
                "id": "step-1",
                "title": f"补齐：{weak}",
                "objective": "建立稳定理解",
                "status": "in_progress",
                "estimated_minutes": 35,
                "resources": [],
            }
        ]
        context["learning_path"] = steps
        note = f"已生成以「{weak}」为起点的学习路径。"
        context.setdefault("expert_outputs", []).append(note)
        return {"path": steps, "trace": self.trace(note)}
