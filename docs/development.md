# 系统开发说明书

## 1. 开发环境

| 类别 | 选型 |
|------|------|
| 语言 | Python 3.11+ / TypeScript |
| 后端 | FastAPI + Uvicorn（ASGI） |
| 前端 | Next.js 14 + React |
| 向量库 | Chroma（嵌入模型 `BAAI/bge-small-zh-v1.5`） |
| 图数据库 | Neo4j（可选，缺失时回退 JSON 图谱） |
| 数据校验 | Pydantic v2 |
| 包管理 | pip / npm |
| AI Coding 辅助 | Cursor（详见《开源协议与 AI 工具说明》） |

## 2. 目录结构

```
edu_agent/
├── backend/
│   ├── app/
│   │   ├── agents/            # 多智能体：MainAgent(ReAct) + 9 专家 Agent + 编排器
│   │   │   ├── resources/     # 6 类资源生成 Agent
│   │   │   └── ...
│   │   ├── api/routes.py      # REST + SSE 路由
│   │   ├── core/              # 配置、依赖注入
│   │   ├── domain/            # Pydantic 模型与 schema
│   │   ├── infrastructure/    # KG-RAG、文档解析、沙箱、TTS、画像工具
│   │   ├── interfaces/contracts.py  # BaseAgent / LLMProvider 等抽象接口
│   │   ├── llm/providers.py   # 可插拔大模型 Provider
│   │   ├── learning/services.py     # 路径规划、学习评估规则实现
│   │   └── main.py
│   ├── scripts/check_kg_backend.py  # KG 后端连通性检查
│   └── tests/
├── frontend/                  # Next.js 前端
├── data/
│   ├── courses/db-principles/ # 样例课程：61 个 PPT/Word 课件
│   ├── users/                 # 用户画像与记忆持久化
│   └── generated_resources/   # 已生成资源（笔记/导图/练习/代码/视频）
├── kg_rag_demo/               # 预置 Chroma + 图谱 JSON
├── skills/                    # 资源生成 skill 包（course-workflow/explainer 等）
├── docs/                      # 本说明书 + 测试说明书 + 开源/AI 工具说明
└── scripts/start_dev.ps1      # 一键启动
```

## 3. 后端启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 4. 前端启动

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000`。一键启动前后端：`.\scripts\start_dev.ps1`。

## 5. 大模型与知识库配置

- **大模型**：默认 Mock Provider（离线可完整演示）。生产环境在前端 `/settings` 或 `.env` 配置豆包 ARK；预留讯飞星火 Provider（见《开源协议与 AI 工具说明》）。配置热更新：保存后调 `reload_llm_dependencies()` 刷新依赖注入。
- **知识库**：课件放入 `data/courses/{course-id}/materials/`，重启后端或删除 `data/cache/course_material_chunks.json` 刷新检索索引。
- **连通性检查**：`python scripts/check_kg_backend.py` 或 `GET /api/system/status`。

## 6. API 接口

接口前缀 `/api`，主要路由（`backend/app/api/routes.py`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/system/status` | Chroma/Neo4j/检索管线/LLM 配置状态 |
| GET / PUT | `/system/llm-config` | 查询 / 更新大模型配置 |
| POST | `/system/llm-config/test` | 测试当前 LLM 连通性 |
| POST | `/auth/register` | 用户注册 |
| GET | `/profile` | 获取学习画像 |
| GET | `/courses` · `/courses/{id}/chapters` · `/courses/{id}/documents` | 课程目录 |
| GET | `/documents/{id}/file` | 下载课件原文 |
| GET / DELETE | `/chat/history` | 对话历史 |
| POST | `/memory/clear-short-term` | 清空短期记忆 |
| **POST** | **`/chat`** | 一次性对话（返回完整回答 + 资源卡片 + ReAct 轨迹） |
| **POST** | **`/chat/stream`** | **流式对话（SSE：status/progress/done 事件）** |
| POST | `/resources/generate` · `/resources/generate/stream` | 批量资源生成（含流式） |
| GET / DELETE | `/resources` · `/resources/{id}` | 资源库 |
| GET | `/knowledge-graph` | 知识图谱数据 |
| GET | `/practice/questions` · POST `/practice/submit` | 练习题作答 |
| GET | `/code-lab/set` · POST `/code-lab/run` · `/code-lab/submit` | 编程沙箱判题 |
| GET | `/path` · `/path/courses` · `/path/courses/{id}` | 学习路径 |
| GET | `/workbench` | 工作台（智能体任务） |

### 对话接口示例（流式）

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我生成第3章的思维导图和练习题"}'
```

响应为 SSE 事件流，依次推送 `status`（"ReAct 第 N 轮…"）、`progress`（ReAct 步骤/资源卡片增量）、最终 `done`（完整回答 + 画像 + 资源）。

### 对话接口示例（非流式）

```json
{
  "message": "我会 SQL，但关系代数和范式容易混淆，想结合图解和练习学习。",
  "course_id": "db-principles"
}
```

## 7. 前端页面

| 路由 | 功能 |
|------|------|
| `/learn` | 对话工作台（流式输出、Markdown 渲染、资源卡片、ReAct 轨迹面板） |
| `/resources` | 资源库（笔记/导图/练习/代码/视频/拓展阅读） |
| `/path` · `/path/{courseId}` | 学习路径与定制系统课 |
| `/practice` | 练习题作答 |
| `/workbench` | 智能体任务监控 |
| `/knowledge-graph` | 知识图谱浏览 |
| `/courses/{courseId}` | 课程目录与课件阅读 |
| `/settings` | 大模型配置 |

## 8. 扩展方式

- **新增大模型供应商**：实现 `LLMProvider`（`app/llm/providers.py`），在 `build_llm_provider` 注册分支。
- **新增资源类型**：实现 `BaseAgent` 子类放入 `app/agents/resources/`，注册进 `AgentOrchestrator` 并补充 `ResourceType` 枚举。
- **新增专家 Agent**：实现 `BaseAgent`，加入 `core/dependencies.py` 的 `get_orchestrator()` 依赖注入与 `registry.py` 注册表。
- **替换检索器**：实现 `Retriever`，在 `get_retriever()` 注入。
- **替换路径/评估算法**：实现 `LearningPathPlanner` / `LearningEvaluator`（`app/learning/services.py`）。

## 9. 部署

后端：`uvicorn app.main:app --host 0.0.0.0 --port 8000`，建议前置 Nginx。前端：`npm run build && npm start`。CORS 已在 `create_app()` 中开启（`core/config.py`）。
