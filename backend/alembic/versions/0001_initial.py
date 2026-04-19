"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    role_enum = postgresql.ENUM("student", "educator", "researcher", name="user_role", create_type=False)
    material_enum = postgresql.ENUM("lesson", "quiz", name="material_type", create_type=False)
    role_enum.create(op.get_bind(), checkfirst=True)
    material_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "educator_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("educator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enrollment_code", sa.String(length=32), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("class_id", "student_id", name="uq_enrollment_class_student"),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("type", material_enum, nullable=False, server_default="lesson"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True, index=True),
    )
    op.create_table(
        "material_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correct_answer", sa.String(length=255), nullable=False),
        sa.Column("points", sa.Float(), nullable=False, server_default="1"),
    )
    op.create_table(
        "tracking_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("tracking_sessions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        CREATE TABLE tracking_events (
            id BIGSERIAL NOT NULL,
            session_id INTEGER NOT NULL REFERENCES tracking_sessions(id) ON DELETE CASCADE,
            event_type VARCHAR(64) NOT NULL,
            event_data JSONB NOT NULL,
            client_ts BIGINT NOT NULL,
            server_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, server_ts)
        ) PARTITION BY RANGE (server_ts)
        """
    )
    op.execute("CREATE INDEX ix_tracking_events_session_id ON tracking_events (session_id)")
    op.execute("CREATE INDEX ix_tracking_events_event_type ON tracking_events (event_type)")
    op.execute("CREATE INDEX ix_tracking_events_server_ts ON tracking_events (server_ts)")
    op.execute("CREATE TABLE tracking_events_default PARTITION OF tracking_events DEFAULT")
    op.create_table(
        "score_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("tracking_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("predicted_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("actual_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "prediction_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("feature_importances", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rmse", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact", sa.LargeBinary(), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "student_profile_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("profile_text", sa.Text(), nullable=False),
        sa.Column("profile_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("trigger_material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("quiz_attempt_id", sa.Integer(), sa.ForeignKey("quiz_attempts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("quiz_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_table(
        "personalized_lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("educator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("base_material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("prompt_used", sa.Text(), nullable=False),
        sa.Column("generated_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "base_material_id", name="uq_personalized_student_material"),
    )

    op.execute("CREATE INDEX ix_student_profile_entries_embedding ON student_profile_entries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX ix_material_sections_embedding ON material_sections USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")


def downgrade() -> None:
    op.drop_table("personalized_lessons")
    op.drop_table("student_profile_entries")
    op.drop_table("prediction_models")
    op.drop_table("score_predictions")
    op.execute("DROP TABLE IF EXISTS tracking_events CASCADE")
    op.drop_table("quiz_attempts")
    op.drop_table("tracking_sessions")
    op.drop_table("quiz_questions")
    op.drop_table("material_sections")
    op.drop_table("materials")
    op.drop_table("enrollments")
    op.drop_table("classes")
    op.drop_table("educator_profiles")
    op.drop_table("users")
    sa.Enum(name="material_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
