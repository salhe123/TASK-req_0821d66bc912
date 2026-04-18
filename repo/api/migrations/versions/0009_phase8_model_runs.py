"""phase 8 — model training/evaluation runs

Revision ID: 0009_phase8_model_runs
Revises: 0008_phase7_backups
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0009_phase8_model_runs"
down_revision: Union[str, None] = "0008_phase7_backups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    conn = op.get_bind()
    # Seed model:run permission and grant to Administrator + ML Engineer.
    conn.execute(
        sa.text(
            "INSERT INTO permissions (resource, action, description) "
            "VALUES ('model', 'run', 'Start/complete training or evaluation runs') "
            "ON CONFLICT (resource, action) DO NOTHING"
        )
    )
    for role_name in ("Administrator", "ML Engineer"):
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.name = :role_name "
                "AND p.resource = 'model' AND p.action = 'run' "
                "ON CONFLICT DO NOTHING"
            ),
            {"role_name": role_name},
        )

    op.create_table(
        "model_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("dataset_ref", sa.String(500), nullable=False, server_default=""),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.String(2000), nullable=False, server_default=""),
        sa.Column(
            "started_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint("kind IN ('TRAINING','EVALUATION')", name="ck_model_run_kind"),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')",
            name="ck_model_run_status",
        ),
    )
    op.create_index("ix_model_runs_model_version_id", "model_runs", ["model_version_id"])


def downgrade() -> None:
    op.drop_index("ix_model_runs_model_version_id", table_name="model_runs")
    op.drop_table("model_runs")
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE resource = 'model' AND action = 'run')"
        )
    )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE resource = 'model' AND action = 'run'")
    )
