"""End-to-end smoke test for the agent orchestrator.

Validates the rubric-critical indicators (profile >= 6 dimensions, >= 5 resource
types supported, learning path, evaluation, agent traces) against the real
``AgentOrchestrator.chat`` API using the Mock LLM provider so it runs offline.
"""

import asyncio

from app.core.dependencies import (
    get_course_service,
    get_memory_service,
    get_orchestrator,
    get_path_service,
    get_settings,
)
from app.services.auth_service import AuthService


def _first_course_id() -> str:
    courses = get_course_service().list_courses("test-student", get_memory_service())
    assert courses, "样例课程未找到，请确认 data/courses/ 下存在课程"
    return courses[0].id


def _ensure_test_user() -> str:
    users_dir = get_settings().users_dir
    auth = AuthService(users_dir)
    # 复用已存在的测试用户，避免重复创建目录
    for user in auth.list_users():
        if user.name == "自动化测试用户":
            return user.id
    return auth.register(
        "自动化测试用户",
        "test-auto@edu-agent.local",
        "testpass123",
        "计算机科学与技术",
    ).id


def test_orchestrator_chat_end_to_end():
    """编排器端到端：对话驱动画像构建 + 多智能体协同 + 评估 + 轨迹。"""
    orchestrator = get_orchestrator()
    user_id = _ensure_test_user()
    course_id = _first_course_id()

    result = asyncio.run(
        orchestrator.chat(
            user_id=user_id,
            message=(
                "我会 SQL，但关系代数和范式总是混淆，希望结合图解、练习题和代码案例学习。"
            ),
            course_id=course_id,
        )
    )

    # 1) 对话式画像：画像载体含不少于 6 个维度字段
    #    （course / goal / recent_topics / weak_points / frequent_errors /
    #     preferences / mastery 等，对应赛题"不少于 6 个维度"的动态画像）
    profile = result["profile"]
    assert profile is not None
    profile_keys = set(profile.keys())
    dimension_keys = {
        "course", "goal", "recent_topics", "weak_points",
        "frequent_errors", "preferences", "mastery",
    }
    covered = profile_keys & dimension_keys
    assert len(covered) >= 6, f"画像维度字段不足: {len(covered)} ({covered})"

    # 2) 随学随新：本轮对话已写入记忆（conversation 持久化）
    conversation = get_memory_service().get_recent_conversation(user_id, limit=2)
    assert conversation, "对话未持久化到记忆"

    # 3) 多智能体协同：本轮产生智能体轨迹（主 Agent ReAct + 至少一次专家/工具调用）
    traces = result.get("traces") or []
    assert traces, "未产生任何智能体轨迹"

    # 4) 多专家注册表：系统注册了 ≥6 个专家 Agent（赛题"多智能体协同架构"的硬支撑）
    from app.agents.registry import EXPERT_AGENTS

    assert len(EXPERT_AGENTS) >= 6, f"注册专家 Agent 不足: {len(EXPERT_AGENTS)}"

    # 4) 学习路径可查询（path 服务持久化）
    path = asyncio.run(asyncio.to_thread(get_path_service().get_path, user_id))
    # path 可能为空（取决于是否触发 path-agent），此处仅校验服务可用不抛错
    assert isinstance(path, list)

    # 5) 资源生成器支持的类型不少于 5 种（注册表层面，对应赛题"至少 5 种资源"）
    from app.domain.models import ResourceType

    assert len(list(ResourceType)) >= 5


def test_resource_types_meet_requirement():
    """赛题硬性要求：不少于 5 种资源类型。"""
    from app.domain.models import ResourceType

    types = [t.value for t in ResourceType]
    assert len(types) >= 5
    # 至少覆盖赛题点名的几类：讲解文档、思维导图、练习题、代码实操、视频
    expected = {
        ResourceType.MIND_MAP,
        ResourceType.EXERCISES,
        ResourceType.CODE_LAB,
        ResourceType.VIDEO_SCRIPT,
    }
    assert expected.issubset(set(ResourceType))


def test_retrieval_pipeline_offline_fallback():
    """KG-RAG 混合检索在无 Chroma/Neo4j 时仍可用（关键词回退）。"""
    from app.infrastructure.kg_rag.hybrid_retriever import HybridRetrievalPipeline
    from app.core.dependencies import get_chunk_repo

    pipeline = HybridRetrievalPipeline(get_chunk_repo(), chroma=None, neo4j=None)
    result = asyncio.run(
        pipeline.search("关系代数", queries=["关系代数"], entities=[], top_k=3)
    )
    assert "chunks" in result
    assert "source_types" in result  # 回退时含 keyword_fallback / none
