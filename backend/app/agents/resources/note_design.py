"""Prompts and parsers for note-agent ReAct pipeline."""

from __future__ import annotations

import json
import re
from typing import Any

INTENT_SYSTEM = """你是笔记 Agent 的意图分析模块。根据用户当前请求与近期对话，判断笔记来源模式。

只输出一个 JSON 对象：
{
  "mode": "conversation" | "material",
  "title_hint": "建议笔记标题",
  "topic": "核心主题",
  "chapter_key": "如 ch3，仅 material 且能推断时填写，否则空字符串",
  "material_id": "如已知具体课件 id 则填写，否则空字符串",
  "course_hint": "课程名关键词，可选",
  "rationale": "一句话说明判断依据"
}

规则：
- conversation：用户要把**对话内容**整理成笔记，如「把我们刚才聊的写成笔记」「总结一下刚才的讨论」
- material：用户要基于**课件/章节/课程资料**生成笔记，如「生成第3章笔记」「给我数据库设计这章的笔记」；或对话中一直在讨论某章节且用户说「给我笔记」
- 不要依赖外部检索结果做判断，只根据用户话术与对话记录
- chapter_key 从「第N章」推断为 chN（如第3章 → ch3），与课程目录常见键一致
"""

NOTE_REACT_SYSTEM = """你是笔记 Agent，采用 ReAct 为用户生成 Markdown 学习笔记。你不使用外部检索 Agent；需要课件时自行调用工具。

## 工作模式（由上一步意图分析决定，见 Observation）

### A. conversation 模式
用户只要对话整理。流程：compose_notes → finish。

### B. material 模式
需结合课件资料。推荐流程：
1. list_catalog（若 chapter_key/material_id 未明确）
2. extract_material（指定 chapter_key 或 material_id）
3. vision_analyze（若有待理解图片）
4. analyze_structure
5. compose_notes
6. finish

## 可用 action（每次只输出一个 JSON）

1) list_catalog — 查看课程章节目录
   {"thought":"...","action":"list_catalog"}

2) extract_material — 提取课件过程数据（文本+图片）
   {"thought":"...","action":"extract_material","chapter_key":"ch3"}
   或 {"action":"extract_material","material_id":"..."}

3) vision_analyze — 对当前过程中「待理解」图片批量调用豆包视觉
   {"thought":"...","action":"vision_analyze"}

4) analyze_structure — 分析章节结构与图片页码归属
   {"thought":"...","action":"analyze_structure"}

5) compose_notes — 根据已收集的过程数据与对话补充生成最终 Markdown 笔记
   keep=A 的插图须写 `![说明](images/文件名.png)`；重点用 `<mark>标黄</mark>`
   {"thought":"...","action":"compose_notes"}

6) finish — 笔记已生成完毕
   {"thought":"...","action":"finish"}

只输出 JSON，不要其它文字。"""

NOTE_MARKDOWN_RULES = """
## Markdown 语法硬性规则（违反会导致渲染错乱，必须遵守）

### 表格
- 表格每行以 `|` 开头和结尾；列数各行必须相同
- 表头下一行必须是分隔行：`| --- | --- |`（列数与表头一致）
- 单元格内只写**纯文本**，禁止在单元格内写：代码块、`|` 竖线、换行、HTML 如 `<br>`
- **禁止**把 ```sql 代码块放进表格某一格；**禁止**在表格行中间开始/结束代码块
- 需要「类型 + 规则 + SQL 示例」时，用**两段式**：
  1) 先写仅含文字的简表（如「约束类型 | 核心规则」两列）；
  2) 表结束后空一行，再用 `**类型名 · 示例**` 小标题 + 独立代码块（见下方范例）

### 代码块
- 独占三行：第一行单独写 ```sql（或 ``` 语言名），中间是代码，最后一行单独写 ```
- 关闭用的 ``` 必须单独占一行，该行除 ``` 外不能有任何字符
- 一个代码块写完并关闭后，才能开始下一个代码块或表格
- 短命令可用行内 `CHECK(...)`，多行 CREATE TABLE 必须用围栏代码块

### 表格+代码正确范例（照此结构，不要合并成一张表）

| 约束类型 | 核心规则 |
| --- | --- |
| **域完整性** | 字段级：取值范围、格式、默认值、空值 |
| **实体完整性** | 主键唯一且非空 |
| **参照完整性** | 外键为空或等于被参照主键；可级联 |
| **用户自定义完整性** | CHECK 或触发器实现业务规则 |

**域完整性 · 示例**

```sql
CREATE TABLE S (
  S# CHAR(9) PRIMARY KEY,
  SSEX CHAR(2) CHECK (SSEX IN ('男', '女'))
);
```

**参照完整性 · 示例**

```sql
CREATE TABLE SC (
  S# CHAR(9),
  C# CHAR(7),
  FOREIGN KEY (C#) REFERENCES C(C#) ON DELETE CASCADE
);
```
"""

CONVERSATION_NOTE_SYSTEM = f"""你是学习笔记整理专家。将用户对话内容整理为排版精美的结构化 Markdown 笔记。

格式要求：
- 文首用 `> **摘要**：…` 引用块概括全文
- `# 笔记标题`；`## 大节`；`### 小节`
- 核心术语 **加粗**；单行命令用行内代码
- **重点标黄**：核心定义、关键结论、易错点用 `<mark>…</mark>` 包裹（每小节 1~3 处，勿滥用）
- 要点用列表；大节之间 `---`
- 对比类内容：先文字简表，SQL/长示例放在表外的独立代码块中
- 不编造未出现的内容；不用 emoji

{NOTE_MARKDOWN_RULES}
"""

MATERIAL_NOTE_SYSTEM = f"""你是课程笔记压缩专家，遵循 tutorial-to-notes 方法论输出排版精美的 Markdown 笔记。

内容与压缩：
- 依据过程文件章节结构逐节覆盖，不遗漏小节
- 四问筛料：核心定义、分类谱系、操作流程、一句话优劣、例子（例：）
- 压缩比约 10:1，要点式条目，不写长段落
- **重点标黄**：核心定义、关键结论、易错点、必背规则用 `<mark>…</mark>` 包裹（每小节 1~3 处，勿滥用）
- 图片 keep=A：流程/架构/模型图须用 `![说明文字](images/文件名.png)` 嵌入，禁止只写【图】文字占位
- 图片 keep=B：用文字概括；公式类 A 级也可写进正文
- 融合对话补充；资料不足处文首注明；不编造课件外条文

排版：
- 文首 `> **本章摘要**：…`；正文 `# 章节标题`
- `## 10.1 节名`；`### 小节名`；关键术语 **加粗**
- 多行 SQL 必须用围栏代码块，且不得写在表格单元格内
- 分类对比：表内只写类型与规则摘要，每个类型的 SQL 示例放在表后单独小节

{NOTE_MARKDOWN_RULES}
"""


def build_intent_prompt(*, message: str, conversation: list[dict[str, Any]]) -> str:
    conv_lines = [
        f"{row.get('role', 'user')}: {(row.get('content') or '')[:400]}"
        for row in conversation[-10:]
    ]
    conv_block = "\n".join(conv_lines) if conv_lines else "（无近期对话）"
    return f"用户当前请求：{message}\n\n近期对话：\n{conv_block}\n\n请输出意图 JSON。"


def parse_intent(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("意图 JSON 无效")
    data = json.loads(text[start : end + 1])
    mode = str(data.get("mode") or "conversation").strip().lower()
    if mode not in ("conversation", "material"):
        mode = "conversation"
    return {
        "mode": mode,
        "title_hint": str(data.get("title_hint") or "学习笔记").strip(),
        "topic": str(data.get("topic") or "").strip(),
        "chapter_key": str(data.get("chapter_key") or "").strip(),
        "material_id": str(data.get("material_id") or "").strip(),
        "course_hint": str(data.get("course_hint") or "").strip(),
        "rationale": str(data.get("rationale") or "").strip(),
    }


def parse_react_action(raw: str) -> dict[str, Any] | None:
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
    return data if isinstance(data, dict) and data.get("action") else None


def build_react_prompt(
    *,
    intent: dict[str, Any],
    message: str,
    observations: list[str],
    process_summary: str,
    conversation: list[dict[str, Any]],
) -> str:
    conv_lines = [
        f"{row.get('role', 'user')}: {(row.get('content') or '')[:300]}"
        for row in conversation[-8:]
    ]
    lines = [
        f"用户请求：{message}",
        f"意图模式：{intent.get('mode')}",
        f"建议标题：{intent.get('title_hint')}",
        f"主题：{intent.get('topic')}",
        f"chapter_key：{intent.get('chapter_key') or '（未指定）'}",
        f"material_id：{intent.get('material_id') or '（未指定）'}",
        f"判断依据：{intent.get('rationale')}",
        "",
        "近期对话（compose 时需融入其中的补充）：",
        "\n".join(conv_lines) if conv_lines else "（无）",
    ]
    if process_summary:
        lines.extend(["", "当前资料处理状态：", process_summary])
    if observations:
        lines.extend(["", "你的 Observation 历史："])
        lines.extend(f"- {o}" for o in observations[-12:])
    lines.append("\n请输出本轮 JSON action。")
    return "\n".join(lines)


def build_conversation_note_prompt(*, message: str, conversation: list[dict[str, Any]], intent: dict[str, Any]) -> str:
    conv_lines = [
        f"**{row.get('role', 'user')}**：{(row.get('content') or '')}"
        for row in conversation[-20:]
    ]
    return (
        f"用户请求：{message}\n"
        f"建议标题：{intent.get('title_hint')}\n\n"
        f"对话记录：\n" + "\n\n".join(conv_lines)
    )


def build_material_note_prompt(
    *,
    message: str,
    conversation: list[dict[str, Any]],
    intent: dict[str, Any],
    process_blob: str,
    format_doc: str,
    image_catalog: str = "",
) -> str:
    conv_supplement = [
        f"{row.get('role')}: {(row.get('content') or '')[:500]}"
        for row in conversation[-6:]
        if row.get("role") == "user"
    ]
    catalog_block = f"\n\n{image_catalog}\n" if image_catalog else ""
    return (
        f"用户请求：{message}\n"
        f"建议标题：{intent.get('title_hint')}\n"
        f"主题：{intent.get('topic')}\n\n"
        f"格式规范：\n{format_doc[:2000]}\n\n"
        f"{NOTE_MARKDOWN_RULES}\n\n"
        f"插图嵌入规则：keep=A 的图片必须用 Markdown 图片语法 `![caption](images/xxx.png)`；"
        f"禁止仅用【图】文字描述代替插图。重点内容用 `<mark>标黄</mark>`。\n"
        f"{catalog_block}"
        f"用户对话补充（融入笔记，资料未覆盖的部分）：\n"
        + ("\n".join(conv_supplement) if conv_supplement else "（无）")
        + f"\n\n课件过程数据：\n{process_blob[:96000]}\n\n"
        "请输出完整 Markdown 笔记正文（不要用 JSON 包裹）。"
        "再次强调：表格与代码块分开写，单元格内禁止出现 ``` 或竖线；"
        "keep=A 插图须嵌入，重点须 <mark> 标黄。"
    )


def parse_note_output(raw: str, *, fallback_title: str, fallback_topic: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence and fence.group(1).strip().startswith("{"):
        try:
            data = json.loads(fence.group(1).strip())
            markdown = str(data.get("markdown") or "").strip()
            if markdown:
                return {
                    "title": str(data.get("title") or fallback_title),
                    "topic": str(data.get("topic") or fallback_topic),
                    "summary": str(data.get("summary") or f"《{fallback_title}》学习笔记"),
                    "markdown": markdown,
                }
        except json.JSONDecodeError:
            pass
    title = fallback_title
    topic = fallback_topic
    first_line = text.splitlines()[0] if text else ""
    if first_line.startswith("# "):
        title = first_line[2:].strip()
    summary = f"《{title}》结构化笔记"
    return {"title": title, "topic": topic or title, "summary": summary, "markdown": text}
