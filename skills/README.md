# Skills（业务能力包）

本目录存放**可注册、可发现、可加载**的 skill 定义（manifest、规范文档、pipeline 说明）。

**不是**把各 Agent 的 system prompt 外置到这里——Agent 提示词仍写在各自的 `.py` 文件里。

| 目录 | 绑定 Agent | 说明 |
|------|-----------|------|
| [explainer-video-html](explainer-video-html/) | `video-agent` | HTML + MP3 讲解视频（规范、JSON 示例、pipeline） |

## 与 Agent 的关系

- **Agent**：运行时逻辑 + **提示词在 Python 中定义**
- **Skill**：能力包元数据（`skill.json`）、领域文档（`visual-spec.md` 等）、pipeline 步骤说明
- **BaseAgent**：提供 `list_skills()` / `load_skill_manifest()` / `run_skill()` 等**查看与加载**能力

## 目录结构

```
skills/{skill-id}/
  skill.json       # id、绑定 agent、docs、pipeline
  SKILL.md         # 人类可读说明
  visual-spec.md   # 可选：领域规范
  reference.md     # 可选：JSON 示例
```

加载入口：`BaseAgent.list_skills()` / `load_skill_manifest()` → `app.skills.loader`

## 与 `.cursor/skills/`

| 位置 | 用途 |
|------|------|
| **`skills/`** | 后端运行时注册与发现 |
| **`.cursor/skills/`** | Cursor IDE 辅助写代码 |
