# 系统设计说明书

## 1. 背景与目标

本系统面向高校课程个性化学习场景，解决学生学习资源繁杂、课程内容难以匹配个人基础、缺少实时辅导与学习效果闭环的问题。系统以《数据库系统原理》为样例课程（已内置 61 个 PPT/Word 课件作为初始知识库），通过对话式学习画像、知识图谱增强检索（KG-RAG）、多智能体协同编排和多模态资源生成，为学生提供个性化资源与学习路径，实现"因材施教"的数字化落地。

## 2. 总体架构

系统采用前后端分离的三层架构：

```
┌──────────────────────────────────────────────────────────────┐
│                        前端 (Next.js + React)                  │
│  对话工作台 / 资源库 / 学习路径 / 练习与代码沙箱 /               │
│  知识图谱 / 模型配置 / 智能体轨迹可视化                          │
└───────────────────────────────┬──────────────────────────────┘
                                │  SSE 流式 (text/event-stream)
┌───────────────────────────────▼──────────────────────────────┐
│                      后端 (FastAPI + Uvicorn)                  │
│                                                                │
│   ┌────────────────────────────────────────────────────────┐  │
│   │            AgentOrchestrator（编排层）                  │  │
│   │   MainAgent(ReAct) ──按需调用──▶ 9 个专家 Agent         │  │
│   └────────────────────────────────────────────────────────┘  │
│   ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│   │ KG-RAG 检索  │  │ 资源生成 Studio│  │ 画像/记忆/路径     │   │
│   │ Chroma+Neo4j │  │ 6 类资源生成器 │  │ 文件持久化        │   │
│   └──────────────┘  └───────────────┘  └──────────────────┘   │
└───────────────────────────────┬──────────────────────────────┘
                                │  LLMProvider 抽象
        ┌───────────────────────▼────────────────────────┐
        │  大模型层（可插拔）                                │
        │  Mock（离线）/ OpenAI 兼容（豆包 ARK）/ 星火（讯飞）│
        └─────────────────────────────────────────────────┘
```

- **前端**：Next.js + React，实现对话式输入、资源卡片化展示、学习路径、代码沙箱判题、知识图谱浏览、评估仪表盘和智能体 ReAct 轨迹可视化。
- **后端**：FastAPI 提供 REST 与 SSE 流式接口，负责智能体编排、KG-RAG 检索、资源生成、画像更新和评估。
- **知识库**：本地课程资料（`data/courses/{course-id}/materials/`），经文档解析后建立 Chroma 向量索引 + Neo4j 知识图谱，混合检索；图谱不可用时回退到 JSON。
- **模型**：通过 `LLMProvider` 抽象统一调用，默认 Mock Provider 可离线完整演示，生产环境接豆包 ARK（OpenAI 兼容），并预留讯飞星火接入。

## 3. 多智能体设计

系统采用"主 Agent + 专家 Agent"的 ReAct 协作架构，所有智能体统一实现 `BaseAgent` 接口（`app/interfaces/contracts.py`）。主 Agent 不直接生成内容，而是通过 ReAct 循环（Thought → action → Observation，最多 6 轮）按需路由到专家 Agent。

### 3.1 主 Agent（ReAct 编排器）

`MainAgent`（`app/agents/main_agent.py`）负责理解用户意图、规划调用顺序、整合专家产出。每轮可选 5 种 action：

| action | 说明 |
|--------|------|
| `reply` | 寒暄/无需查资料的直接回复 |
| `call_expert` | 调用一名专家 Agent（可多轮多次） |
| `call_tool` | 调用原子工具（课程目录、文档阅读、画像更新等） |
| `call_skill` | 触发绑定 Agent 的完整 pipeline（如定制系统课） |
| `finish` | 信息已足够，生成最终回答 |

ReAct 系统提示约束专家调用必须先具备课程资料（`ensure_material_basis`），无资料时禁止生成，从源头降低幻觉。

### 3.2 专家 Agent 注册表（9 个）

注册表见 `app/agents/registry.py`：

| 专家 Agent | 职责 | 赛题对应 |
|-----------|------|---------|
| `retrieval-agent` | 检索课程资料 + 知识图谱 1 跳关系 | 智能辅导、防幻觉 |
| `note-agent` | 生成结构化 Markdown 学习笔记（含图片嵌入、重点标黄） | 资源①讲解文档 |
| `mindmap-agent` | 基于检索资料生成 Mermaid 思维导图 | 资源②思维导图 |
| `exercise-agent` | 查找题库(search) / 基于资料生成练习题(generate) | 资源③练习题目 |
| `code-lab-agent` | 生成 Python 编程题，沙箱运行判题 | 资源④代码实操案例 |
| `video-agent` | 生成 HTML 讲解动画 + edge-tts 本地配音（分镜脚本驱动） | 资源⑤多模态教学视频 |
| `path-agent` | 单点知识补强路径（轻量规划，用于临时补齐） | 路径规划（辅助） |
| `course-workflow-agent` | 编排"定制系统课"：讲次 ReAct 自主决定每讲生成什么资源与顺序，写入持久化学习路径 | 路径规划（主）+ 多智能体协同 |
| `safety-agent` | 来源校验与内容安全审校 | 防幻觉、内容安全 |

> **多智能体协同与路径规划的关键体现**：①主 Agent 与 9 专家是显式分工的多角色；②`course-workflow-agent` 是系统学习路径的**真正生成者**——它内部用"讲次编排 Agent"二次 ReAct，每讲自主决定生成资源类型与顺序，再 `save_path` 写入持久化学习路径，前端 `/path` 展示；③`path-agent` 仅作为单点知识补强的轻量规划补充；④`note-agent`/`video-agent` 等资源专家自身也走 ReAct 子流程（如笔记 Agent：意图分析 → 取料 → 视觉理解 → 结构分析 → 生成）。

> 注：`app/learning/services.py` 中的 `RuleBasedLearningPathPlanner` / `RuleBasedLearningEvaluator` 为早期接口原型，已被融合进 `course-workflow-agent` + `path-agent` 的智能体化实现取代，当前不参与运行时调用链，保留作为面向对象扩展接口的样例参考。

### 3.3 资源类型（6 类，超出赛题"至少 5 种"要求）

`ResourceType` 枚举（`app/domain/models.py`）：`explanation`（笔记）、`mind_map`（思维导图）、`exercises`（练习题）、`reading`（拓展阅读）、`code_lab`（代码实操）、`video_script`（多模态讲解视频）。

## 4. 核心知识检索（KG-RAG）

`HybridRetrievalPipeline`（`app/infrastructure/kg_rag/hybrid_retriever.py`）实现 Plan-driven 混合检索：

```
MainAgent 给出改写后的 queries + 图谱 entities
        │
        ▼
1. 关键词检索（课程资料 chunk）──┐
2. Chroma 向量检索（bge-small）─┤── 合并去重 + 标题/路径加权 boost ──▶ ranked chunks
3. Neo4j 图谱 1 跳关系查询 ─────┘                                  ▼
                                                          附加 kg_context 关系三元组
```

- 向量检索用 Chroma + `BAAI/bge-small-zh-v1.5`；Neo4j 不可用时回退到 `kg_rag_demo` 预置的 JSON 图谱。
- 检索结果携带 `source` 与 `citations`，供下游生成与溯源。
- 这种"先检索后生成、无依据不生成"的模式是防幻觉的核心机制（详见第 7 节）。

## 5. 面向对象的扩展接口

核心扩展点均以抽象基类定义，便于替换：

| 扩展点 | 接口 | 当前实现 | 替换方向 |
|--------|------|---------|---------|
| 大模型 | `LLMProvider` | Mock / 豆包 ARK | 讯飞星火 |
| 检索器 | `Retriever` | `HybridRetrievalPipeline` | FAISS / Milvus |
| 画像抽取 | `ProfileExtractor` | `HeuristicProfileExtractor` | LLM 抽取 |
| 资源生成 | 资源 Agent（`BaseAgent` 子类） | 6 类生成器 | 新增 PPT / 实验报告 |
| 路径规划 | `LearningPathPlanner` | `RuleBasedLearningPathPlanner` | 强化学习/图搜索 |
| 学习评估 | `LearningEvaluator` | `RuleBasedLearningEvaluator` | 学情分析模型 |
| 安全审校 | `SafetyReviewAgent` + `ToxicContentDetector` | 规则级来源校验 | 训练有害内容检测模型 |

新增智能体只需实现 `BaseAgent` 并注册进 `AgentOrchestrator`（`app/core/dependencies.py`）。

## 6. 个性化学习画像

画像存储于 `data/users/{user_id}/user_profile.json`，至少覆盖赛题要求的 6 个维度（实际 7 个）：知识基础、学习目标、认知风格、易错点、学习偏好、时间投入、实践能力。

- **对话式抽取**：主 Agent 通过 `user-profile-update` 工具，由大模型从自然语言对话中抽取 `course / goal / recent_topics / weak_points` 等字段。
- **随学随新**：`user-profile-gather` 工具聚合对话历史、已生成资源主题、练习低分知识点等信号，输出"记忆整合 digest"供下一轮画像更新使用，避免重复索要信息。
- **记忆驱动**：画像、对话历史、工作记忆、短期资料上下文统一由 `MemoryService`（文件持久化）管理。

## 7. 防幻觉与内容安全

| 机制 | 实现位置 | 说明 |
|------|---------|------|
| 资料约束生成 | `ensure_material_basis` + ReAct 系统提示 | 资源类专家调用前必须已有课程资料，否则拒绝 |
| 强制溯源作答 | `_SUMMARIZE_SYSTEM` | 只依据检索资料回答，无依据明确说"未找到"，标注【资料N】 |
| 禁止编造条文 | 分镜/笔记系统提示 | "只能依据参考资料，不可编造规范条文、页码、章节号" |
| 来源字段保留 | `ResourceCard.sources` / 检索 `citations` | 每个资源卡片携带来源 |
| 安全审校 | `SafetyReviewAgent` | 检索为空时提醒；预留 `ToxicContentDetector` 敏感内容检测 |

## 8. 关键流程图：一次对话的执行链路

```
用户消息
   │
   ▼
POST /api/chat/stream ──▶ AgentOrchestrator.chat_stream (SSE)
   │
   ▼
MainAgent.react_loop (最多 6 轮 ReAct)
   │
   ├─[call_tool] course-catalog-list / course-document-read  (获取课程资料)
   ├─[call_expert] retrieval-agent   (KG-RAG 检索)
   ├─[call_expert] note/mindmap/exercise/code-lab/video-agent (生成 6 类资源)
   ├─[call_expert] path-agent        (规划学习路径)
   └─[finish]     summarize(检索资料 → 标注引用 → 作答)
   │
   ▼
SSE 推送 status/progress 事件 + done(最终回答+资源卡片+画像+ReAct轨迹)
   │
   ▼
前端：流式渲染回答 + 资源卡片 + 智能体轨迹面板
```
