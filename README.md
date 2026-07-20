# StudyVerse

**StudyVerse**（个性化学习多智能体系统）面向高校课程场景，通过对话式学习画像、知识图谱增强检索（KG-RAG）与多智能体协同编排，为学生生成笔记、思维导图、练习题、代码实操、讲解视频等学习资源，并支持定制系统课与学习路径管理。

在线体验：http://120.27.131.220/

---

## 功能概览

| 模块 | 说明 |
|------|------|
| **对话学习** | 主 Agent ReAct 推理，按需调用 9 个专家 Agent，SSE 流式输出回答与资源卡片 |
| **学习画像** | 对话中自动抽取学习目标、薄弱点、近期主题、偏好等，持久化到用户档案 |
| **KG-RAG 检索** | Chroma 向量 + 关键词 + Neo4j 图谱混合检索，约束课程类回答，降低幻觉 |
| **资源生成** | 笔记、思维导图、练习题、代码实操、讲解视频、拓展阅读，共 6 类资源 |
| **定制系统课** | 用户提出学习需求 → 生成课程大纲卡片 → 确认后按讲次自动生成资源并写入学习路径 |
| **学习路径** | `/path` 管理定制课，`/path/[courseId]` 按讲次顺序学习，资源以交互式卡片呈现 |
| **课程阅读** | 课件在线预览（PPT/Word），阅读页侧边栏可与 Agent 对话，选中内容可直接提问 |
| **练习与判题** | 选择题作答、Python 代码沙箱运行与自动判题，提交结果反哺学习画像 |
| **资源工坊** | 像素风「资源办公室」UI，支持独立发起资源生成与多 Agent 讨论编排 |
| **模型配置** | 前端 `/settings` 热切换豆包 / DeepSeek / GLM 等 OpenAI 兼容模型，未配置时回退 Mock |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 15、React 19、TypeScript、Tailwind CSS 4 |
| 后端 | Python 3.10+、FastAPI、Uvicorn、Pydantic v2 |
| 向量检索 | ChromaDB + `BAAI/bge-small-zh-v1.5` |
| 知识图谱 | Neo4j（可选，不可用时回退 JSON 图谱） |
| 大模型 | OpenAI 兼容接口（火山引擎豆包 ARK 等），可插拔 `LLMProvider` |
| 语音合成 | edge-tts（讲解视频配音） |
| 部署 | Docker Compose（backend + frontend + nginx） |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- （可选）Neo4j 5.x

### 本地开发

**后端**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**前端**

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 http://localhost:3000。API 默认指向 `http://localhost:8000/api`。

Windows 一键启动：`.\scripts\start_dev.ps1`

### Docker 部署

```bash
docker compose up --build
```

| 服务 | 端口 | 说明 |
|------|------|------|
| backend | 8000 | FastAPI 应用 |
| frontend | 3000 | Next.js 生产构建 |
| nginx | 80 | 反向代理，`/api/` → backend，`/` → frontend |

持久化数据通过 volume 挂载到 `./data/*`、`./tools`、`./skills`。

**热更新部署（不重新下载依赖）**：将改动文件 `docker cp` 进容器后重启，前端在容器内执行 `npm run build` 再重启 frontend。

---

## 配置

### 环境变量（项目根目录 `.env`）

```env
# 大模型（火山引擎豆包）
ARK_API_KEY=你的密钥
EDU_AGENT_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EDU_AGENT_LLM_MODEL=doubao-seed-2-0-lite-260428

# 知识图谱（可选）
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=你的密码

# 向量库（可选覆盖）
EDU_AGENT_CHROMA_COLLECTION=edu_agent
EDU_AGENT_EMBED_MODEL_PATH=BAAI/bge-small-zh-v1.5
```

未配置 API Key 时系统自动使用 **Mock Provider**，可离线完整演示对话与资源生成流程。

运行时 LLM 配置也可在前端 **设置** 页（`/settings`）修改，保存至 `data/settings/llm.json`（已 gitignore），立即生效无需重启。

### 课程资料

将课件放入 `data/courses/{course-id}/materials/`，详见 [data/courses/README.md](data/courses/README.md)。

```text
data/courses/
  db-principles/
    course.json
    materials/
      第1章 绪论.pptx
      第2章 关系模型.docx
```

新增课程后重启后端，或删除 `data/cache/course_material_chunks.json` 刷新检索索引。

### 知识库连通性检查

```bash
cd backend
python scripts/check_kg_backend.py
curl http://localhost:8000/api/system/status
```

---

## 页面导航

| 路由 | 功能 |
|------|------|
| `/` | 首页仪表盘（继续学习、下一项练习） |
| `/learn` | 主对话工作台（流式聊天、ReAct 轨迹、资源卡片） |
| `/courses` | 课程列表 |
| `/courses/[courseId]` | 章节与课件目录 |
| `/courses/[courseId]/read/[docId]` | 课件阅读 + 侧边 Agent 对话 |
| `/path` | 定制系统课列表 |
| `/path/[courseId]` | 按讲次学习，资源卡片（operator-card 风格） |
| `/practice` | 练习题与代码实操 |
| `/resources` | 资源工坊（像素办公室） |
| `/settings` | 大模型与界面偏好配置 |

---

## 项目结构

```text
StudyVerse/
├── backend/app/          # FastAPI 应用
│   ├── agents/           # MainAgent、Orchestrator、9 专家 Agent
│   ├── api/              # REST + SSE 路由
│   ├── infrastructure/   # 记忆、KG-RAG、沙箱、TTS
│   ├── services/         # 课程、路径、练习、聊天存储
│   └── tools/            # 原子工具注册与执行
├── frontend/             # Next.js 前端
│   ├── app/              # 页面路由
│   ├── components/       # UI 组件（chat、reader、studio、path 等）
│   └── lib/              # API 封装、全局状态、类型定义
├── data/                 # 运行时数据（用户、课程、资源、知识库）
├── skills/               # Skill 流水线定义（course-workflow 等）
├── tools/                # 原子工具定义（TOOL.md + tool.json）
├── deploy/               # nginx 配置
└── docs/                 # 设计与技术文档
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/technical_reference.md](docs/technical_reference.md) | **详细技术参考**（架构、Agent、记忆、API、前端、部署） |
| [docs/system_design.md](docs/system_design.md) | 系统设计说明书（赛题背景、防幻觉、流程图） |
| [docs/development.md](docs/development.md) | 开发环境与扩展指南 |
| [docs/testing.md](docs/testing.md) | 测试说明与手动验收清单 |
| [docs/open_source_and_ai_tools.md](docs/open_source_and_ai_tools.md) | 开源协议与 AI 工具使用说明 |
| [tools/README.md](tools/README.md) | Tool 与 Skill 的区别 |
| [skills/README.md](skills/README.md) | Skill 清单结构 |

---

## 核心设计亮点

- **主 Agent + 专家 Agent**：`MainAgent` 通过 ReAct 循环（最多 6 轮）路由到检索、笔记、导图、练习、代码、视频、路径、定制课、安全审校等专家，不直接生成内容。
- **资料约束生成**：资源类专家调用前必须已有课程资料（`ensure_material_basis`），无依据不生成，降低幻觉。
- **定制课工作流**：`course-workflow-propose` 生成大纲卡片 → 用户确认 → `course-workflow` Skill 按讲次 ReAct 编排资源 → 持久化到 `learning_paths.json`。
- **分层记忆**：用户画像、对话历史、工作记忆、短期资料上下文、助手人格（me）分层存储，主 Agent 按需读取与更新。
- **可插拔扩展**：`LLMProvider`、`BaseAgent`、`Retriever` 等抽象接口，便于替换模型、向量库与新增 Agent。

---

## 测试

```bash
cd backend
pytest
```

详见 [docs/testing.md](docs/testing.md)。

---

## License

本项目使用的开源组件与 AI 工具说明见 [docs/open_source_and_ai_tools.md](docs/open_source_and_ai_tools.md)。
