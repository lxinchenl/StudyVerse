from typing import Any, Protocol

from app.interfaces.contracts import BaseAgent


class ToxicContentDetector(Protocol):
    """轻量化网暴/有害内容检测模型接口（后续训练完成后注入）。"""

    async def scan(self, text: str) -> dict[str, Any]:
        """
        返回示例：
        {"is_toxic": bool, "score": float, "labels": list[str]}
        """
        ...


class SafetyReviewAgent(BaseAgent):
    """
    Review / Safety Agent 占位实现。

    当前：规则级来源校验（检索为空时的提醒）。
    后续：注入 ToxicContentDetector，对用户输入与生成内容做网暴检测。
    """

    name = "safety-agent"
    role = "安全审校 Agent"

    def __init__(self, detector: ToxicContentDetector | None = None):
        self.detector = detector

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        warnings: list[str] = []

        chunks = context.get("retrieval", {}).get("chunks", [])
        if context.get("message") and not chunks and context.get("need_pipeline"):
            warnings.append("部分回答缺乏明确课程引用，请结合资料谨慎理解。")

        if self.detector is not None:
            user_text = context.get("message") or ""
            scan = await self.detector.scan(user_text)
            if scan.get("is_toxic"):
                labels = "、".join(scan.get("labels") or []) or "有害内容"
                warnings.append(f"检测到潜在敏感内容（{labels}），请文明交流。")

        for note in warnings:
            context.setdefault("expert_outputs", []).append(note)

        summary = "完成来源与安全审校"
        if warnings:
            summary += f"（{len(warnings)} 条提醒）"
        if self.detector is None:
            summary += "；网暴检测模型尚未接入"

        return {"warnings": warnings, "trace": self.trace(summary)}
