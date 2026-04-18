"""focus scores and learning profile graph

Revision ID: 0002_focus_and_learning_profile
Revises: 0001_initial
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0002_focus_and_learning_profile"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracking_sessions", sa.Column("focus_score", sa.Float(), nullable=True))
    op.add_column("tracking_sessions", sa.Column("focus_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("tracking_sessions", sa.Column("focus_label", sa.String(length=32), nullable=True))

    op.create_table(
        "section_focus_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("tracking_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("material_sections.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("focus_score", sa.Float(), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "section_id", name="uq_section_focus_session_section"),
    )

    op.create_table(
        "material_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("topic", sa.String(length=255), nullable=False, index=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("material_id", "topic", name="uq_material_topic"),
    )

    op.create_table(
        "user_learning_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("style_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rolling_focus_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("rolling_reading_speed_wpm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rolling_completion_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("preferred_session_length_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("peak_focus_time_of_day", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("engagement_fingerprint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("behavioral_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("session_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lesson_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_focus_label", sa.String(length=32), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "topic_mastery_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("topic", sa.String(length=255), nullable=False, index=True),
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("exposure_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("encounter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("struggle_signal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("strength_signal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.UniqueConstraint("user_id", "topic", name="uq_topic_mastery_user_topic"),
    )

    op.create_table(
        "topic_mastery_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_topic", sa.String(length=255), nullable=False, index=True),
        sa.Column("to_topic", sa.String(length=255), nullable=False, index=True),
        sa.Column("relation", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "from_topic", "to_topic", "relation", name="uq_topic_edge"),
    )

    op.execute("CREATE INDEX ix_topic_mastery_nodes_embedding ON topic_mastery_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_topic_mastery_nodes_embedding")
    op.drop_table("topic_mastery_edges")
    op.drop_table("topic_mastery_nodes")
    op.drop_table("user_learning_profiles")
    op.drop_table("material_topics")
    op.drop_table("section_focus_scores")
    op.drop_column("tracking_sessions", "focus_label")
    op.drop_column("tracking_sessions", "focus_breakdown")
    op.drop_column("tracking_sessions", "focus_score")
