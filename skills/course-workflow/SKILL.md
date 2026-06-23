# Course Workflow（定制系统课）

每讲资源由 **讲次编排 Agent ReAct 自主决定**：生成什么、以什么顺序生成、何时结束。

## 确认流程

1. 主 Agent 调用 `course-workflow-propose` → 返回结构化 JSON 卡片（`course_proposal_card`）
2. 前端展示可编辑卡片：同意 / 取消
3. 用户点击「同意」→ `course_workflow_action=confirm` + 编辑后的大纲 → **直接**执行 `course-workflow` skill（不经主 Agent ReAct 绕路）

## Pipeline

| 步骤 | 说明 |
|------|------|
| plan_course | LLM 编排 2~3 讲大纲 |
| module_react | 每讲 ReAct：Thought → generate_resource / finish_module |
| generate_resource | 按 Agent 决定的顺序调用专家，`brief` 为任务说明 |
| save_path | 写入学习路径（resources 含 `order` 字段） |

## 讲次 ReAct action

- `generate_resource` — 生成下一项（顺序 = 学习顺序）
- `finish_module` — 本讲足够，结束（须至少 1 项）

编排 Agent 每轮看到：资料摘要、已生成资源列表（带序号）、Observation 历史，据此自主规划下一项。
