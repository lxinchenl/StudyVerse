# 开源协议与 AI 工具说明

> 本文档在显著位置标注系统中使用的开源项目、AI 工具/框架的名称、来源与协议，符合赛题非功能需求第 2 条要求。

## 1. 开源组件清单（后端，Python）

| 组件 | 用途 | 协议 |
|------|------|------|
| FastAPI | 后端 Web API 框架（ASGI） | MIT |
| Uvicorn | ASGI 服务器 | BSD-3-Clause |
| Pydantic / pydantic-settings | 数据校验与配置管理 | MIT |
| HTTPX | HTTP 客户端（模型 API 调用） | BSD-3-Clause |
| python-multipart | 表单/文件上传解析 | Apache-2.0 |
| python-pptx | PPT 课件文本与图片解析 | MIT |
| python-docx | Word 实验文档解析 | MIT |
| ChromaDB | 向量数据库（课程资料检索） | Apache-2.0 |
| Neo4j Python Driver + neo4j-nvl | 图数据库与图谱可视化 | Apache-2.0 |
| sentence-transformers | 文本嵌入模型（`BAAI/bge-small-zh-v1.5`） | Apache-2.0 |
| openai (Python SDK) | OpenAI 兼容接口（豆包 ARK 等） | MIT |
| python-dotenv | 环境变量加载 | BSD-3-Clause |
| edge-tts | 讲解视频本地配音（中文 TTS） | MIT |
| pytest / pytest-asyncio | 自动化测试 | MIT |

## 2. 开源组件清单（前端，TypeScript/React）

| 组件 | 用途 | 协议 |
|------|------|------|
| Next.js | 前端应用框架 | MIT |
| React / react-dom | UI 组件 | MIT |
| Tailwind CSS | 原子化样式 | MIT |
| lucide-react | 图标库 | ISC |
| react-markdown / remark-gfm | Markdown 渲染 | MIT |
| rehype-highlight / rehype-katex / rehype-raw / remark-math | 代码高亮、数学公式、富文本 | MIT |
| KaTeX | 数学公式渲染 | MIT |
| Mermaid | 思维导图渲染 | MIT |
| docx-preview | Word 文档预览 | Apache-2.0 |

## 3. 嵌入模型

- **BAAI/bge-small-zh-v1.5**（来源：北京智源人工智能研究院，MIT 协议）：用于课程资料向量化检索。

## 4. 大模型接入现状与讯飞工具说明

系统通过 `LLMProvider` 抽象（`backend/app/llm/providers.py`）统一接入大模型，支持热切换：

1. **Mock Provider（默认）**：离线可完整演示赛题全流程，无需任何外部 API。
2. **OpenAI 兼容 Provider**：当前默认真实模型为火山引擎豆包（ARK，`doubao-seed-2-0-lite`），可在前端 `/settings` 或 `.env` 配置。

**关于科大讯飞相关工具**：系统架构已为讯飞能力预留接入点，计划/已接入的路径包括：

- **讯飞星火大模型**：`LLMProvider` 抽象的 `build_llm_provider()` 已预留星火分支。星火提供 OpenAI 兼容的 HTTP 接口，可通过在前端 `/settings` 配置星火的 Base URL、Model、API Key 直接复用现有 `OpenAICompatibleLLMProvider`；也可实现独立的 `XFYunSparkProvider` 接入星火 WebSocket/SDK。
- **多模态生成**：资源生成链路（讲解视频、笔记配图、代码沙箱）的 `LLMProvider` 注入点统一，可平滑替换为讯飞多模态能力。

> 团队承诺：在最终提交版本中，至少将一条核心生成链路（对话回答或资源生成）切换为讯飞星火真实模型并完成联调验证，以满足赛题"开发过程中使用的其他 AI 辅助工具，需选用科大讯飞相关工具"的要求。

## 5. AI Coding 工具使用说明

开发过程中使用 **Cursor** 作为 AI 辅助编程工具，用于：项目结构脚手架、样板代码生成、文档撰写草稿、测试用例补充。需明确说明：

- AI Coding 工具仅作为**开发辅助**，系统核心架构设计（ReAct 多智能体编排、KG-RAG 混合检索、画像记忆机制、6 类资源生成 pipeline）均由团队自主设计与评审定稿。
- 业务逻辑、赛题功能实现、最终代码审查与验收由团队负责。
- 涉及的 AI 辅助生成代码均已由团队人工 review 并测试。

> 赛题提交要求第 6 条："如若使用 AI Coding 工具，给出相关说明"——本节即该项说明。
