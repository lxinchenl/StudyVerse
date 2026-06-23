# Mindmap：Mermaid 思维导图

**渲染库**：前端 [Mermaid.js](https://mermaid.js.org/syntax/mindmap.html)（项目已集成，无需新依赖）。

**交付物**：
- `mindmap.mmd` — Mermaid 源码
- 用户资源库 `type: mindmap` 条目
- 聊天窗口内嵌 `MindmapViewer` 组件

## Pipeline（mindmap-agent）

```
用户问题 + 近期对话 + RAG 资料
  → LLM 输出 JSON（title / topic / summary / mermaid）
  → mermaid-mindmap-render 规范化
  → 写入 data/generated_resources/mindmap/{id}/
  → 注册资源库 + 聊天 mindmaps 卡片
```

## Mermaid 语法要点

- 首行 `mindmap`
- 2 空格缩进层级
- 根节点 `root((中心))` 推荐
- 最多 4 层

## 主 Agent 调用

生成思维导图前应先 `retrieval-agent` 检索资料，再 `call_expert mindmap-agent`。
