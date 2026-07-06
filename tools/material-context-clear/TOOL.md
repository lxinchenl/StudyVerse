# material-context-clear

清空主 Agent 当前 ReAct 上下文中已加载的课程资料（`retrieval`）。

适用场景：
- 当前用户话题与已加载资料明显无关
- 已加载资料命中偏题，需重新检索/重读文档

建议：
- 清空后再执行 `call_expert retrieval-agent` 或 `call_tool course-document-read`
