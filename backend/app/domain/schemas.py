from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResourceType(StrEnum):
    EXERCISE = "exercise"
    NOTE = "note"
    MINDMAP = "mindmap"
    VIDEO_SCRIPT = "video_script"
    CODE_LAB = "code_lab"


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    RETRY = "retry"


class UserOut(BaseModel):
    id: str
    name: str
    major: str
    email: str = ""


class UserRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    major: str = ""


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserUploadOut(BaseModel):
    filename: str
    relative_path: str
    size: int


class UserProfileOut(BaseModel):
    student_id: str
    major: str
    course: str
    goal: str
    recent_topics: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    frequent_errors: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    mastery: dict[str, float] = Field(default_factory=dict)


class CourseOut(BaseModel):
    id: str
    title: str
    description: str
    progress: float
    last_studied_at: str
    chapter_count: int
    document_count: int


class ChapterOut(BaseModel):
    id: str
    course_id: str
    title: str
    order: int


class DocumentOut(BaseModel):
    id: str
    course_id: str
    chapter_id: str
    title: str
    type: str
    pages: int | None = None
    progress: float = 0
    content: str | None = None
    file_name: str | None = None
    file_url: str | None = None


class DocumentProgressUpdateRequest(BaseModel):
    viewed_page: int | None = None
    total_pages: int | None = None
    completed: bool = False


class DocumentProgressOut(BaseModel):
    document_progress: float
    course_progress: float
    last_studied_at: str


class CourseProposalModuleOut(BaseModel):
    id: str
    title: str
    objective: str
    chapter_key: str = ""
    estimated_minutes: int = 45
    topics: list[str] = Field(default_factory=list)


class CourseProposalCardOut(BaseModel):
    kind: str = "course_proposal"
    status: str = "pending"
    topic: str = ""
    course_title: str = ""
    summary: str = ""
    modules: list[CourseProposalModuleOut] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    course_id: str | None = None
    document_id: str | None = None
    selected_text: str | None = None
    course_workflow_action: str | None = None
    course_proposal: dict[str, Any] | None = None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    agent_traces: list[dict[str, Any]] = Field(default_factory=list)
    react_steps: list[dict[str, Any]] = Field(default_factory=list)
    retrieval: dict[str, Any] | None = None
    explainer_videos: list["ExplainerVideoOut"] = Field(default_factory=list)
    exercise_sets: list["ExerciseSetOut"] = Field(default_factory=list)
    mindmaps: list["MindmapOut"] = Field(default_factory=list)
    notes: list["NoteOut"] = Field(default_factory=list)
    code_lab_sets: list["CodeLabSetOut"] = Field(default_factory=list)
    course_proposal_card: CourseProposalCardOut | None = None


class NoteOut(BaseModel):
    resource_id: str
    title: str
    topic: str
    summary: str
    markdown: str


class MindmapOut(BaseModel):
    resource_id: str
    title: str
    topic: str
    summary: str
    mermaid_source: str


class ExplainerVideoOut(BaseModel):
    resource_id: str
    title: str
    summary: str
    player_url: str
    scene_count: int = 0


class ChatResponse(BaseModel):
    messages: list[ChatMessageOut]
    profile: UserProfileOut


class GraphNodeOut(BaseModel):
    id: str
    label: str
    type: str
    x: float = 0
    y: float = 0


class GraphEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    relation: str


class KnowledgeGraphMetaOut(BaseModel):
    backend: str
    neo4j_connected: bool
    node_count: int
    edge_count: int


class KnowledgeGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    meta: KnowledgeGraphMetaOut | None = None


class ExerciseOut(BaseModel):
    id: str
    resource_id: str
    resource_title: str
    topic: str
    difficulty: str
    question: str
    grading_type: str = "standard"


class ExerciseQuestionOut(BaseModel):
    id: str
    topic: str
    difficulty: str
    question: str
    grading_type: str = "standard"
    attempt_status: str | None = None
    last_score: float | None = None


class ExerciseSetOut(BaseModel):
    resource_id: str
    title: str
    topic: str
    summary: str
    questions: list[ExerciseQuestionOut] = Field(default_factory=list)


class ExerciseSubmitRequest(BaseModel):
    answers: dict[str, str]


class ExerciseResultOut(BaseModel):
    question_id: str
    score: float
    standard_answer: str
    grading_type: str = "standard"
    feedback: str = ""


class ExerciseSubmitResponse(BaseModel):
    total_score: float
    results: list[ExerciseResultOut]
    profile: UserProfileOut


class CodeLabChallengeOut(BaseModel):
    id: str
    topic: str
    difficulty: str
    question: str
    starter_code: str = ""
    setup_code: str = ""
    language: str = "python"
    hint: str = ""
    attempt_status: str | None = None
    last_score: float | None = None


class CodeLabSetOut(BaseModel):
    resource_id: str
    title: str
    topic: str
    summary: str
    challenges: list[CodeLabChallengeOut] = Field(default_factory=list)


class CodeLabRunRequest(BaseModel):
    challenge_id: str
    code: str


class CodeLabRunResponse(BaseModel):
    ok: bool
    stdout: str
    stderr: str
    exit_code: int
    error: str = ""


class CodeLabSubmitRequest(BaseModel):
    answers: dict[str, str]


class CodeLabResultOut(BaseModel):
    challenge_id: str
    score: float
    passed: bool
    expected_stdout: str = ""
    actual_stdout: str = ""
    stderr: str = ""
    feedback: str = ""


class CodeLabSubmitResponse(BaseModel):
    total_score: float
    results: list[CodeLabResultOut]
    profile: UserProfileOut


class ResourceOut(BaseModel):
    id: str
    type: str
    title: str
    summary: str
    content: str
    topic: str
    created_at: str
    player_url: str | None = None
    scene_count: int | None = None


class ResourceGenerateRequest(BaseModel):
    course_id: str | None = None
    topic: str
    types: list[str]
    clarification: str | None = None


class LearningPathStepOut(BaseModel):
    id: str
    title: str
    objective: str
    status: str
    estimated_minutes: int
    resources: list[str]


class CourseResourceRefOut(BaseModel):
    type: str
    resource_id: str
    title: str
    order: int = 0
    learning_order_reason: str = ""


class LearningModuleOut(BaseModel):
    id: str
    title: str
    objective: str
    status: str
    estimated_minutes: int
    chapter_key: str = ""
    resources: list[CourseResourceRefOut] = Field(default_factory=list)


class LearningCourseSummaryOut(BaseModel):
    id: str
    title: str
    topic: str
    summary: str
    status: str
    module_count: int
    progress: float
    created_at: str


class LearningCourseDetailOut(BaseModel):
    id: str
    title: str
    topic: str
    summary: str
    status: str
    created_at: str
    modules: list[LearningModuleOut] = Field(default_factory=list)


class CourseWorkflowProposeRequest(BaseModel):
    topic: str
    course_id: str | None = None


class PlannerTaskOut(BaseModel):
    id: str
    name: str
    agent: str
    status: str
    parallel: bool
    input_summary: str
    output_summary: str | None = None


class WorkbenchOut(BaseModel):
    tasks: list[PlannerTaskOut]


class LLMConfigOut(BaseModel):
    provider: str
    base_url: str
    model: str
    api_key_set: bool
    api_key_hint: str
    ready: bool


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class LLMTestResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    preview: str
    error: str | None = None
