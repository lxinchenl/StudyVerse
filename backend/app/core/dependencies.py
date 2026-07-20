from functools import lru_cache

from app.agents.orchestrator import AgentOrchestrator
from app.agents.resource_studio import ResourceStudioOrchestrator
from app.agents.main_agent import MainAgent
from app.agents.path_agent import PathPlanningAgent
from app.agents.course_workflow_agent import CourseWorkflowAgent
from app.agents.resources import (
    CodeLabAgent,
    ExerciseAgent,
    MindmapAgent,
    NoteAgent,
    VideoAgent,
)
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.safety_agent import SafetyReviewAgent

from app.core.config import get_settings

from app.infrastructure.kg_rag.graph_repository import HybridGraphRepository
from app.infrastructure.kg_rag.hybrid_retriever import HybridRetrievalPipeline
from app.infrastructure.kg_rag import get_chroma_store, get_neo4j_store
from app.infrastructure.material_catalog import CourseCatalog
from app.infrastructure.memory_service import FileMemoryService
from app.infrastructure.repositories import FileChunkRepository, QuestionRepository
from app.infrastructure.llm_config_service import LLMConfigService
from app.llm.providers import build_llm_provider

from app.services.app_services import (
    CourseService,
    GraphService,
    PathService,
    PracticeService,
    ResourceService,
)
from app.services.auth_service import AuthService

_orchestrator_by_user: dict[str, AgentOrchestrator] = {}
_resource_studio_by_user: dict[str, ResourceStudioOrchestrator] = {}
_practice_by_user: dict[str, PracticeService] = {}


@lru_cache
def get_course_catalog() -> CourseCatalog:
    return CourseCatalog.discover(get_settings().courses_dir)


@lru_cache
def get_memory_service() -> FileMemoryService:
    return FileMemoryService(get_settings().users_dir)


@lru_cache
def get_chunk_repo() -> FileChunkRepository:
    s = get_settings()
    return FileChunkRepository(get_course_catalog(), s.cache_dir)


@lru_cache
def get_graph_repo() -> HybridGraphRepository:
    s = get_settings()
    return HybridGraphRepository(get_neo4j_store(), s.kg_data_dir)


@lru_cache
def get_question_repo() -> QuestionRepository:
    s = get_settings()
    return QuestionRepository(s.courses_dir, s.resources_dir / "exercises")


@lru_cache
def get_code_lab_repo():
    from app.infrastructure.code_lab_repository import CodeLabRepository

    s = get_settings()
    return CodeLabRepository(s.resources_dir / "code_lab")


@lru_cache
def get_retriever() -> HybridRetrievalPipeline:
    return HybridRetrievalPipeline(
        get_chunk_repo(),
        chroma=get_chroma_store(),
        neo4j=get_neo4j_store(),
    )


@lru_cache
def get_llm_config_service() -> LLMConfigService:
    return LLMConfigService(get_settings().users_dir)


def get_llm_provider_for_user(user_id: str):
    return build_llm_provider(get_llm_config_service().resolve_runtime(user_id))


def invalidate_user_llm(user_id: str) -> None:
    _orchestrator_by_user.pop(user_id, None)
    _resource_studio_by_user.pop(user_id, None)
    _practice_by_user.pop(user_id, None)


def reload_llm_dependencies() -> None:
    """Clear all per-user LLM-bound caches (e.g. after bulk env changes)."""
    _orchestrator_by_user.clear()
    _resource_studio_by_user.clear()
    _practice_by_user.clear()
    get_resource_service.cache_clear()


def _build_orchestrator(llm) -> AgentOrchestrator:
    memory = get_memory_service()
    retriever = get_retriever()
    retrieval_agent = RetrievalAgent(retriever)
    resource_service = get_resource_service()
    exercise_agent = ExerciseAgent(get_question_repo(), llm, resource_service, memory)
    note_agent = NoteAgent(llm, resource_service, memory)
    mindmap_agent = MindmapAgent(llm, resource_service, memory)
    video_agent = VideoAgent(llm, resource_service)
    code_lab_agent = CodeLabAgent(llm, resource_service, memory, get_code_lab_repo())
    resource_experts = {
        retrieval_agent.name: retrieval_agent,
        exercise_agent.name: exercise_agent,
        note_agent.name: note_agent,
        mindmap_agent.name: mindmap_agent,
        video_agent.name: video_agent,
        code_lab_agent.name: code_lab_agent,
    }
    course_workflow_agent = CourseWorkflowAgent(
        llm, memory, get_path_service(), resource_experts
    )
    return AgentOrchestrator(
        main_agent=MainAgent(memory, llm),
        retrieval_agent=retrieval_agent,
        exercise_agent=exercise_agent,
        note_agent=note_agent,
        mindmap_agent=mindmap_agent,
        video_agent=video_agent,
        code_lab_agent=code_lab_agent,
        path_agent=PathPlanningAgent(),
        course_workflow_agent=course_workflow_agent,
        safety_agent=SafetyReviewAgent(),
        memory=memory,
    )


def get_orchestrator_for_user(user_id: str) -> AgentOrchestrator:
    cached = _orchestrator_by_user.get(user_id)
    if cached is not None:
        return cached
    orch = _build_orchestrator(get_llm_provider_for_user(user_id))
    _orchestrator_by_user[user_id] = orch
    return orch


# Backward-compatible aliases used by tests / tools without user context → mock
def get_llm_provider():
    return build_llm_provider({"provider": "mock"})


def get_orchestrator() -> AgentOrchestrator:
    return _build_orchestrator(get_llm_provider())


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(get_settings().users_dir)


@lru_cache
def get_course_service() -> CourseService:
    return CourseService(get_course_catalog())


@lru_cache
def get_graph_service() -> GraphService:
    return GraphService(get_graph_repo())


def get_practice_service_for_user(user_id: str) -> PracticeService:
    cached = _practice_by_user.get(user_id)
    if cached is not None:
        return cached
    svc = PracticeService(get_question_repo(), get_memory_service(), get_llm_provider_for_user(user_id))
    _practice_by_user[user_id] = svc
    return svc


def get_practice_service() -> PracticeService:
    return PracticeService(get_question_repo(), get_memory_service(), get_llm_provider())


@lru_cache
def get_code_lab_service():
    from app.services.app_services import CodeLabService

    return CodeLabService(get_code_lab_repo(), get_memory_service())


@lru_cache
def get_resource_service() -> ResourceService:
    # ResourceService mainly does file I/O; LLM is only used in generate helpers.
    return ResourceService(get_settings().resources_dir, get_llm_provider())


def get_resource_studio_for_user(user_id: str) -> ResourceStudioOrchestrator:
    cached = _resource_studio_by_user.get(user_id)
    if cached is not None:
        return cached
    memory = get_memory_service()
    llm = get_llm_provider_for_user(user_id)
    resource_service = get_resource_service()
    retriever = get_retriever()
    studio = ResourceStudioOrchestrator(
        retrieval_agent=RetrievalAgent(retriever),
        exercise_agent=ExerciseAgent(get_question_repo(), llm, resource_service, memory),
        note_agent=NoteAgent(llm, resource_service, memory),
        mindmap_agent=MindmapAgent(llm, resource_service, memory),
        video_agent=VideoAgent(llm, resource_service),
        code_lab_agent=CodeLabAgent(llm, resource_service, memory, get_code_lab_repo()),
        resource_service=resource_service,
        memory=memory,
        llm=llm,
    )
    _resource_studio_by_user[user_id] = studio
    return studio


def get_resource_studio() -> ResourceStudioOrchestrator:
    return get_resource_studio_for_user("__mock__")


@lru_cache
def get_path_service() -> PathService:
    return PathService(get_memory_service())
