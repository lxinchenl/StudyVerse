# 测试说明书

## 1. 测试目标

验证系统能完整运行赛题要求的关键流程：对话式画像构建、多智能体协同资源生成、学习路径规划、智能辅导、学习效果评估、知识图谱增强检索（KG-RAG）和内容安全审校。

## 2. 测试环境

- Python 3.11+，依赖见 `backend/requirements.txt`（FastAPI / Pydantic / Chroma / Neo4j / sentence-transformers / openai / edge-tts / pytest）。
- 默认 Mock Provider，无需外部模型 API 与数据库即可完成自动化测试；Chroma 不可用时回退关键词检索，Neo4j 不可用时回退 JSON 图谱。

## 3. 自动化测试

```powershell
cd backend
pip install -r requirements.txt
pytest
```

当前自动化测试覆盖（`backend/tests/`）：

| 用例 | 验证点 | 对应赛题功能 |
|------|--------|-------------|
| `test_orchestrator_chat_end_to_end` | 编排器端到端跑通：画像维度字段 ≥6、对话写入记忆（随学随新）、产生智能体轨迹、专家注册表 ≥6 | 功能①②③④⑤ |
| `test_resource_types_meet_requirement` | `ResourceType` 枚举 ≥5 种，覆盖思维导图/练习题/代码实操/视频 | 功能② |
| `test_retrieval_pipeline_offline_fallback` | KG-RAG 混合检索在无 Chroma/Neo4j 时仍可用（关键词回退） | 防幻觉、智能辅导 |

> 端到端用例使用 Mock Provider，确保在任何环境下都能稳定复现赛题核心指标（画像 6 维、资源 5 类、专家 6 个）。

## 4. 手工功能测试

1. 启动后端与前端（`scripts/start_dev.ps1`）。
2. 打开 `http://localhost:3000`，注册用户并选择课程《数据库系统原理》。
3. **画像构建**：在对话中描述"我会 SQL、关系代数和范式易混淆、偏好图解和练习"，查看 `/profile` 画像维度随对话更新（≥6 维，且 `recent_topics` / `weak_points` 随学随新）。
4. **多智能体资源生成**：分别请求笔记、思维导图、练习题、代码实操、讲解视频，检查资源库 `/resources` 出现 6 类资源卡片，并含来源与个性化理由。
5. **学习路径**：访问 `/path`，确认路径步骤有 `reason` 与 `checkpoint`，且资源已按顺序关联。
6. **智能辅导**：提问课程概念，检查回答标注【资料N】引用、无来源时不编造。
7. **代码沙箱**：在 `/practice` 提交编程题代码，确认沙箱能运行并判题。
8. **防幻觉**：对知识库外问题，确认系统提示"资料中未找到"而非杜撰。

## 5. 接口测试

- 健康与后端状态：`GET /api/health`、`GET /api/system/status`。
- KG 连通性：`python scripts/check_kg_backend.py`。
- 流式对话：`curl -N -X POST http://localhost:8000/api/chat/stream -H "Content-Type: application/json" -d '{"message":"..."}'`，确认收到 `status` → `progress` → `done` 事件序列。
- 资源生成（流式）：`POST /api/resources/generate/stream`，确认进度追踪事件避免白屏等待。

## 6. 非功能测试

- **响应效率**：核心对话通过 SSE 流式（`status`/`progress`）持续反馈，避免长时间白屏；长任务（如多模态视频生成）通过 `studio_progress` 增量推送。
- **稳定性**：Mock Provider 保证离线演示；真实模型接入后保留 Mock 作为降级。
- **内容安全**：`SafetyReviewAgent` 在检索为空时给出风险提醒；预留敏感内容检测接口。

## 7. 演示稳定性策略

系统默认使用 Mock Provider，无需外部模型 API 即可完整演示赛题全流程；接入真实模型时，应保留 Mock 作为降级方案，并对 Neo4j 缺失、Chroma 缺失等场景做了回退处理。
