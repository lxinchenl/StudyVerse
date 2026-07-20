# user-profile-update

更新当前用户的 `data/users/{user_id}/user_profile.json` 中的学习画像字段：

- `course` — 正在学的课程
- `goal` — 学习目标
- `recent_topics` — 近期学习/讨论主题（列表）
- `weak_points` — 薄弱知识点（列表）

## 何时调用

用户说「更新画像」「同步画像」时：**禁止**让用户逐项填写；应先调用 `user-profile-gather` 读取原始记忆材料，再由主 Agent 自行提炼后调用本工具。

主 Agent 在对话中**发现用户信息有变化**时也应主动调用，例如：

- 用户说正在学哪门课、备考目标
- 用户明确某知识点「不懂」「混淆」「总错」
- 本轮深入讨论了某章节/主题，应记入 `recent_topics`
- 你发现了用户的薄弱点

不必等用户说「请更新画像」；有依据就更新，避免臆造。

## recent_topics 写法（重要）

- 只写 **4-30 字** 的知识点/章节/专题短语
- 示例：`["第2章 关系运算", "关系代数与演算"]`
- **禁止**写入：用户整句原话、助手称呼、memory/画像抱怨、确认按钮文案

## 调用示例

```json
{
  "thought": "用户提到正在复习第6章范式，且对2NF部分依赖仍困惑",
  "action": "call_tool",
  "tool": "user-profile-update",
  "input": {
    "course": "数据库系统原理",
    "recent_topics": ["第6章 关系模式规范化", "第二范式 2NF"],
    "weak_points": ["2NF 部分函数依赖判定"]
  }
}
```

仅改目标：

```json
{
  "action": "call_tool",
  "tool": "user-profile-update",
  "input": { "goal": "期末考试通过，重点攻克范式与 SQL" }
}
```

整表替换薄弱点（少用）：

```json
{
  "action": "call_tool",
  "tool": "user-profile-update",
  "input": {
    "weak_points": ["事务 ACID", "并发控制"],
    "list_mode": "replace"
  }
}
```

## 说明

- 未出现在 `input` 中的字段**保持不变**
- 默认 `list_mode=merge`：新主题/薄弱点与已有记录合并去重，各最多保留 10 条
- 写入后学习页侧栏「用户画像」与后续出题 Agent 会读取最新值
