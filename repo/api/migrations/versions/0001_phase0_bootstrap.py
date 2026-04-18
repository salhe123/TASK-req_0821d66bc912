"""phase 0 bootstrap — enable pgcrypto extension and create schema_meta

Revision ID: 0001_phase0_bootstrap
Revises:
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_phase0_bootstrap"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "schema_meta",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('bootstrap', 'phase0')"
    )


def downgrade() -> None:
    op.drop_table("schema_meta")
