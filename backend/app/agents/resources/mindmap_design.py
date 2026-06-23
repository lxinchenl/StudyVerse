"""LLM helpers for mindmap-agent — output Mermaid mindmap syntax."""

from __future__ import annotations

import json
import re
from typing import Any

MINDMAP_SYSTEM = """你是课程知识点思维导图设计师。根据用户问题、近期对话与参考资料，输出一个 JSON 对象（不要 markdown 包裹）。

结构：
{
  "title": "思维导图标题",
  "topic": "核心知识点",
  "summary": "一句话说明导图覆盖范围",
  "mermaid": "mindmap 语法全文（从 mindmap 行开始）"
}

mermaid 字段规则（Mermaid mindmap）：
- 第一行必须是 mindmap
- 第二行起用 2 空格缩进表示层级，最多 4 层（含根）
- 根节点写法：root((中心主题)) 或 root[中心主题]
- 子节点用中文短语，每条不超过 12 字为宜
- 只能依据参考资料，不可编造课件外的规范条文
- 不要输出 ``` 代码块标记

示例：
mindmap
  root((第二范式 2NF))
    定义
      消除部分依赖
      非主属性完全依赖候选键
    判定三步
      找主键
      对比依赖
      得出结论
    拆表
      消除冗余
"""


def build_mindmap_prompt(
    *,
    message: str,
    basis: str,
    profile: dict[str, Any],
    conversation: list[dict[str, Any]],
) -> str:
    weak = "、".join(profile.get("weak_points") or []) or "未知"
    conv_lines = [
        f"{row.get('role', 'user')}: {(row.get('content') or '')[:280]}"
        for row in conversation[-6:]
    ]
    conv_block = "\n".join(conv_lines) if conv_lines else "（无近期对话）"
    return (
        f"用户请求：{message}\n"
        f"用户薄弱点：{weak}\n\n"
        f"近期对话：\n{conv_block}\n\n"
        f"参考资料：\n{basis or '（无检索结果，请基于问题合理归纳，并提醒用户补充课件）'}\n\n"
        "请输出 JSON，mermaid 字段为完整 mindmap 源码。"
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:mermaid)?\s*([\s\S]*?)```", text)
    if fence:
        return fence.group(1).strip()
    return text


def parse_mindmap_payload(raw: str) -> dict[str, Any]:
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
        raise ValueError("mindmap JSON 必须是对象")
    mermaid = _strip_fences(str(data.get("mermaid") or ""))
    if not mermaid.lower().startswith("mindmap"):
        raise ValueError("mermaid 字段必须以 mindmap 开头")
    title = str(data.get("title") or data.get("topic") or "思维导图").strip()
    topic = str(data.get("topic") or title).strip()
    summary = str(data.get("summary") or f"{topic} 知识结构导图").strip()
    return {
        "title": title,
        "topic": topic,
        "summary": summary,
        "mermaid": mermaid,
    }
