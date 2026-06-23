# Tools（可调用工具包）

本目录描述 **MainAgent / Expert** 可调用的原子工具（TTS、渲染、静态播放等）。

| 目录 | 说明 |
|------|------|
| [user-profile-gather](user-profile-gather/) | 从记忆文件整合画像线索（只读） |
| [user-profile-update](user-profile-update/) | 更新用户学习画像（课程/目标/近期主题/薄弱点） |
| [user-me-update](user-me-update/) | 更新对话助手人设记忆（add/delete/rewrite） |
| [edge-tts-narration](edge-tts-narration/) | edge-tts 生成场景 MP3 |
| [explainer-html-render](explainer-html-render/) | storyboard → index.html |
| [explainer-play](explainer-play/) | bundle 静态播放 URL |

## 与 `skills/` 的区别

| 概念 | 职责 |
|------|------|
| **Skill** | 一整条业务能力（prompt + 规范 + 多步 pipeline） |
| **Tool** | 单步可复用函数（被 skill 或 MainAgent `call_tool` 调用） |

注册与查询：`BaseAgent.list_tools()` / `invoke_tool()` → `app.tools.registry.get_tool_registry()`
