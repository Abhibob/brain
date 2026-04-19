"""research workbench neural surrogate and tribe prediction tables

Revision ID: 0004_research_workbench
Revises: 0003_lesson_studio
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_research_workbench"
down_revision = "0003_lesson_studio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_neural_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("version", sa.String(length=128), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("architecture", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("feature_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalization", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("loss_history", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("student_sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trained_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_table(
        "tribe_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("personalized_lesson_id", sa.Integer(), sa.ForeignKey("personalized_lessons.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, index=True),
        sa.Column("stimulus_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("stimulus_title", sa.String(length=255), nullable=False),
        sa.Column("stimulus_kind", sa.String(length=32), nullable=False, server_default="personalized_lesson"),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("hemodynamic_lag_s", sa.Float(), nullable=False, server_default="5"),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("roi_timeseries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("roi_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("connectivity", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("surface_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "material_id", "stimulus_hash", name="uq_tribe_student_material_stimulus"),
    )


def downgrade() -> None:
    op.drop_table("tribe_predictions")
    op.drop_table("research_neural_models")
