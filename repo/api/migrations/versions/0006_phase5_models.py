"""phase 5 — model registry, routing, experiments, rollback events

Revision ID: 0006_phase5_models
Revises: 0005_phase4_plans
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0006_phase5_models"
down_revision: Union[str, None] = "0005_phase4_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("live_schema_hash", sa.String(64), nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_id", UUID(as_uuid=True), sa.ForeignKey("models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("feature_schema", JSONB, nullable=False),
        sa.Column("feature_schema_hash", sa.String(64), nullable=False),
        sa.Column("artifact_uri", sa.String(500), nullable=False, server_default=""),
        sa.Column("artifact_params", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", TIMESTAMP, nullable=True),
        sa.UniqueConstraint("model_id", "version_no", name="uq_model_version_no"),
    )
    op.create_index("ix_model_versions_feature_schema_hash", "model_versions", ["feature_schema_hash"])

    op.create_table(
        "experiments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("ingest_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("apply_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "inference_routing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "model_a_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "model_b_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("weight_a", sa.Integer, nullable=False, server_default="90"),
        sa.Column("weight_b", sa.Integer, nullable=False, server_default="10"),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("weight_a BETWEEN 0 AND 100 AND weight_b BETWEEN 0 AND 100",
                           name="ck_inference_routing_weights_range"),
        sa.CheckConstraint("weight_a + weight_b = 100", name="ck_inference_routing_weights_sum"),
    )

    op.create_table(
        "rollback_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column(
            "triggered_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("metrics_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("trigger IN ('manual','metric')", name="ck_rollback_events_trigger"),
    )
    op.create_index("ix_rollback_events_experiment", "rollback_events", ["experiment_id"])


def downgrade() -> None:
    op.drop_index("ix_rollback_events_experiment", table_name="rollback_events")
    op.drop_table("rollback_events")
    op.drop_table("inference_routing")
    op.drop_table("experiments")
    op.drop_index("ix_model_versions_feature_schema_hash", table_name="model_versions")
    op.drop_table("model_versions")
    op.drop_table("models")
