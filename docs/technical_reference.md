# StudyVerse 技术参考文档

本文档面向开发者，详细说明 StudyVerse 的系统架构、核心模块、数据流、API 与部署方式。配合 [system_design.md](./system_design.md)（赛题背景与设计理念）和 [development.md](./development.md)（开发环境）使用。

---

## 目录

1. [系统总览](#1-系统总览)
2. [技术栈与依赖](#2-技术栈与依赖)
3. [目录与数据布局](#3-目录与数据布局)
4. [后端架构](#4-后端架构)
5. [多智能体系统](#5-多智能体系统)
6. [记忆与上下文](#6-记忆与上下文)
7. [KG-RAG 检索](#7-kg-rag-检索)
8. [对话与流式推送](#8-对话与流式推送)
9. [定制课工作流](#9-定制课工作流)
10. [学习路径与资源](#10-学习路径与资源)
11. [前端架构](#11-前端架构)
12. [API 参考](#12-api-参考)
13. [配置与环境变量](#13-配置与环境变量)
14. [部署与运维](#14-部署与运维)
15. [扩展开发指南](#15-扩展开发指南)

---

## 1. 系统总览

StudyVerse 采用前后端分离架构：Next.js 前端通过 REST 与 SSE 与 FastAPI 后端通信；后端以 `AgentOrchestrator` 为入口，驱动 `MainAgent` ReAct 循环，按需调用专家 Agent、原子 Tool 与 Skill 流水线，生成学习资源并更新用户画像与学习路径。

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 (Next.js 15 + React 19)                 │
│  /learn 对话  /path 学习路径  /courses 阅读  /resources 工坊     │
│  background-chat.ts 全局聊天状态  SSE 事件解析                      │
└────────────────────────────┬────────────────────────────────────┘
                             │  REST + SSE (text/event-stream)
┌────────────────────────────▼────────────────────────────────────┐
│                    后端 (FastAPI + Uvicorn)                       │
│  routes.py ──▶ AgentOrchestrator ──▶ MainAgent.react_loop        │
│       │              │                      │                     │
│       │              │         ┌───────────┼───────────┐         │
│       │              │         ▼           ▼           ▼         │
│       │              │    9 Experts    Tools      Skills         │
│       │              ▼                                           │
│       │         FileMemoryService / PathService / KG-RAG         │
└───────┼──────────────────────────────────────────────────────────┘
        │
        ▼
  data/users  data/courses  data/kg  data/generated_resources
```

**请求鉴权**：多数 API 要求请求头 `X-User-Id: {user_id}`（`backend/app/api/deps.py`），由前端登录后将用户 ID 写入 localStorage 并随请求携带。当前为文件型用户体系，非 JWT Session。

---

## 2. 技术栈与依赖

### 2.1 后端

| 组件 | 版本/选型 | 用途 |
|------|-----------|------|
| Python | 3.10+ | 运行时 |
| FastAPI | ≥0.111 | Web 框架 |
| Uvicorn | ≥0.30 | ASGI 服务器 |
| Pydantic | v2 | 请求/响应校验 |
| ChromaDB | ≥0.5 | 向量检索 |
| sentence-transformers | ≥3.0 | 嵌入 `BAAI/bge-small-zh-v1.5` |
| Neo4j | ≥5.0（可选） | 知识图谱 |
| openai SDK | ≥1.40 | OpenAI 兼容 LLM 调用 |
| edge-tts | ≥6.1 | 讲解视频配音 |
| python-pptx / python-docx | — | 课件解析 |

### 2.2 前端

| 组件 | 版本/选型 | 用途 |
|------|-----------|------|
| Next.js | 15.x | App Router、SSR/CSR |
| React | 19.x | UI |
| TypeScript | 5.7+ | 类型安全 |
| Tailwind CSS | 4.x | 样式 |
| react-markdown + KaTeX | — | 笔记/Markdown 渲染 |
| Mermaid | 11.x | 思维导图 |
| Framer Motion | 12.x | 动画 |
| docx-preview | — | Word 课件预览 |

### 2.3 基础设施

- **Docker Compose**：`backend`、`frontend`、`nginx` 三服务
- **nginx**（`deploy/nginx.conf`）：`/api/` 代理至 backend:8000，`/` 代理至 frontend:3000；`client_max_body_size 100M`，读写超时 600s（适配长时 LLM 生成）

---

## 3. 目录与数据布局

### 3.1 代码目录

```text
backend/app/
├── main.py                 # create_app()，Chroma sqlite 补丁
├── api/
│   ├── routes.py           # 全部 REST + SSE 端点
│   └── deps.py             # require_user_id
├── agents/
│   ├── orchestrator.py     # AgentOrchestrator
│   ├── main_agent.py       # ReAct 主 Agent
│   ├── chat_stream.py      # SSE 事件打包
│   ├── course_workflow_agent.py
│   ├── retrieval_agent.py, path_agent.py, safety_agent.py
│   ├── resource_studio.py, studio_hub.py
│   ├── registry.py         # EXPERT_AGENTS, MAX_REACT_STEPS=6
│   ├── prompt_blocks.py    # 系统提示拼装（含 me 人格）
│   └── resources/          # note, mindmap, exercise, video, code_lab
├── core/
│   ├── config.py           # Settings (EDU_AGENT_*)
│   └── dependencies.py     # DI：orchestrator, retriever, llm
├── domain/
│   ├── models.py           # ResourceType 等
│   └── schemas.py          # ChatRequest, ChatMessageOut 等
├── infrastructure/
│   ├── memory_service.py   # FileMemoryService
│   ├── learning_path_store.py
│   ├── kg_rag/             # hybrid_retriever, chroma, neo4j
│   ├── llm_config_service.py
│   ├── python_sandbox.py
│   └── profile_tools.py    # user-profile-gather/update
├── interfaces/contracts.py # BaseAgent, LLMProvider, MemoryService
├── llm/providers.py        # Mock / OpenAICompatible
├── services/
│   ├── app_services.py     # Course, Path, Practice, Resource
│   ├── chat_store.py       # 消息记录构建
│   ├── material_context.py
│   └── reader_context.py   # 阅读器上下文
└── tools/                  # 工具注册表与 handler

frontend/
├── app/                    # 页面（learn, path, courses, resources…）
├── components/
│   ├── chat/               # ReActSteps, CourseProposalCard, MainAgentContextModal
│   ├── reader/             # DocumentReader, ReaderChatPanel
│   ├── path/               # LearningResourceModal
│   ├── studio/             # ResourceOffice, PixelOfficeCanvas
│   └── exercise/, code-lab/, mindmap/, explainer/, note/
└── lib/
    ├── api.ts              # 全部 API 封装 + sendChatStream
    ├── background-chat.ts  # 全局聊天状态（learn + reader 共享）
    ├── types.ts
    └── llm-models.ts       # 前端可选模型列表
```

### 3.2 运行时数据（`data/`）

| 路径 | 说明 |
|------|------|
| `data/users/{user_id}/user_profile.json` | 学习画像 |
| `data/users/{user_id}/me.json` | 助手人格（昵称、语气、边界） |
| `data/users/{user_id}/conversation_memory/{date}.json` | 按日对话历史 |
| `data/users/{user_id}/memory/*.json` | 显式长期记忆条目 |
| `data/users/{user_id}/working_memory.json` | ReAct 规划任务与轨迹 |
| `data/users/{user_id}/learning_paths.json` | 定制系统课 |
| `data/users/{user_id}/practice_attempts.json` | 练习作答记录 |
| `data/users/{user_id}/reading_progress.json` | 阅读进度 |
| `data/courses/{course_id}/` | 课程元数据 + materials/ 课件 |
| `data/kg/chroma/` | Chroma 持久化 |
| `data/kg/data/subgraphs.json` | Neo4j 不可用时的图谱回退 |
| `data/generated_resources/` | Agent 生成的笔记/导图/练习等 |
| `data/settings/llm.json` | 运行时 LLM 配置（gitignore） |
| `data/cache/course_material_chunks.json` | 课件分块缓存 |

### 3.3 Skills 与 Tools

- **Tool**（`tools/*/TOOL.md` + `tool.json`）：原子操作，由 MainAgent `call_tool` 调用。例：`course-catalog-list`、`user-profile-gather`、`course-workflow-propose`、`material-context-clear`。
- **Skill**（`skills/*/skill.json`）：多步流水线，由 MainAgent `call_skill` 触发并绑定专家 Agent。例：`course-workflow` → `course-workflow-agent`。

---

## 4. 后端架构

### 4.1 应用入口

`backend/app/main.py` 中 `create_app()`：
- 挂载 CORS（`Settings.cors_origins`）
- 注册 `api/routes.py` 路由，前缀 `/api`
- 可选：为 Chroma 打 `pysqlite3` 补丁（Docker Python 3.10-slim）

### 4.2 依赖注入

`backend/app/core/dependencies.py` 的 `get_orchestrator()` 组装：
- `MainAgent`（注入 LLM、Memory、Retriever）
- 9 个专家 Agent 实例
- `FileMemoryService`

LLM 配置变更时调用 `reload_llm_dependencies()` 刷新 Provider。

### 4.3 服务层

| 服务 | 文件 | 职责 |
|------|------|------|
| `CourseService` | `app_services.py` | 课程目录、章节、文档、阅读进度 |
| `PathService` | `app_services.py` | 定制课列表、详情、进度计算 |
| `PracticeService` | `app_services.py` | 练习列表、提交、画像反哺 |
| `ResourceService` | `app_services.py` | 资源库 CRUD、生成编排入口 |
| `AuthService` | `auth_service.py` | 注册/登录（文件用户表） |

---

## 5. 多智能体系统

### 5.1 AgentOrchestrator

文件：`backend/app/agents/orchestrator.py`

**非流式** `chat()` 与 **流式** `chat_stream()` 均进入 `_execute_chat()`：

1. 组装 `context`：`user_id`、`message`、`course_id`、`document_id`、`selected_text`、画像、对话、资料上下文
2. `preload_material_context()`：合并分桶后的短期资料摘要
3. `preload_reader_context()`：阅读器场景注入选中文本/文档上下文
4. 若 `course_workflow_action` 为 `confirm`/`cancel`：调用 `memory.patch_proposal_card_status()` 更新历史卡片状态
5. `await main_agent.react_loop(context, experts)`
6. `build_user_record` / `build_assistant_record` 持久化本轮对话
7. 流式场景通过 `event_sink` 推送 `chat_stream` 事件

### 5.2 MainAgent ReAct

文件：`backend/app/agents/main_agent.py`  
最大步数：`MAX_REACT_STEPS = 6`（`registry.py`）

每轮 LLM 输出 JSON，包含 `thought` 与 `action`：

| action | 行为 |
|--------|------|
| `reply` | 直接回复（寒暄、无需查资料） |
| `call_expert` | 调用一名专家，传入 `expert` 名与 `input` |
| `call_tool` | 调用原子工具，如 `user-profile-gather` |
| `call_skill` | 触发 Skill，如 `course-workflow` |
| `finish` | 结束循环，进入 summarize 生成最终回答 |

**系统提示构成**（`prompt_blocks.py`）：
- ReAct 规则与专家/工具列表
- 用户 `me` 人格块
- 用户消息、画像、今日对话（有字数上限）、资料摘要、检索 observation

**资料门禁**：`ensure_material_basis()` 在调用 note/mindmap/exercise/code_lab/video 等专家前检查是否已有课程 chunks；无资料则拒绝生成。

### 5.3 专家 Agent（9 个）

| 名称 | 类/文件 | 职责 |
|------|---------|------|
| `retrieval-agent` | `RetrievalAgent` | 混合检索，返回 chunks + kg_context |
| `note-agent` | `NoteAgent` | Markdown 笔记，支持图片嵌入与 vision 分析 |
| `mindmap-agent` | `MindmapAgent` | Mermaid 思维导图 |
| `exercise-agent` | `ExerciseAgent` | 题库检索或基于资料出题 |
| `code-lab-agent` | `CodeLabAgent` | Python 编程题 + 沙箱判题 |
| `video-agent` | `VideoAgent` | HTML 分镜讲解 + edge-tts |
| `path-agent` | `PathPlanningAgent` | 单点知识补强路径（轻量） |
| `course-workflow-agent` | `CourseWorkflowAgent` | 定制系统课全流程 |
| `safety-agent` | `SafetyReviewAgent` | 来源与安全审校 |

资源专家多数内部仍有子 ReAct 或分步 pipeline（如笔记：取料 → 结构分析 → 生成）。

### 5.4 Resource Studio（独立生成）

不经过主对话时，前端资源工坊调用：
- `POST /resources/generate` 或 `/resources/generate/stream`
- `ResourceStudioOrchestrator`（`resource_studio.py`）
- 可选 `studio_hub.py` MsgHub 多 Agent 讨论

---

## 6. 记忆与上下文

实现：`FileMemoryService`（`memory_service.py`）

### 6.1 分层记忆

| 类型 | 存储 | 读写方式 |
|------|------|----------|
| 学习画像 | `user_profile.json` | `get_profile` / `update_profile`；工具 `user-profile-update` |
| 助手人格 | `me.json` | 工具 `user-me-update`；注入 ReAct system |
| 对话历史 | `conversation_memory/*.json` | `append_chat_turn`；`get_recent_conversation` 按日期正序合并后取最近 N 条 |
| 工作记忆 | `working_memory.json` | ReAct 产生的 planner_tasks、traces |
| 显式记忆 | `memory/*.json` | 用户声明需长期记住的事实 |
| 短期资料 | context 内 `retrieval` / material buckets | `material_context.py` 分桶合并；工具 `material-context-clear` 清空 |

### 6.2 画像更新流程

1. MainAgent 调用 `user-profile-gather`：返回**原始**近期对话与资源主题等材料，不做解析
2. MainAgent 根据材料决定是否调用 `user-profile-update` 写入结构化字段
3. 练习提交时 `PracticeService` 可自动更新 `frequent_errors`

### 6.3 对话历史一致性

- 确认定制课卡片时：`patch_proposal_card_status()` 将历史中 `pending` 卡片改为 `confirmed`/`cancelled`
- 工作流完成后的助手消息不再重复附带 `course_proposal_card`
- 前端 `normalizeChatHistory()` 在加载历史时根据「确认/取消」用户消息修正卡片状态

### 6.4 阅读器上下文

`reader_context.py`：当 `document_id` 或阅读器传入上下文时，将当前文档与选中内容注入 MainAgent user prompt。阅读器侧边栏发送时，编辑框内容作为完整 `message` 发送（非单独 `selected_text` 字段）。

---

## 7. KG-RAG 检索

实现：`HybridRetrievalPipeline`（`infrastructure/kg_rag/hybrid_retriever.py`）

```
MainAgent / retrieval-agent 提供 queries + entities
        │
        ├─▶ 关键词匹配（course material chunks）
        ├─▶ Chroma 向量检索（bge-small-zh）
        └─▶ Neo4j 1-hop（或 JSON subgraphs 回退）
        │
        ▼
   合并、去重、打分排序 → ranked chunks + kg_context + citations
```

- 课件由 `document_parser.py` 解析 PPT/Word，分块后写入缓存与 Chroma
- 检索结果进入 `context["retrieval"]`，供 summarize 与资源生成引用
- 防幻觉：summarize 系统提示要求仅依据【资料N】作答，无依据明确说明

---

## 8. 对话与流式推送

### 8.1 SSE 端点

`POST /api/chat/stream`  
请求体（`ChatRequest`）主要字段：

```json
{
  "message": "用户消息",
  "course_id": "db-principles",
  "document_id": "可选，阅读器文档 ID",
  "course_workflow_action": "confirm | cancel",
  "course_proposal": { "course_title": "...", "modules": [] }
}
```

### 8.2 事件类型

打包逻辑：`chat_stream.py`

| type | 内容 |
|------|------|
| `status` | 阶段文案，如「主 Agent 开始 ReAct 推理…」 |
| `progress` | `react_steps`、`agent_traces`、`main_context`、增量资源卡片等 |
| `answer_start` / `answer_delta` | 最终回答流式 token（模拟分块） |
| `done` | 完整 `messages`、更新后 `profile` |
| `error` | 错误信息 |

### 8.3 前端消费

- `lib/api.ts`：`sendChatStream()` 解析 SSE
- `lib/background-chat.ts`：
  - `initializeBackgroundChat()` 拉取服务端历史（不依赖 sessionStorage 中的 messages）
  - `startBackgroundChat()` 发送消息并 `applyStreamEvent` 更新 UI
  - `/learn` 与 `ReaderChatPanel` 共用同一 snapshot

---

## 9. 定制课工作流

### 9.1 交互流程

```
用户：「我想系统学关系代数」
    │
    ▼
MainAgent → call_tool course-workflow-propose
    │
    ▼
SSE 返回 course_proposal_card（status: pending）
    │
    ▼
用户点击「确认生成定制系统课」
    │
    ▼
POST /chat/stream { message: "确认...", course_workflow_action: "confirm", course_proposal: {...} }
    │
    ▼
patch_proposal_card_status(confirmed) → call_skill course-workflow
    │
    ▼
CourseWorkflowAgent：plan_course → 每讲 module_react → dispatch 资源专家 → save_learning_path
    │
    ▼
学习路径写入 learning_paths.json，前端 /path 展示
```

### 9.2 CourseWorkflowAgent

文件：`course_workflow_agent.py`  
绑定 Skill：`skills/course-workflow/skill.json`

每讲内部 ReAct（最多 10 步）决定生成哪些资源类型及顺序，结果含 `learning_order_reason` 字段供路径页展示。

---

## 10. 学习路径与资源

### 10.1 路径 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/path/courses` | 定制课摘要列表（含进度） |
| GET | `/path/courses/{course_id}` | 讲次、目标、资源引用列表 |
| GET | `/path` | 兼容旧版扁平步骤 |

### 10.2 路径页 UI

- `/path/[courseId]/page.tsx`：时间线折叠讲次，横向资源轨道
- 资源卡片：复用 `public/card/` 下角色图与 logo（`operator-card` 风格），含 3D 悬停与 logo overlay 动效
- 点击卡片：`LearningResourceModal` 按类型加载笔记/导图/视频/练习/代码实操

### 10.3 资源类型与存储

`ResourceType`（`domain/models.py`）与前端 `RESOURCE_TYPE_LABELS` 对应：

| 类型 | 说明 | 典型存储 |
|------|------|----------|
| `note` | 讲解笔记 | `generated_resources/note/` |
| `mindmap` | Mermaid 导图 | `generated_resources/mindmap/` |
| `exercise` | 练习题集 | `generated_resources/exercises/` |
| `code_lab` | Python 实操 | `generated_resources/code_lab/` |
| `video_script` | HTML 讲解 + MP3 | explainer 目录 + `/explainer/play/` |
| `reading` | 拓展阅读 | 关联文档或生成文本 |

---

## 11. 前端架构

### 11.1 路由与布局

- `app/layout.tsx`：`AuthProvider`、`AuthGuard`、`UiPreferencesInit`
- `components/layout/AppShell.tsx` + `Sidebar.tsx`：统一壳与导航

### 11.2 关键模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 全局聊天 | `lib/background-chat.ts` | 跨页面聊天状态、历史规范化 |
| API | `lib/api.ts` | 所有后端调用、类型映射 |
| 对话 UI | `learn/page.tsx` | 主工作台 |
| 阅读器 | `DocumentReader.tsx`, `ReaderChatPanel.tsx` | 课件预览 + 浮动可缩放对话面板 |
| 路径 | `path/[courseId]/page.tsx` | 讲次时间线 + 资源卡片 |
| 工坊 | `ResourceOffice.tsx`, `background-resource-office.ts` | 像素办公室资源生成 |
| 上下文调试 | `MainAgentContextModal.tsx` | 查看 MainAgent System/User prompt |
| ReAct 展示 | `ReActSteps.tsx` | 推理步骤可视化 |

### 11.3 模型选择

`lib/llm-models.ts` 定义前端可选模型（豆包、DeepSeek V4、GLM-5、Mock 等），通过 `PUT /system/llm-config` 同步后端。`deepseek-v4-pro` 系列在后端走 Responses API + `web_search`。

### 11.4 样式

全局样式 `app/globals.css`，含学习路径、资源卡片、阅读器、聊天面板等 BEM 风格类名。资源卡片动效通过 CSS 变量 + `onMouseMove` 更新 `--card-rotate-*`、`--overlay-*` 实现，与 `card/operator-card.html` 行为对齐。

---

## 12. API 参考

前缀：`/api`  
鉴权：Header `X-User-Id`（除 `/health`、`/auth/*` 等公开接口）

### 12.1 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/system/status` | Chroma、Neo4j、LLM 状态 |
| GET/PUT | `/system/llm-config` | LLM 配置 |
| POST | `/system/llm-config/test` | 测试连通性 |

### 12.2 认证与用户

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录 |
| GET | `/auth/me` | 当前用户 |
| GET | `/profile` | 学习画像 |
| POST | `/users/uploads` | 文件上传 |

### 12.3 课程与文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/courses` | 课程列表 |
| GET | `/courses/{id}/chapters` | 章节树 |
| GET | `/courses/{id}/documents` | 文档列表 |
| GET | `/documents/{id}` | 文档元数据 |
| GET | `/documents/{id}/file` | 原始文件流 |
| POST | `/documents/{id}/progress` | 更新阅读进度 |

### 12.4 对话与记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat` | 非流式对话 |
| POST | `/chat/stream` | **SSE 流式对话** |
| GET | `/chat/history` | 历史消息 |
| DELETE | `/chat/history` | 清空历史 |
| POST | `/memory/clear-short-term` | 清空短期/工作记忆 |
| GET | `/chat/main-context` | 调试：当前 MainAgent 上下文 |

### 12.5 资源与生成

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/resources` | 资源列表 |
| GET/DELETE | `/resources/{id}` | 详情/删除 |
| POST | `/resources/generate` | 批量生成 |
| POST | `/resources/generate/stream` | 流式生成 |
| GET | `/explainer/play/{token}/{path}` | 讲解视频静态资源 |
| GET | `/note/assets/{resource_id}/{filename}` | 笔记内嵌图片 |

### 12.6 练习与代码实验

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/practice/resources` | 可练习资源 |
| GET | `/practice/questions` | 题目列表 |
| POST | `/practice/submit` | 提交作答 |
| GET | `/code-lab/set` | 代码题集 |
| POST | `/code-lab/run` | 沙箱运行 |
| POST | `/code-lab/submit` | 提交判题 |

### 12.7 学习路径

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/path` | 扁平路径步骤 |
| GET | `/path/courses` | 定制课列表 |
| GET | `/path/courses/{course_id}` | 定制课详情 |

### 12.8 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge-graph` | 图谱节点与边 |
| GET | `/workbench` | 工作台任务 |

### 12.9 流式请求示例

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-User-Id: demo-user" \
  -d '{"message":"帮我生成第3章的思维导图","course_id":"db-principles"}'
```

---

## 13. 配置与环境变量

`Settings` 类：`backend/app/core/config.py`，环境变量前缀 `EDU_AGENT_`。

| 变量 | 说明 | 默认 |
|------|------|------|
| `EDU_AGENT_LLM_PROVIDER` | `mock` / `openai_compatible` | 有 `ARK_API_KEY` 时为后者 |
| `EDU_AGENT_LLM_BASE_URL` | API Base | `https://ark.cn-beijing.volces.com/api/v3` |
| `EDU_AGENT_LLM_MODEL` | 模型 ID | `doubao-seed-2-0-lite-260428` |
| `ARK_API_KEY` | 火山引擎密钥 | — |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | 图谱连接 | 可选 |
| `EDU_AGENT_CHROMA_COLLECTION` | Chroma 集合名 | `edu_agent` |
| `EDU_AGENT_EMBED_MODEL_PATH` | 嵌入模型 | `BAAI/bge-small-zh-v1.5` |

路径类设置：`users_dir`、`courses_dir`、`chroma_dir`、`resources_dir`、`skills_dir`、`tools_dir` 等均可在 Settings 中覆盖。

前端：`NEXT_PUBLIC_API_BASE`（生产 Docker 中常设为公网 `/api` 地址）。

---

## 14. 部署与运维

### 14.1 Docker Compose

```bash
docker compose up --build
```

Volume 挂载保证用户数据、课程、生成资源、知识库、skills/tools 在容器重建后保留。

### 14.2 生产热更新（不重装依赖）

```bash
# 后端单文件
docker cp backend/app/agents/orchestrator.py studyverse-backend-1:/app/app/agents/orchestrator.py
docker restart studyverse-backend-1

# 前端
docker cp frontend/app/path/[courseId]/page.tsx studyverse-frontend-1:/app/app/path/[courseId]/page.tsx
docker exec studyverse-frontend-1 npm run build
docker restart studyverse-frontend-1
```

### 14.3 nginx

`deploy/nginx.conf` 配置域名与上游超时。上传限制 100MB，适配大课件与长生成任务。

### 14.4 监控与排错

- `GET /api/system/status`：各子系统就绪状态
- `python backend/scripts/check_kg_backend.py`：本地 KG 检查
- 后端日志：Uvicorn stdout；前端构建错误：`npm run build` 输出

---

## 15. 扩展开发指南

### 15.1 新增大模型

1. 在 `llm/providers.py` 的 `build_llm_provider` 增加分支，或扩展现有 `OpenAICompatibleLLMProvider`
2. 在 `frontend/lib/llm-models.ts` 增加预设项
3. 如需特殊 API（如 web_search），在 Provider 的 `complete` / `stream` 中分支处理

### 15.2 新增专家 Agent

1. 实现 `BaseAgent`（`interfaces/contracts.py`）：`name`、`run(context) -> dict`
2. 放入 `agents/resources/` 或 `agents/`
3. 在 `dependencies.py` 的 `get_orchestrator()` 注入并在 `_experts` 注册
4. 在 `registry.py` 的 `EXPERT_AGENTS` 增加描述供 MainAgent 选择
5. 更新 `prompt_blocks.py` 中专家列表（如需要）

### 15.3 新增 Tool

1. 在 `tools/{tool-name}/` 添加 `TOOL.md` 与 `tool.json`
2. 在 `app/tools/` 注册 handler
3. 在 MainAgent 工具列表中声明

### 15.4 新增 Skill

1. 在 `skills/{skill-name}/skill.json` 定义步骤与绑定 Agent
2. MainAgent 通过 `call_skill` 触发

### 15.5 新增资源类型

1. `domain/models.py` 扩展 `ResourceType`
2. 实现对应 `BaseAgent` 子类
3. 扩展 `chat_store.py` 消息记录字段与前端 `types.ts`、`api.ts` 映射
4. 路径页 `RESOURCE_VISUAL_META` 与卡片素材

### 15.6 替换检索器

实现 `Retriever` 接口，在 `get_retriever()` 返回新实例；保持返回结构含 `chunks`、`kg_context`、`citations` 以兼容下游。

---

## 附录：关键文件速查

| 关注点 | 文件路径 |
|--------|----------|
| 对话入口 | `backend/app/api/routes.py` → `orchestrator.chat_stream` |
| ReAct 主循环 | `backend/app/agents/main_agent.py` |
| 专家注册 | `backend/app/agents/registry.py` |
| 记忆实现 | `backend/app/infrastructure/memory_service.py` |
| 混合检索 | `backend/app/infrastructure/kg_rag/hybrid_retriever.py` |
| 定制课 | `backend/app/agents/course_workflow_agent.py` |
| SSE 打包 | `backend/app/agents/chat_stream.py` |
| 前端聊天状态 | `frontend/lib/background-chat.ts` |
| API 封装 | `frontend/lib/api.ts` |
| LLM 配置 UI | `frontend/app/settings/page.tsx` |

---

*文档版本：与当前代码库同步（含阅读器对话、定制课卡片状态修复、路径资源卡片 operator-card 动效、多模型支持）。*
