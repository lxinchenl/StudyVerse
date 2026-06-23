"""LLM helpers for exercise-agent generate mode."""

from __future__ import annotations

import json
import re
from typing import Any

GENERATE_SYSTEM = """你是数据库课程练习题设计师。根据主题、对话与参考资料，输出一个 JSON 对象（不要 markdown）。

结构：
{
  "title": "题集标题",
  "topic": "知识点",
  "questions": [
    {
      "id": "q1",
      "topic": "子知识点",
      "difficulty": "easy | medium | hard",
      "question": "题干",
      "grading_type": "standard | rubric",
      "standard_answer": "标准答案（grading_type=standard 时必填）",
      "rubric": "评分标准条目，多条用分号分隔（grading_type=rubric 时必填）"
    }
  ]
}

规则：
- 输出 3~5 道题，覆盖基础判定、应用分析、分解/设计等不同角度
- grading_type=standard：有明确标准答案（填空、判断、唯一解）
- grading_type=rubric：开放作答，必须写 rubric（采分点），standard_answer 可留空
- 只能依据参考资料与主题，不可编造课件外的规范条文
- 使用简体中文
"""


def build_generate_prompt(
    *,
    topic: str,
    message: str,
    basis: str,
    profile: dict[str, Any],
    conversation: list[dict[str, Any]],
) -> str:
    weak = "、".join(profile.get("weak_points") or []) or "未知"
    conv_lines = [
        f"{row.get('role', 'user')}: {(row.get('content') or '')[:300]}"
        for row in conversation[-6:]
    ]
    conv_block = "\n".join(conv_lines) if conv_lines else "（无近期对话）"
    return (
        f"主题：{topic}\n"
        f"用户当前请求：{message}\n"
        f"用户薄弱点：{weak}\n\n"
        f"近期对话：\n{conv_block}\n\n"
        f"参考资料：\n{basis or '（无检索结果，请基于主题合理出题并标注依据不足）'}\n\n"
        "请输出练习题 JSON。"
    )


def parse_generated_exercises(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM 输出中未找到 JSON")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("练习题 JSON 必须是对象")
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions 不能为空")
    normalized: list[dict[str, Any]] = []
    for i, row in enumerate(questions, start=1):
        if not isinstance(row, dict):
            continue
        grading = str(row.get("grading_type") or "standard").strip().lower()
        if grading not in ("standard", "rubric"):
            grading = "standard"
        item = {
            "id": str(row.get("id") or f"q{i}"),
            "topic": str(row.get("topic") or data.get("topic") or ""),
            "difficulty": str(row.get("difficulty") or "medium"),
            "question": str(row.get("question") or "").strip(),
            "grading_type": grading,
            "standard_answer": str(row.get("standard_answer") or "").strip(),
            "rubric": str(row.get("rubric") or "").strip(),
        }
        if not item["question"]:
            continue
        if grading == "standard" and not item["standard_answer"]:
            item["grading_type"] = "rubric"
            item["rubric"] = item["rubric"] or "答案需覆盖题干核心要点；每命中一条得 20 分。"
        if grading == "rubric" and not item["rubric"]:
            item["rubric"] = "答案需条理清晰、概念准确；按采分点给分。"
        normalized.append(item)
    if not normalized:
        raise ValueError("未解析到有效题目")
    return {
        "title": str(data.get("title") or f"{data.get('topic', '练习')}题集"),
        "topic": str(data.get("topic") or ""),
        "questions": normalized,
    }
