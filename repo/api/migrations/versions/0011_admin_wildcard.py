"""phase 10 — grant Administrator the (*, *) wildcard permission

The RBAC layer already treats the tuple ("*", "*") as a super-admin bypass
(`AuthContext.has_permission`), but the Administrator role was never given
that literal grant. Several later guards (submission read, feedback subject
override, share-link revocation, reviewer binding) rely on this, so we add
it here.

Revision ID: 0011_admin_wildcard
Revises: 0010_phase9_ruleset_tz
Create Date: 2026-04-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_admin_wildcard"
down_revision: Union[str, None] = "0010_phase9_ruleset_tz"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO permissions (resource, action, description) "
            "VALUES ('*', '*', 'Super-admin wildcard — grants every resource:action pair') "
            "ON CONFLICT (resource, action) DO NOTHING"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.name = 'Administrator' "
            "AND p.resource = '*' AND p.action = '*' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE resource = '*' AND action = '*')"
        )
    )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE resource = '*' AND action = '*'")
    )
