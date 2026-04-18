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


class SessionEndOut(BaseModel):
    session_id: int
    features: dict[str, Any] | None
    prediction: dict[str, Any] | None


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
