# Personalized Learning Multi-Agent System

面向中国软件杯 A3 赛题的个性化学习资源生成与学习多智能体系统。项目采用 FastAPI 后端、Next.js 前端、课程知识库/RAG、多智能体编排和可插拔大模型 Provider 设计。

## Quick Start

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## 课程资料

将课件放入 `data/courses/{course-id}/materials/`，详见 [data/courses/README.md](data/courses/README.md)。

```text
data/courses/
  db-principles/
    course.json
    materials/
      第1章 xxx.pptx
```

新增课程后重启后端，或删除 `data/cache/course_material_chunks.json` 刷新检索索引。

## 向量库 / 知识图谱

默认读取本仓库内的知识库目录：

| 组件 | 默认路径 / 配置 |
|------|----------------|
| Chroma | `data/kg/chroma`，collection `edu_agent` |
| Neo4j | `NEO4J_URI` / `NEO4J_PASSWORD` |
| 图谱 JSON 回退 | `data/kg/data/subgraphs.json` |

环境变量（`.env` 根目录）：

```env
NEO4J_PASSWORD=你的密码
# 可选
EDU_AGENT_CHROMA_COLLECTION=edu_agent
EDU_AGENT_EMBED_MODEL_PATH=BAAI/bge-small-zh-v1.5
```

检查连接：

```powershell
cd backend
python scripts/check_kg_backend.py
curl http://localhost:8000/api/system/status
```

检索流程（简化版）：Chroma 向量检索 → 关键词回退 → Neo4j 1 跳图谱 → 合并去重。

## 大模型（豆包 / OpenAI 兼容）

默认支持火山引擎豆包 API。可在前端 **模型配置** 页（`/settings`）填写 Base URL、Model、API Key，也可在 `.env` 中设置：

```env
ARK_API_KEY=你的密钥
EDU_AGENT_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EDU_AGENT_LLM_MODEL=doubao-seed-2-0-lite-260428
```

配置保存在 `data/settings/llm.json`（已加入 `.gitignore`）。保存后对话与资源生成会使用真实模型；未配置时回退 Mock。

## Highlights

- 对话式学习画像构建，覆盖知识基础、学习目标、学习风格、易错点等维度。
- 多智能体协同生成讲解文档、思维导图、题库、拓展阅读、代码案例和视频脚本。
- RAG 约束课程知识类回答，降低幻觉风险。
- 可插拔 `LLMProvider`，默认 Mock 可完整演示，预留讯飞星火等真实模型接入。
- 面向对象接口优先，方便替换模型、向量库、资源生成器和智能体角色。

