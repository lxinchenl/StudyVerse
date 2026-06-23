# Tutorial-to-Notes（EduAgent 改编版）

将课件资料或对话内容转为结构化 **Markdown** 学习笔记。本 skill 由 `note-agent` 通过 ReAct + Tools 执行，不依赖命令行或 PaddleOCR。

## 与 Hermes 原版的差异

| 原版 (Hermes) | 本项目 |
|---------------|--------|
| Shell 跑 Python 脚本 | Agent 调用 `tools/*` |
| PaddleOCR 识图 | **豆包视觉 API**（`doubao-vision-analyze`） |
| 输出 .docx | 输出 **Markdown** 存入资源库 |
| 预检索 Agent | **不预调检索**；笔记 Agent 自行 `list_catalog` / `extract_material` |

## Pipeline

1. **analyze_intent** — 判断 `conversation`（对话整理）或 `material`（课件笔记）
2. **conversation** — 直接 `compose_notes` 输出 Markdown
3. **material** — ReAct 循环：
   - `course-catalog-list` — 章节目录
   - `note-material-extract` — PDF/PPT 逐页文本+图片提取
   - `doubao-vision-analyze` — 图片内容理解（替代 OCR）
   - `note-structure-analyze` — 章节结构与图片页码归属
   - `compose_notes` — 四问筛料 + 压缩生成 Markdown

## 意图规则

- **conversation**：「把我们聊的写成笔记」「总结刚才讨论」
- **material**：「生成第3章笔记」「给我xxx章的笔记」；或对话一直在讨论某章后说「给我笔记」

## 输出格式

见 `references/notes-format.md`：层次标题、要点条目、每条概念后跟 `例：`、压缩比约 10:1。

## Tools

- `note-material-extract` — 提取课件过程数据
- `doubao-vision-analyze` — 豆包视觉理解单张图
- `note-structure-analyze` — 章节结构分析
- `course-catalog-list` / `course-document-read` — 目录与阅读（extract 已内置读取）
