"""LLM helpers for code-lab-agent — Python 编程题生成（类比 exercise-agent）。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.infrastructure.code_lab_script import normalize_challenge_codes, validate_lab_script

GENERATE_SYSTEM = """你是数据库课程 Python 编程题设计师。根据主题、对话与参考资料，输出一个 JSON 对象。

## 输出格式硬约束
- 只输出一个合法 JSON 对象，首字符必须是 `{`，末字符必须是 `}`。
- 禁止输出 Markdown 代码围栏，禁止输出 ```json，禁止在 JSON 前后添加解释、寒暄或分析。
- 所有多行字符串必须使用 `\\n` 转义换行，禁止在字符串内部直接换行。
- 字符串里的双引号必须转义为 `\\"`。
- 如果没有足够资料，也必须输出符合结构的 JSON，并在 question 的「### 背景」中说明依据不足。

结构：
{
  "title": "题集标题",
  "topic": "知识点",
  "challenges": [
    {
      "id": "c1",
      "topic": "子知识点",
      "difficulty": "easy | medium | hard",
      "question": "题干（Markdown 字符串，见下方排版规范）",
      "setup_code": "模块级初始化（见下方 setup 规范）",
      "starter_code": "仅含 def xxx(conn): 函数骨架 + 文件末尾一行 xxx(conn)",
      "solution_code": "仅含 def xxx(conn): 完整实现 + 文件末尾一行 xxx(conn)",
      "hint": "可选提示一句",
      "language": "python"
    }
  ]
}

## question 排版规范（硬性，前端按 Markdown 渲染）

question 必须使用 Markdown，按以下小节顺序组织，每节标题用 `###`：

### 背景
1~2 句说明考查点与场景。

### 原关系模式
- 写出**完整关系名**与**属性列表**，格式：`R(属性1, 属性2, …)`
- 明确标注：**主键**、**候选键**（如有）、**函数依赖**（如有）
- 涉及分解/范式判定时，必须写清「哪些非主属性部分/传递依赖于哪个键」

### 示例数据
- 用 Markdown 表格给出 **2~4 行** 有代表性的示例元组（含表头）
- 表格须覆盖判定所需的关键字与易错场景，不要空泛描述

### 目标结构 / 已知条件
- 若题目给出分解结果、子表、待校验对象，逐条列出每个子关系的模式
- 编号列表，一行一个子表，格式：`1. R1(…) — 简要说明`

### 编程任务
- 用有序列表写清步骤（如：1. 检查… 2. 统计… 3. 计算得分…）
- 评分规则、阈值、满分条件写具体数字

### 输出格式
- 直接写 stdout 样例，不要使用三反引号代码块，例如：
  `stdout 样例：\\nOrder_Info: 是\\nOrder_Item: 是\\nGoods_Info: 否`

禁止把以上所有内容挤在一个长段落；禁止省略原表属性名与示例数据。

## setup_code 规范

- **SQL/查询类**：import sqlite3、`conn = sqlite3.connect(':memory:')`、建表插数据、conn.commit()，须定义全局 conn
- **范式/模式/逻辑校验类**：可用 Python 结构描述模式与示例元组（如 dict/list），不必强行建 sqlite 表；仍须保证 solution 的 stdout 可判题
- starter_code 与 solution_code **不得**再 import sqlite3、不得 connect、不得 if __name__

starter/solution 模板：
- setup_code: `"import sqlite3\\nconn = sqlite3.connect(':memory:')\\n..."`
- starter_code: `"def solve(conn):\\n    cur = conn.cursor()\\n    # TODO\\n\\nsolve(conn)"`
- solution_code: `"def solve(conn):\\n    ...\\n\\nsolve(conn)"`

## 其他硬性规则

- 输出 2~4 道编程题，难度递进；题目须与数据库课程相关
- 判题方式：先执行 setup_code，再执行用户代码，**stdout 完全一致**即通过
- solution 的 stdout 只能有题目要求的输出，无调试 print
- 优先标准库 + sqlite3（SQL 题）；禁止联网、读写磁盘、subprocess
- 只能依据参考资料，不可编造课件外规范；资料不足时在背景中注明
- 使用简体中文题干
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
        f"参考资料：\n{basis or '（无检索结果，请基于主题设计通用 sqlite 编程题并标注依据不足）'}\n\n"
        "请输出一个合法 JSON 对象，不能输出 markdown 围栏或解释文字。\n"
        "每题 question 必须是一个 JSON 字符串，内部换行统一写成 \\n，且含 ### 背景、### 原关系模式、"
        "### 示例数据、### 编程任务、### 输出格式。"
        "涉及范式/分解/模式校验时，原表须写清关系名、全部属性、主键与函数依赖，并给出 2~4 行示例元组。"
        "确保 setup_code、starter_code、solution_code 都是合法 JSON 字符串，代码换行也必须写成 \\n。"
        "确保 solution_code 运行后 stdout 稳定、可复现。"
    )


def parse_generated_code_labs(raw: str) -> dict[str, Any]:
    data = _loads_json_object(raw)
    if not isinstance(data, dict):
        raise ValueError("编程题 JSON 必须是对象")
    challenges = data.get("challenges")
    if not isinstance(challenges, list) or not challenges:
        raise ValueError("challenges 不能为空")
    normalized: list[dict[str, Any]] = []
    for i, row in enumerate(challenges, start=1):
        if not isinstance(row, dict):
            continue
        question = str(row.get("question") or "").strip()
        solution = str(row.get("solution_code") or "").strip()
        if not question or not solution:
            continue
        item = normalize_challenge_codes(
            {
                "id": str(row.get("id") or f"c{i}"),
                "topic": str(row.get("topic") or "").strip(),
                "difficulty": str(row.get("difficulty") or "medium").strip().lower(),
                "question": question,
                "setup_code": str(row.get("setup_code") or "").strip(),
                "starter_code": str(row.get("starter_code") or "").strip(),
                "solution_code": solution,
                "hint": str(row.get("hint") or "").strip(),
                "language": str(row.get("language") or "python").strip().lower(),
            }
        )
        setup = item["setup_code"]
        for label, code in (("starter_code", item["starter_code"]), ("solution_code", item["solution_code"])):
            err = validate_lab_script(setup, code)
            if err:
                raise ValueError(f"题目 {item['id']} {label} 无效: {err}")
        normalized.append(item)
    if not normalized:
        raise ValueError("无有效编程题")
    title = str(data.get("title") or "数据库编程练习").strip()
    topic = str(data.get("topic") or title).strip()
    return {"title": title, "topic": topic, "challenges": normalized}


def _loads_json_object(raw: str) -> Any:
    text = raw.strip()
    if not text:
        raise ValueError("LLM 输出为空")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for block in _json_fence_blocks(text):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

    for candidate in _balanced_json_objects(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    if "{" not in text or "}" not in text:
        raise ValueError("LLM 输出中未找到 JSON")
    raise ValueError("LLM 输出包含 JSON 片段，但不是合法 JSON")


def _json_fence_blocks(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"```json\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    ]


def _balanced_json_objects(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None

    return candidates
