from __future__ import annotations

import re
import uuid
from typing import Any

from app.agents.resources._helpers import retrieval_basis
from app.agents.resources.exercise_design import (
    GENERATE_SYSTEM,
    build_generate_prompt,
    parse_generated_exercises,
)
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


def _match_score(question: dict[str, Any], keywords: list[str]) -> int:
    hay = f"{question.get('topic', '')} {question.get('question', '')} {question.get('resource_title', '')}".lower()
    return sum(1 for kw in keywords if kw.lower() in hay)


def _attempt_status(score: float | None) -> str:
    if score is None:
        return "unanswered"
    if score >= 60:
        return "correct"
    return "wrong"


class ExerciseAgent(BaseAgent):
    name = "exercise-agent"
    role = "练习题 Agent"

    def __init__(
        self,
        question_repo,
        llm: LLMProvider,
        resource_service: ResourceService,
        memory: MemoryService,
    ):
        self.question_repo = question_repo
        self.llm = llm
        self.resource_service = resource_service
        self.memory = memory

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        mode = str(context.get("exercise_mode") or "search").strip().lower()
        if mode == "generate":
            return await self._generate(context)
        return await self._search(context)

    async def _search(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        topic = str(context.get("exercise_topic") or context.get("message") or "")
        retrieval = context.get("retrieval") or {}
        entities = retrieval.get("entities") or []
        keywords = _keywords(topic, context.get("message", ""), *entities)

        attempts = self.memory.get_practice_attempts(user_id)
        all_questions = self.question_repo.list_questions()
        scored = sorted(
            ((q, _match_score(q, keywords)) for q in all_questions),
            key=lambda item: item[1],
            reverse=True,
        )
        matched = [q for q, score in scored if score > 0][:8]
        if not matched and keywords:
            matched = [q for q, _ in scored[:5]]

        by_resource: dict[str, list[dict[str, Any]]] = {}
        for q in matched:
            by_resource.setdefault(q["resource_id"], []).append(q)

        best_resource_id = ""
        best_questions: list[dict[str, Any]] = []
        if by_resource:
            best_resource_id = max(by_resource, key=lambda rid: len(by_resource[rid]))
            best_questions = by_resource[best_resource_id][:5]

        display_questions: list[dict[str, Any]] = []
        unanswered = wrong = correct = 0
        for q in best_questions:
            last = attempts.get(q["resource_id"], {}).get(q["id"])
            score = last.get("score") if isinstance(last, dict) else None
            status = _attempt_status(score)
            if status == "unanswered":
                unanswered += 1
            elif status == "wrong":
                wrong += 1
            else:
                correct += 1
            display_questions.append(
                {
                    "id": q["id"],
                    "topic": q.get("topic", ""),
                    "difficulty": q.get("difficulty", "medium"),
                    "question": q.get("question", ""),
                    "grading_type": q.get("grading_type", "standard"),
                    "attempt_status": status,
                    "last_score": score,
                }
            )

        needs_generate = len(best_questions) == 0 or unanswered > 0 or wrong > 0
        context["matched_questions"] = best_questions
        context["exercise_search"] = {
            "matched_count": len(best_questions),
            "resource_id": best_resource_id,
            "needs_generate": needs_generate,
            "unanswered": unanswered,
            "wrong": wrong,
            "correct": correct,
        }

        if best_questions:
            exercise_set = {
                "resource_id": best_resource_id,
                "title": best_questions[0].get("resource_title", "练习题"),
                "topic": topic or best_questions[0].get("topic", ""),
                "summary": f"匹配 {len(best_questions)} 题（未答 {unanswered} · 答错 {wrong} · 正确 {correct}）",
                "questions": display_questions,
            }
            context.setdefault("exercise_sets", []).append(exercise_set)

        if not best_questions:
            note = f"查找模式：未匹配到与「{topic[:30] or '当前主题'}」相关的练习题，needs_generate=true。"
        else:
            note = (
                f"查找模式：匹配 {len(best_questions)} 题（resource={best_resource_id}），"
                f"未答 {unanswered}、答错 {wrong}、正确 {correct}，"
                f"needs_generate={'true' if needs_generate else 'false'}。"
            )
        context.setdefault("expert_outputs", []).append(note)
        return {"mode": "search", "questions": best_questions, "needs_generate": needs_generate, "trace": self.trace(note)}

    async def _generate(self, context: dict[str, Any]) -> dict[str, Any]:
        user_id = context["user_id"]
        topic = str(context.get("exercise_topic") or context.get("message") or "数据库练习")
        basis = retrieval_basis(context, max_chars=2500)
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
            payload = parse_generated_exercises(raw)
        except ValueError:
            raw = await self.llm.complete(
                prompt + "\n\n上次 JSON 无效，请严格输出合法 JSON，questions 3~5 条。",
                system=GENERATE_SYSTEM,
            )
            payload = parse_generated_exercises(raw)

        resource_id = f"ex-gen-{uuid.uuid4().hex[:10]}"
        title = str(payload.get("title") or f"{topic} 练习题")
        topic_out = str(payload.get("topic") or topic)
        questions = payload["questions"]

        self.question_repo.save_generated_set(
            resource_id=resource_id,
            user_id=user_id,
            title=title,
            topic=topic_out,
            questions=questions,
        )
        enriched = self.question_repo.get_by_resource(resource_id)
        resource_item = self.resource_service.register_exercise_set(
            user_id=user_id,
            resource_id=resource_id,
            title=title,
            topic=topic_out,
            summary=f"Agent 生成 {len(enriched)} 道题 · 标准答案/LLM 评分",
            question_count=len(enriched),
        )

        display_questions = [
            {
                "id": q["id"],
                "topic": q.get("topic", ""),
                "difficulty": q.get("difficulty", "medium"),
                "question": q.get("question", ""),
                "grading_type": q.get("grading_type", "standard"),
                "attempt_status": "unanswered",
                "last_score": None,
            }
            for q in enriched
        ]
        exercise_set = {
            "resource_id": resource_id,
            "title": title,
            "topic": topic_out,
            "summary": resource_item.summary,
            "questions": display_questions,
        }
        context.setdefault("exercise_sets", []).append(exercise_set)
        context.setdefault("generated_resources", []).append(
            {
                "type": "exercise",
                "resource_id": resource_id,
                "title": title,
                "topic": topic_out,
                "summary": resource_item.summary,
                "question_count": len(enriched),
            }
        )
        context["matched_questions"] = enriched
        note = f"生成模式：已生成《{title}》共 {len(enriched)} 题，resource={resource_id}，可在对话或练习页作答。"
        context.setdefault("expert_outputs", []).append(note)
        return {
            "mode": "generate",
            "resource_id": resource_id,
            "questions": enriched,
            "trace": self.trace(note),
        }
