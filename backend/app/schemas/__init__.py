from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["student", "educator", "researcher"]
    bio: str | None = None
    institution: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class ClassCreate(BaseModel):
    title: str
    description: str | None = None


class ClassOut(BaseModel):
    id: int
    educator_id: int
    title: str
    description: str | None
    enrollment_code: str
    created_at: datetime


class EnrollRequest(BaseModel):
    enrollment_code: str


class SectionCreate(BaseModel):
    title: str
    content: str
    order_index: int = 0


class SectionOut(BaseModel):
    id: int
    title: str
    content: str
    order_index: int
    word_count: int


class MaterialCreate(BaseModel):
    title: str
    type: Literal["lesson", "quiz"] = "lesson"
    order_index: int = 0
    sections: list[SectionCreate] = Field(default_factory=list)


class MaterialUpdate(BaseModel):
    title: str | None = None
    type: Literal["lesson", "quiz"] | None = None
    order_index: int | None = None
    sections: list[SectionCreate] | None = None


class MaterialOut(BaseModel):
    id: int
    class_id: int
    title: str
    type: str
    order_index: int
    published_at: datetime | None
    personalized: bool = False
    generated_content: str | None = None
    sections: list[SectionOut] = Field(default_factory=list)


class PublishOut(BaseModel):
    material_id: int
    published_at: datetime
    personalization_tasks: int


class QuizQuestionCreate(BaseModel):
    question: str
    options: list[str]
    correct_answer: str
    points: float = 1.0


class QuizQuestionPublic(BaseModel):
    id: int
    question: str
    options: list[str]
    points: float


class QuizSubmit(BaseModel):
    answers: dict[str, str]
    session_id: int | None = None


class QuizResult(BaseModel):
    attempt_id: int
    score: float
    max_score: float
    normalized_score: float


class SessionStart(BaseModel):
    material_id: int


class SessionStartOut(BaseModel):
    session_id: int
    started_at: datetime


class SessionFocusOut(BaseModel):
    focus_score: float
    confidence: float | None = None
    breakdown: dict[str, Any]
    label: str


class SectionFocusOut(BaseModel):
    section_id: int
    focus_score: float
    breakdown: dict[str, Any]
    label: str


class SessionEndOut(BaseModel):
    session_id: int
    features: dict[str, Any] | None
    prediction: dict[str, Any] | None
    focus: SessionFocusOut | None = None
    section_focus: list[SectionFocusOut] = Field(default_factory=list)


class SessionPredictionOut(BaseModel):
    session_id: int
    predicted_score: float
    confidence: float
    model_version: str
    actual_score: float | None


class ClassAnalyticsOut(BaseModel):
    class_id: int
    model: dict[str, Any] | None
    drift: dict[str, Any]
    students: list[dict[str, Any]]
    material_engagement: list[dict[str, Any]]
    section_heatmap: list[dict[str, Any]]


class ProfileEntryOut(BaseModel):
    id: int
    profile_text: str
    profile_json: dict[str, Any]
    quiz_score: float | None
    trigger_material_id: int | None
    created_at: datetime


class UserLearningProfileOut(BaseModel):
    user_id: int
    style_vector: dict[str, float]
    rolling_focus_score: float
    rolling_reading_speed_wpm: float
    rolling_completion_rate: float
    preferred_session_length_s: float
    engagement_fingerprint: dict[str, Any]
    behavioral_signals: dict[str, Any]
    peak_focus_time_of_day: dict[str, Any]
    session_count: int
    lesson_count: int
    quiz_count: int
    last_focus_label: str | None
    last_updated_at: datetime | None


class TopicNodeOut(BaseModel):
    topic: str
    mastery_score: float
    exposure_score: float
    encounter_count: int
    quiz_sample_count: int
    struggle_signal: float
    strength_signal: float
    last_seen_at: datetime | None


class TopicEdgeOut(BaseModel):
    from_topic: str
    to_topic: str
    relation: str
    weight: float


class MasteryOut(BaseModel):
    seed_topic: str | None
    nodes: list[TopicNodeOut]
    edges: list[TopicEdgeOut]


class LessonPlanSectionOut(BaseModel):
    title: str
    angle: str
    why_this_works_for_them: str
    estimated_word_count: int


class LessonPlanOut(BaseModel):
    topic: str
    sections: list[LessonPlanSectionOut]
    prerequisites_to_reinforce: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    style_summary: list[str] = Field(default_factory=list)


class LessonPlanRequest(BaseModel):
    topic: str
    material_id: int | None = None


class LearningContextOut(BaseModel):
    style_summary_lines: list[str]
    mastery_lines: list[str]
    mastery_nodes: list[dict[str, Any]]
    topic_edges: list[dict[str, Any]]
    profile_entries: list[dict[str, Any]]
    recent_focus: list[dict[str, Any]]
    recent_hints: list[str]
    seed_text: str


class LessonPlanCreate(BaseModel):
    student_id: int
    topic: str
    description: str | None = None
    class_id: int | None = None
    material_id: int | None = None


class LessonAssetOut(BaseModel):
    id: int
    kind: str
    topic: str
    title: str
    payload: dict[str, Any]
    external_url: str | None
    generated_by: str


class LessonPlanNodeOut(BaseModel):
    id: int
    asset_id: int
    order_index: int
    label: str | None
    notes: str | None
    teacher_adjusted: bool
    asset: LessonAssetOut | None
    fit_score: int | None
    rationale: str | None


class LessonPlanEdgeOut(BaseModel):
    id: int
    from_node_id: int
    to_node_id: int
    condition: dict[str, Any] | None


class LessonPlanCandidateOut(BaseModel):
    asset: LessonAssetOut
    fit_score: int
    rationale: str
    components: dict[str, Any]


class LessonPlanDraftOut(BaseModel):
    id: int
    educator_id: int
    student_id: int
    class_id: int | None
    topic: str
    description: str | None
    status: str
    nodes: list[LessonPlanNodeOut]
    edges: list[LessonPlanEdgeOut]
    candidates: list[LessonPlanCandidateOut]
    created_at: datetime
    updated_at: datetime


class LessonPlanNodePatch(BaseModel):
    asset_id: int
    order_index: int = 0
    label: str | None = None
    notes: str | None = None
    teacher_adjusted: bool = True


class LessonPlanPatch(BaseModel):
    nodes: list[LessonPlanNodePatch] | None = None


class LearningViewOut(BaseModel):
    student_id: int
    learning_profile: UserLearningProfileOut | None
    top_mastery: list[TopicNodeOut]
    top_struggles: list[TopicNodeOut]
    topic_edges: list[TopicEdgeOut]
    recent_focus: list[dict[str, Any]]
    narrative_notes: list[dict[str, Any]]
