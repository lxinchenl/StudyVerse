from app.compat import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResourceType(StrEnum):
    EXPLANATION = "explanation"
    MIND_MAP = "mind_map"
    EXERCISES = "exercises"
    READING = "reading"
    CODE_LAB = "code_lab"
    VIDEO_SCRIPT = "video_script"


class ProfileDimension(BaseModel):
    name: str
    value: str
    confidence: float = Field(ge=0, le=1, default=0.7)


class StudentProfile(BaseModel):
    student_id: str
    major: str = "计算机科学与技术"
    course: str = "人工智能导论"
    dimensions: list[ProfileDimension] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    updated_reason: str = "initial"


class LearningRequest(BaseModel):
    student_id: str = "demo-student"
    message: str
    target_topic: str | None = None


class ResourceCard(BaseModel):
    id: str
    type: ResourceType
    title: str
    summary: str
    content: str
    personalized_reason: str
    difficulty: str = "medium"
    sources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningPathStep(BaseModel):
    id: str
    title: str
    objective: str
    reason: str
    estimated_minutes: int
    resources: list[str] = Field(default_factory=list)
    checkpoint: str


class EvaluationReport(BaseModel):
    student_id: str
    mastery: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


class AgentTrace(BaseModel):
    agent: str
    role: str
    summary: str


class OrchestratedLearningResult(BaseModel):
    profile: StudentProfile
    resources: list[ResourceCard]
    learning_path: list[LearningPathStep]
    evaluation: EvaluationReport
    tutor_answer: str
    traces: list[AgentTrace]

