"""phase 7 — backups + restore events

Revision ID: 0008_phase7_backups
Revises: 0007_phase6_feedback
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0008_phase7_backups"
down_revision: Union[str, None] = "0007_phase6_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "backup_archives",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("filename", sa.String(255), nullable=False, unique=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("kek_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_backup_archives_created_at", "backup_archives", ["created_at"])

    op.create_table(
        "restore_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "archive_id",
            UUID(as_uuid=True),
            sa.ForeignKey("backup_archives.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column(
            "started_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kek_fingerprint", sa.String(64), nullable=False),
        sa.Column("notes", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", TIMESTAMP, nullable=True),
        sa.CheckConstraint("state IN ('staged','committed','aborted')", name="ck_restore_state"),
    )


def downgrade() -> None:
    op.drop_table("restore_events")
    op.drop_index("ix_backup_archives_created_at", table_name="backup_archives")
    op.drop_table("backup_archives")
