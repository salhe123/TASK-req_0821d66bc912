"""phase 2 — evaluation cycles, templates, assignments, digest state

Revision ID: 0003_phase2_cycles
Revises: 0002_phase1_identity
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0003_phase2_cycles"
down_revision: Union[str, None] = "0002_phase1_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "template_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("items", JSONB, nullable=False),
        sa.Column("published_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("template_id", "version_no", name="uq_template_version_no"),
    )

    op.create_table(
        "evaluation_cycles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        sa.Column("deadline_at", TIMESTAMP, nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("makeup_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("makeup_business_days", sa.Integer, nullable=False, server_default="5"),
        sa.Column("holidays", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "template_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cycle_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluator_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewer_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state", sa.String(40), nullable=False, server_default="NOT_STARTED"),
        sa.Column("draft_values", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("submitted_at", TIMESTAMP, nullable=True),
        sa.Column("late_flag", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("returned_reason", sa.String(500), nullable=True),
        sa.Column("archived_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "evaluator_user_id", name="uq_assignment_cycle_evaluator"),
    )
    op.create_index(
        "ix_assignments_cycle_evaluator",
        "assignments",
        ["cycle_id", "evaluator_user_id"],
    )
    op.create_index("ix_assignments_state", "assignments", ["state"])

    # Per-user digest state — last date the 09:00 banner was delivered.
    op.add_column(
        "users",
        sa.Column("digest_last_shown_date", sa.Date, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "digest_last_shown_date")
    op.drop_index("ix_assignments_state", table_name="assignments")
    op.drop_index("ix_assignments_cycle_evaluator", table_name="assignments")
    op.drop_table("assignments")
    op.drop_table("evaluation_cycles")
    op.drop_table("template_versions")
    op.drop_table("templates")
