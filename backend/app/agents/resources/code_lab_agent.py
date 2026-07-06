from __future__ import annotations

import re
import uuid
from typing import Any

from app.agents.resources._helpers import append_session_dialogue_basis, retrieval_basis
from app.agents.resources.code_lab_design import (
    GENERATE_SYSTEM,
    build_generate_prompt,
    parse_generated_code_labs,
)
from app.infrastructure.code_lab_repository import CodeLabRepository
from app.interfaces.contracts import BaseAgent, LLMProvider, MemoryService
from app.services.app_services import ResourceService


def _keywords(*parts: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        for token in re.split(r"[，。；、？！,.;!?\s]+", part):
            text = token.strip()
            if len(text) >= 2 and text not in seen:
                seen.add(text)
                result.append(text)
    return result[:12]


def _match_score(challenge: dict[str, Any], keywords: list[str]) -> int:
    hay = (
        f"{challenge.get('topic', '')} {challenge.get('question', '')} "
        f"{challenge.get('resource_title', '')}"
    ).lower()
    return sum(1 for kw in keywords if kw.lower() in hay)


def _attempt_status(score: float | None) -> str:
    if score is None:
        return "unanswered"
    if score >= 60:
        return "passed"
    return "failed"


class CodeLabAgent(BaseAgent):
    """实操案例 Agent — 生成 Python 编程题，沙箱 stdout 判题。"""

    name = "code-lab-agent"
    role = "实操案例 Agent"

    def __init__(
        self,
        llm: LLMProvider,
        resource_service: ResourceService,
        memory: MemoryService,
        code_lab_repo: CodeLabRepository,
    ):
        self.llm = llm
        self.resource_service = resource_service
        self.memory = memory
        self.code_lab_repo = code_lab_repo

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        mode = str(context.get("code_lab_mode") or "search").strip().lower()
        if mode == "generate":
            return await self._generate(context)
        return await self._search(context)

    async def _search(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        topic = str(context.get("code_lab_topic") or context.get("message") or "")
        retrieval = context.get("retrieval") or {}
        entities = retrieval.get("entities") or []
        keywords = _keywords(topic, context.get("message", ""), *entities)

        attempts = self.memory.get_practice_attempts(user_id)
        all_challenges = self.code_lab_repo.list_challenges()
        scored = sorted(
            ((c, _match_score(c, keywords)) for c in all_challenges),
            key=lambda item: item[1],
            reverse=True,
        )
        matched = [c for c, score in scored if score > 0][:12]
        if not matched and keywords:
            matched = [c for c, _ in scored[:6]]

        by_resource: dict[str, list[dict[str, Any]]] = {}
        for c in matched:
            by_resource.setdefault(c["resource_id"], []).append(c)

        best_resource_id = ""
        best_challenges: list[dict[str, Any]] = []
        if by_resource:
            best_resource_id = max(by_resource, key=lambda rid: len(by_resource[rid]))
            best_challenges = by_resource[best_resource_id][:4]

        display: list[dict[str, Any]] = []
        unanswered = failed = passed = 0
        for c in best_challenges:
            last = attempts.get(c["resource_id"], {}).get(c["id"])
            score = last.get("score") if isinstance(last, dict) else None
            status = _attempt_status(score)
            if status == "unanswered":
                unanswered += 1
            elif status == "failed":
                failed += 1
            else:
                passed += 1
            display.append(self._public_challenge(c, status, score))

        needs_generate = len(best_challenges) == 0 or unanswered > 0 or failed > 0
        context["code_lab_search"] = {
            "matched_count": len(best_challenges),
            "resource_id": best_resource_id,
            "needs_generate": needs_generate,
            "unanswered": unanswered,
            "failed": failed,
            "passed": passed,
        }

        if best_challenges:
            lab_set = {
                "resource_id": best_resource_id,
                "title": best_challenges[0].get("resource_title", "编程练习"),
                "topic": topic or best_challenges[0].get("topic", ""),
                "summary": (
                    f"匹配 {len(best_challenges)} 题（未做 {unanswered} · 未通过 {failed} · 已通过 {passed}）"
                ),
                "challenges": display,
            }
            context.setdefault("code_lab_sets", []).append(lab_set)

        if not best_challenges:
            note = f"查找模式：未匹配到与「{topic[:30] or '当前主题'}」相关的编程题，needs_generate=true。"
        else:
            note = (
                f"查找模式：匹配 {len(best_challenges)} 题（resource={best_resource_id}），"
                f"needs_generate={'true' if needs_generate else 'false'}。"
            )
        context.setdefault("expert_outputs", []).append(note)
        return {
            "mode": "search",
            "challenges": best_challenges,
            "needs_generate": needs_generate,
            "trace": self.trace(note),
        }

    async def _generate(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        topic = str(context.get("code_lab_topic") or context.get("message") or "数据库编程")
        basis = append_session_dialogue_basis(retrieval_basis(context, max_chars=2500), context)
        profile = context.get("profile") or self.memory.get_profile(user_id)
        conversation = self.memory.get_recent_conversation(user_id, limit=8)
        prompt = build_generate_prompt(
            topic=topic,
            message=context.get("message", ""),
            basis=basis,
            profile=profile,
            conversation=conversation,
        )
        raw = await self.llm.complete(prompt, system=GENERATE_SYSTEM)
        try:
            payload = parse_generated_code_labs(raw)
        except ValueError as exc:
            retry_prompt = (
                f"{prompt}\n\n"
                f"上次输出无法解析：{exc}\n"
                f"上次输出片段：{raw[:1200]}\n\n"
                "请重新输出。要求：只输出一个合法 JSON 对象；首字符是 {，末字符是 }；"
                "不要 markdown 围栏；不要解释文字；所有多行 question/setup_code/starter_code/solution_code "
                "必须使用 \\n 转义换行；challenges 2~4 条且每条必须含 solution_code。"
            )
            raw = await self.llm.complete(
                retry_prompt,
                system=GENERATE_SYSTEM,
            )
            payload = parse_generated_code_labs(raw)

        resource_id = f"lab-gen-{uuid.uuid4().hex[:10]}"
        title = str(payload.get("title") or f"{topic} 编程练习")
        topic_out = str(payload.get("topic") or topic)
        challenges = payload["challenges"]

        self.code_lab_repo.save_generated_set(
            resource_id=resource_id,
            user_id=user_id,
            title=title,
            topic=topic_out,
            challenges=challenges,
        )
        enriched = self.code_lab_repo.get_by_resource(resource_id)
        resource_item = self.resource_service.register_code_lab_set(
            user_id=user_id,
            resource_id=resource_id,
            title=title,
            topic=topic_out,
            summary=f"Agent 生成 {len(enriched)} 道编程题 · stdout 沙箱判题",
            challenge_count=len(enriched),
        )

        display = [self._public_challenge(c, "unanswered", None) for c in enriched]
        lab_set = {
            "resource_id": resource_id,
            "title": title,
            "topic": topic_out,
            "summary": resource_item.summary,
            "challenges": display,
        }
        context.setdefault("code_lab_sets", []).append(lab_set)
        context.setdefault("generated_resources", []).append(
            {
                "type": "code_lab",
                "resource_id": resource_id,
                "title": title,
                "topic": topic_out,
                "summary": resource_item.summary,
                "challenge_count": len(enriched),
            }
        )
        note = f"生成模式：已生成《{title}》共 {len(enriched)} 道编程题，resource={resource_id}，可在对话中编码作答。"
        context.setdefault("expert_outputs", []).append(note)
        return {
            "mode": "generate",
            "resource_id": resource_id,
            "challenges": enriched,
            "trace": self.trace(note),
        }

    @staticmethod
    def _public_challenge(
        challenge: dict[str, Any],
        attempt_status: str,
        last_score: float | None,
    ) -> dict[str, Any]:
        return {
            "id": challenge["id"],
            "topic": challenge.get("topic", ""),
            "difficulty": challenge.get("difficulty", "medium"),
            "question": challenge.get("question", ""),
            "starter_code": challenge.get("starter_code", ""),
            "setup_code": challenge.get("setup_code", ""),
            "language": challenge.get("language", "python"),
            "hint": challenge.get("hint", ""),
            "attempt_status": attempt_status,
            "last_score": last_score,
        }
