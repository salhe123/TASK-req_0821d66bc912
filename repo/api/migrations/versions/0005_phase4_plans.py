"""phase 4 — build plans, bom lines, share links

Revision ID: 0005_phase4_plans
Revises: 0004_phase3_scoring
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0005_phase4_plans"
down_revision: Union[str, None] = "0004_phase3_scoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "owner_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "plan_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column(
            "parent_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("plan_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "version_no", name="uq_plan_version_no"),
    )
    op.create_index("ix_plan_versions_plan_id", "plan_versions", ["plan_id"])

    op.create_table(
        "bom_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "plan_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("plan_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_identity_key", sa.String(120), nullable=False),
        sa.Column("part_number", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False, server_default="ea"),
        sa.Column("notes", sa.String(2000), nullable=False, server_default=""),
        sa.Column("tags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.UniqueConstraint("plan_version_id", "line_identity_key", name="uq_bom_lines_identity"),
    )
    op.create_index("ix_bom_lines_plan_version_id", "bom_lines", ["plan_version_id"])

    op.create_table(
        "plan_share_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "plan_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("plan_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        sa.Column("opened_at", TIMESTAMP, nullable=True),
    )
    op.create_index("ix_plan_share_links_version", "plan_share_links", ["plan_version_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_share_links_version", table_name="plan_share_links")
    op.drop_table("plan_share_links")
    op.drop_index("ix_bom_lines_plan_version_id", table_name="bom_lines")
    op.drop_table("bom_lines")
    op.drop_index("ix_plan_versions_plan_id", table_name="plan_versions")
    op.drop_table("plan_versions")
    op.drop_table("plans")
