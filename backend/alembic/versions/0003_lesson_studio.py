"""lesson studio: assets, drafts, nodes, edges, fit scores

Revision ID: 0003_lesson_studio
Revises: 0002_focus_and_learning_profile
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003_lesson_studio"
down_revision = "0002_focus_and_learning_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    asset_kind = postgresql.ENUM("reading", "quiz", "video", "practice", name="lesson_asset_kind", create_type=False)
    plan_status = postgresql.ENUM("draft", "ready", "published", name="lesson_plan_status", create_type=False)
    asset_kind.create(op.get_bind(), checkfirst=True)
    plan_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "lesson_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", asset_kind, nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False, index=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("external_url", sa.String(length=1024), nullable=True),
        sa.Column("generated_by", sa.String(length=32), nullable=False, server_default="llm"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "lesson_plan_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("educator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", plan_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "lesson_plan_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("lesson_plan_drafts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("lesson_assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("teacher_adjusted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "lesson_plan_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("lesson_plan_drafts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_node_id", sa.Integer(), sa.ForeignKey("lesson_plan_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("to_node_id", sa.Integer(), sa.ForeignKey("lesson_plan_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("condition", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "asset_fit_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("lesson_assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("asset_id", "student_id", name="uq_asset_fit_asset_student"),
    )
    op.execute("CREATE INDEX ix_lesson_assets_embedding ON lesson_assets USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lesson_assets_embedding")
    op.drop_table("asset_fit_scores")
    op.drop_table("lesson_plan_edges")
    op.drop_table("lesson_plan_nodes")
    op.drop_table("lesson_plan_drafts")
    op.drop_table("lesson_assets")
    sa.Enum(name="lesson_plan_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="lesson_asset_kind").drop(op.get_bind(), checkfirst=True)
