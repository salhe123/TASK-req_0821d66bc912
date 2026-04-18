"""phase 9 — rule-set manage permission + per-user timezone preference

Revision ID: 0010_phase9_ruleset_tz
Revises: 0009_phase8_model_runs
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_phase9_ruleset_tz"
down_revision: Union[str, None] = "0009_phase8_model_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO permissions (resource, action, description) "
            "VALUES ('rule_set', 'manage', 'Create/update rule sets and publish versions') "
            "ON CONFLICT (resource, action) DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.name = 'Administrator' "
            "AND p.resource = 'rule_set' AND p.action = 'manage' "
            "ON CONFLICT DO NOTHING"
        )
    )

    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="UTC",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE resource = 'rule_set' AND action = 'manage')"
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM permissions WHERE resource = 'rule_set' AND action = 'manage'"
        )
    )
