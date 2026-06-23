# Course Workflow Propose

为主 Agent 生成「定制系统课」**讲次大纲**提案，不生成资源。用户同意后再 `call_skill course-workflow`；具体每讲生成哪些资源由 workflow 内编排 LLM 决定。

## 参数

- `topic` — 用户想系统学习的主题
- `course_id` — 课程库 id（默认 db-principles）

## 返回

- `proposal` — 课程 JSON（modules 2~3 讲）
- `summary` — 可直接展示给用户的大纲文本
