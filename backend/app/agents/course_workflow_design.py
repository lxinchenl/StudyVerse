"""Prompts and parsers for course-workflow skill."""

from __future__ import annotations

import json
import re
from typing import Any

PLAN_SYSTEM = """你是课程编排专家。根据用户学习目标、画像与课程目录，设计一门「针对性系统课」。

输出唯一 JSON：
{
  "course_title": "如：关系代数系统课",
  "summary": "一两句话说明课程价值",
  "modules": [
    {
      "title": "第1讲：…",
      "objective": "学完能做什么",
      "chapter_key": "ch2 或空字符串",
      "estimated_minutes": 45,
      "topics": ["子主题1", "子主题2"]
    }
  ]
}

规则：
- modules 数量 2~3 讲，由浅入深
- 每讲 estimated_minutes 30~60
- 若目录有对应章节，填写 chapter_key（如第3章 → ch3）
- 不要编造目录中不存在的章节号
- 不在此步决定具体资源；每讲资源由讲次编排 Agent 自主 ReAct 决定
"""

MODULE_REACT_SYSTEM = """你是定制课「讲次资源编排 Agent」，采用 ReAct **自主**为本讲规划学习资源：决定生成什么、以什么顺序生成、何时结束。

你已看到本讲目标、用户画像、课程资料摘要，以及**已生成资源**（按学习顺序编号）。每轮只输出一个 JSON action。

## action 1) generate_resource — 生成下一项资源（顺序即学习顺序）

{
  "thought": "为何此刻生成此项、与上一项如何衔接",
  "action": "generate_resource",
  "type": "note | mindmap | video_script | exercise | code_lab",
  "title_hint": "建议资源标题",
  "topic": "检索/出题关键词",
  "brief": "给对应专家 Agent 的完整任务说明（写什么、覆盖范围、深度）",
  "learning_order_reason": "一句话说明为何放在当前顺序（如：先建立概念再练习）"
}

## action 2) finish_module — 本讲资源已够，结束编排

{"thought":"…","action":"finish_module"}

## 专家 Agent 与 type

- note — 结构化 Markdown 笔记
- mindmap — Mermaid 思维导图（适合总览）
- video_script — HTML 讲解动画（适合流程/demo）
- exercise — 生成练习题（非题库检索）
- code_lab — Python 实操题

## 自主编排原则

- **顺序由你决定**：典型路径「导入(note/video) → 结构化(note/mindmap) → 巩固(exercise/code_lab)」，但须按本讲目标灵活调整
- **按需生成**：不需要的类型不要生成；同一 type 可多次出现（如两个 note 各管一小节）
- **看 Observation 迭代**：上一项失败或已足够时，可改换 type 或 finish_module
- brief 必须具体，专家 Agent 仅依据 brief 生成
- 资料不足时减少项数，brief 限定范围，禁止编造课件外内容
- 本讲通常 2~6 项即可；至少生成 1 项后再 finish_module
- 只输出 JSON，不要其它文字
"""

RESOURCE_TYPES = ("note", "mindmap", "video_script", "exercise", "code_lab")

RESOURCE_LABELS = {
    "note": "笔记",
    "mindmap": "思维导图",
    "video_script": "讲解视频",
    "exercise": "练习题",
    "code_lab": "实操案例",
}

TYPE_TO_EXPERT: dict[str, str] = {
    "note": "note-agent",
    "mindmap": "mindmap-agent",
    "video_script": "video-agent",
    "exercise": "exercise-agent",
    "code_lab": "code-lab-agent",
}


def build_plan_prompt(
    *,
    topic: str,
    profile: dict[str, Any],
    catalog_summary: str,
    conversation: list[dict[str, Any]],
) -> str:
    conv = "\n".join(
        f"{r.get('role')}: {(r.get('content') or '')[:300]}"
        for r in conversation[-6:]
    )
    return (
        f"用户学习主题：{topic}\n"
        f"专业：{profile.get('major', '')}\n"
        f"课程：{profile.get('course', '')}\n"
        f"目标：{profile.get('goal', '')}\n"
        f"薄弱点：{', '.join(profile.get('weak_points') or [])}\n"
        f"近期主题：{', '.join(profile.get('recent_topics') or [])}\n\n"
        f"课程目录：\n{catalog_summary or '（未加载）'}\n\n"
        f"近期对话：\n{conv or '（无）'}\n\n"
        "请输出课程编排 JSON。"
    )


def build_module_react_prompt(
    *,
    course_topic: str,
    module: dict[str, Any],
    profile: dict[str, Any],
    material_summary: str,
    generated: list[dict[str, Any]],
    observations: list[str],
) -> str:
    topics = module.get("topics") or []
    gen_lines = []
    for item in generated:
        gen_lines.append(
            f"  {item.get('order')}. [{RESOURCE_LABELS.get(item.get('type'), item.get('type'))}] "
            f"{item.get('title')} (id={item.get('resource_id')})"
        )
    gen_block = "\n".join(gen_lines) if gen_lines else "  （尚无，请从第 1 项开始规划）"
    obs_block = "\n".join(f"- {o}" for o in observations[-12:]) if observations else "（首轮）"
    return (
        f"课程总主题：{course_topic}\n"
        f"本讲标题：{module.get('title')}\n"
        f"本讲目标：{module.get('objective')}\n"
        f"子主题：{', '.join(topics) if topics else '（无）'}\n"
        f"关联章节：{module.get('chapter_key') or '未指定'}\n\n"
        f"用户目标：{profile.get('goal', '')}\n"
        f"薄弱点：{', '.join(profile.get('weak_points') or [])}\n\n"
        f"资料摘要：\n{material_summary or '（资料较少）'}\n\n"
        f"已生成资源（学习顺序）：\n{gen_block}\n\n"
        f"Observation 历史：\n{obs_block}\n\n"
        f"下一顺序号将是 {len(generated) + 1}。请输出本轮 JSON action。"
    )


def parse_plan(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("课程编排 JSON 无效")
    data = json.loads(text[start : end + 1])
    modules = data.get("modules") or []
    if not modules:
        raise ValueError("modules 不能为空")
    cleaned: list[dict[str, Any]] = []
    for idx, mod in enumerate(modules[:3], start=1):
        cleaned.append(
            {
                "id": f"mod-{idx}",
                "title": str(mod.get("title") or f"第{idx}讲").strip(),
                "objective": str(mod.get("objective") or "掌握本讲核心内容").strip(),
                "chapter_key": str(mod.get("chapter_key") or "").strip(),
                "estimated_minutes": int(mod.get("estimated_minutes") or 45),
                "topics": [str(t).strip() for t in (mod.get("topics") or []) if str(t).strip()],
                "status": "pending",
                "resources": [],
            }
        )
    return {
        "course_title": str(data.get("course_title") or "定制系统课").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "modules": cleaned,
    }


def parse_module_react_action(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("action"):
        return None
    return data


def normalize_generate_task(action: dict[str, Any]) -> dict[str, Any] | None:
    if str(action.get("action") or "").strip().lower() != "generate_resource":
        return None
    rtype = str(action.get("type") or "").strip()
    if rtype not in RESOURCE_TYPES:
        return None
    brief = str(action.get("brief") or "").strip()
    if not brief:
        return None
    return {
        "type": rtype,
        "title_hint": str(action.get("title_hint") or RESOURCE_LABELS.get(rtype, rtype)).strip(),
        "topic": str(action.get("topic") or "").strip(),
        "brief": brief,
        "learning_order_reason": str(action.get("learning_order_reason") or "").strip(),
        "thought": str(action.get("thought") or "").strip(),
    }
