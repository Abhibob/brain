from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def json_type():
    return JSON().with_variant(JSONB, "postgresql")


def vector_type():
    return JSON().with_variant(Vector(1536), "postgresql")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Enum("student", "educator", "researcher", name="user_role"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    educator_profile: Mapped["EducatorProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    taught_classes: Mapped[list["Class"]] = relationship(back_populates="educator", foreign_keys="Class.educator_id")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student", foreign_keys="Enrollment.student_id")


class EducatorProfile(Base):
    __tablename__ = "educator_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    bio: Mapped[str | None] = mapped_column(Text)
    institution: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="educator_profile")


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    educator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    enrollment_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    educator: Mapped[User] = relationship(back_populates="taught_classes", foreign_keys=[educator_id])
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    materials: Mapped[list["Material"]] = relationship(back_populates="class_", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_enrollment_class_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    class_: Mapped[Class] = relationship(back_populates="enrollments")
    student: Mapped[User] = relationship(back_populates="enrollments", foreign_keys=[student_id])


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(Enum("lesson", "quiz", name="material_type"), default="lesson")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    class_: Mapped[Class] = relationship(back_populates="materials")
    sections: Mapped[list["MaterialSection"]] = relationship(back_populates="material", cascade="all, delete-orphan", order_by="MaterialSection.order_index")
    questions: Mapped[list["QuizQuestion"]] = relationship(back_populates="material", cascade="all, delete-orphan")


class MaterialSection(Base):
    __tablename__ = "material_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(vector_type())

    material: Mapped[Material] = relationship(back_populates="sections")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(json_type())
    correct_answer: Mapped[str] = mapped_column(String(255))
    points: Mapped[float] = mapped_column(Float, default=1.0)

    material: Mapped[Material] = relationship(back_populates="questions")


class TrackingSession(Base):
    __tablename__ = "tracking_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    features: Mapped[dict[str, Any] | None] = mapped_column(json_type())
    focus_score: Mapped[float | None] = mapped_column(Float)
    focus_breakdown: Mapped[dict[str, Any] | None] = mapped_column(json_type())
    focus_label: Mapped[str | None] = mapped_column(String(32))

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    material: Mapped[Material] = relationship()
    events: Mapped[list["TrackingEvent"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    prediction: Mapped["ScorePrediction | None"] = relationship(back_populates="session", cascade="all, delete-orphan")
    section_focus: Mapped[list["SectionFocusScore"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("tracking_sessions.id", ondelete="SET NULL"), index=True)
    answers: Mapped[dict[str, Any]] = mapped_column(json_type())
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    material: Mapped[Material] = relationship()
    session: Mapped[TrackingSession | None] = relationship()


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("tracking_sessions.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(json_type())
    client_ts: Mapped[int] = mapped_column(BigInteger)
    server_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped[TrackingSession] = relationship(back_populates="events")


class ScorePrediction(Base):
    __tablename__ = "score_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("tracking_sessions.id", ondelete="CASCADE"), unique=True, index=True)
    predicted_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(128))
    actual_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[TrackingSession] = relationship(back_populates="prediction")


class PredictionModel(Base):
    __tablename__ = "prediction_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(128))
    model_type: Mapped[str] = mapped_column(String(128))
    feature_importances: Mapped[dict[str, Any]] = mapped_column(json_type())
    rmse: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    artifact: Mapped[bytes | None] = mapped_column(LargeBinary)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentProfileEntry(Base):
    __tablename__ = "student_profile_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_text: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[dict[str, Any]] = mapped_column(json_type())
    embedding: Mapped[list[float] | None] = mapped_column(vector_type())
    trigger_material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="SET NULL"), index=True)
    quiz_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="SET NULL"), index=True)
    quiz_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    student: Mapped[User] = relationship(foreign_keys=[user_id])
    material: Mapped[Material | None] = relationship(foreign_keys=[trigger_material_id])


class SectionFocusScore(Base):
    __tablename__ = "section_focus_scores"
    __table_args__ = (UniqueConstraint("session_id", "section_id", name="uq_section_focus_session_section"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("tracking_sessions.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("material_sections.id", ondelete="CASCADE"), index=True)
    focus_score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict[str, Any]] = mapped_column(json_type())
    label: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[TrackingSession] = relationship(back_populates="section_focus")
    section: Mapped[MaterialSection] = relationship()


class MaterialTopic(Base):
    __tablename__ = "material_topics"
    __table_args__ = (UniqueConstraint("material_id", "topic", name="uq_material_topic"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserLearningProfile(Base):
    __tablename__ = "user_learning_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    style_vector: Mapped[dict[str, Any]] = mapped_column(json_type())
    rolling_focus_score: Mapped[float] = mapped_column(Float, default=0.5)
    rolling_reading_speed_wpm: Mapped[float] = mapped_column(Float, default=0.0)
    rolling_completion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    preferred_session_length_s: Mapped[float] = mapped_column(Float, default=0.0)
    peak_focus_time_of_day: Mapped[dict[str, Any]] = mapped_column(json_type())
    engagement_fingerprint: Mapped[dict[str, Any]] = mapped_column(json_type())
    behavioral_signals: Mapped[dict[str, Any]] = mapped_column(json_type())
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    lesson_count: Mapped[int] = mapped_column(Integer, default=0)
    quiz_count: Mapped[int] = mapped_column(Integer, default=0)
    last_focus_label: Mapped[str | None] = mapped_column(String(32))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class TopicMasteryNode(Base):
    __tablename__ = "topic_mastery_nodes"
    __table_args__ = (UniqueConstraint("user_id", "topic", name="uq_topic_mastery_user_topic"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.5)
    exposure_score: Mapped[float] = mapped_column(Float, default=0.5)
    encounter_count: Mapped[int] = mapped_column(Integer, default=0)
    quiz_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    struggle_signal: Mapped[float] = mapped_column(Float, default=0.0)
    strength_signal: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding: Mapped[list[float] | None] = mapped_column(vector_type())

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class TopicMasteryEdge(Base):
    __tablename__ = "topic_mastery_edges"
    __table_args__ = (
        UniqueConstraint("user_id", "from_topic", "to_topic", "relation", name="uq_topic_edge"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_topic: Mapped[str] = mapped_column(String(255), index=True)
    to_topic: Mapped[str] = mapped_column(String(255), index=True)
    relation: Mapped[str] = mapped_column(String(32))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LessonAsset(Base):
    __tablename__ = "lesson_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Enum("reading", "quiz", "video", "practice", name="lesson_asset_kind"))
    topic: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(json_type())
    external_url: Mapped[str | None] = mapped_column(String(1024))
    generated_by: Mapped[str] = mapped_column(String(32), default="llm")
    embedding: Mapped[list[float] | None] = mapped_column(vector_type())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LessonPlanDraft(Base):
    __tablename__ = "lesson_plan_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    educator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="SET NULL"), index=True)
    topic: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Enum("draft", "ready", "published", name="lesson_plan_status"), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    nodes: Mapped[list["LessonPlanNode"]] = relationship(back_populates="draft", cascade="all, delete-orphan", order_by="LessonPlanNode.order_index")
    edges: Mapped[list["LessonPlanEdge"]] = relationship(back_populates="draft", cascade="all, delete-orphan")


class LessonPlanNode(Base):
    __tablename__ = "lesson_plan_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("lesson_plan_drafts.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("lesson_assets.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    teacher_adjusted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    draft: Mapped[LessonPlanDraft] = relationship(back_populates="nodes")
    asset: Mapped[LessonAsset] = relationship()


class LessonPlanEdge(Base):
    __tablename__ = "lesson_plan_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("lesson_plan_drafts.id", ondelete="CASCADE"), index=True)
    from_node_id: Mapped[int] = mapped_column(ForeignKey("lesson_plan_nodes.id", ondelete="CASCADE"), index=True)
    to_node_id: Mapped[int] = mapped_column(ForeignKey("lesson_plan_nodes.id", ondelete="CASCADE"), index=True)
    condition: Mapped[dict[str, Any] | None] = mapped_column(json_type())

    draft: Mapped[LessonPlanDraft] = relationship(back_populates="edges")


class AssetFitScore(Base):
    __tablename__ = "asset_fit_scores"
    __table_args__ = (UniqueConstraint("asset_id", "student_id", name="uq_asset_fit_asset_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("lesson_assets.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fit_score: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text)
    components: Mapped[dict[str, Any]] = mapped_column(json_type())
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PersonalizedLesson(Base):
    __tablename__ = "personalized_lessons"
    __table_args__ = (UniqueConstraint("student_id", "base_material_id", name="uq_personalized_student_material"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    educator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    base_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    prompt_used: Mapped[str] = mapped_column(Text)
    generated_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    educator: Mapped[User] = relationship(foreign_keys=[educator_id])
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    material: Mapped[Material] = relationship(foreign_keys=[base_material_id])


class ResearchNeuralModel(Base):
    __tablename__ = "research_neural_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    architecture: Mapped[dict[str, Any]] = mapped_column(json_type())
    feature_schema: Mapped[list[str]] = mapped_column(json_type())
    normalization: Mapped[dict[str, Any]] = mapped_column(json_type())
    weights: Mapped[dict[str, Any]] = mapped_column(json_type())
    metrics: Mapped[dict[str, Any]] = mapped_column(json_type())
    loss_history: Mapped[list[dict[str, Any]]] = mapped_column(json_type())
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    student_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    class_: Mapped[Class | None] = relationship(foreign_keys=[class_id])


class TribePrediction(Base):
    __tablename__ = "tribe_predictions"
    __table_args__ = (UniqueConstraint("student_id", "material_id", "stimulus_hash", name="uq_tribe_student_material_stimulus"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    personalized_lesson_id: Mapped[int | None] = mapped_column(ForeignKey("personalized_lessons.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    stimulus_hash: Mapped[str] = mapped_column(String(64), index=True)
    stimulus_title: Mapped[str] = mapped_column(String(255))
    stimulus_kind: Mapped[str] = mapped_column(String(32), default="personalized_lesson")
    model_version: Mapped[str | None] = mapped_column(String(128))
    hemodynamic_lag_s: Mapped[float] = mapped_column(Float, default=5.0)
    request_payload: Mapped[dict[str, Any]] = mapped_column(json_type())
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(json_type())
    roi_timeseries: Mapped[dict[str, Any]] = mapped_column(json_type())
    roi_summary: Mapped[dict[str, Any]] = mapped_column(json_type())
    connectivity: Mapped[list[dict[str, Any]]] = mapped_column(json_type())
    surface_summary: Mapped[dict[str, Any]] = mapped_column(json_type())
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    material: Mapped[Material] = relationship(foreign_keys=[material_id])
    personalized_lesson: Mapped[PersonalizedLesson | None] = relationship(foreign_keys=[personalized_lesson_id])
