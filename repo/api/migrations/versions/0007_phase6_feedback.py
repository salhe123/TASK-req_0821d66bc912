"""phase 6 — feedback events, signals, subject blocks

Revision ID: 0007_phase6_feedback
Revises: 0006_phase5_models
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "0007_phase6_feedback"
down_revision: Union[str, None] = "0006_phase5_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "feedback_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("arm", sa.String(1), nullable=False),
        sa.Column("subject_key", sa.String(200), nullable=False),
        sa.Column("target_id", sa.String(200), nullable=False),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("ingest_enabled_at_time", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('LIKE','NOT_INTERESTED','BLOCK')", name="ck_feedback_kind"),
        sa.CheckConstraint("arm IN ('A','B')", name="ck_feedback_arm"),
    )
    op.create_index(
        "ix_feedback_events_subject_created",
        "feedback_events",
        ["subject_key", "created_at"],
    )
    op.create_index("ix_feedback_events_experiment", "feedback_events", ["experiment_id"])

    op.create_table(
        "feedback_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("arm", sa.String(1), nullable=False),
        sa.Column("target_id", sa.String(200), nullable=False),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_interested_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("experiment_id", "arm", "target_id", name="uq_feedback_signals_triple"),
        sa.CheckConstraint("arm IN ('A','B')", name="ck_feedback_signals_arm"),
    )

    op.create_table(
        "subject_blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("subject_key", sa.String(200), nullable=False),
        sa.Column("target_id", sa.String(200), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subject_key", "target_id", name="uq_subject_blocks_pair"),
    )
    op.create_index("ix_subject_blocks_subject", "subject_blocks", ["subject_key"])


def downgrade() -> None:
    op.drop_index("ix_subject_blocks_subject", table_name="subject_blocks")
    op.drop_table("subject_blocks")
    op.drop_table("feedback_signals")
    op.drop_index("ix_feedback_events_experiment", table_name="feedback_events")
    op.drop_index("ix_feedback_events_subject_created", table_name="feedback_events")
    op.drop_table("feedback_events")
