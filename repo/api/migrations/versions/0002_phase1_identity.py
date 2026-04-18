"""phase 1 identity — users, rbac, sessions, audit_logs, failed_logins

Revision ID: 0002_phase1_identity
Revises: 0001_phase0_bootstrap
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0002_phase1_identity"
down_revision: Union[str, None] = "0001_phase0_bootstrap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


DEFAULT_ROLES: list[tuple[str, str, list[str]]] = [
    ("Administrator", "Full operational surface, user/role management, backups, audit.", ["*"]),
    ("ML Engineer", "Model registry, routing console, rollback.", ["model.feature_schema", "model.metrics"]),
    ("Evaluator", "Evaluation forms, own assignments.", ["evaluator_notes"]),
    ("Reviewer", "Review/approve submissions, trace viewer.", ["evaluator_notes"]),
    ("Plan Owner", "Build plans, BOM diff, share links.", ["plan.bom.notes"]),
]


DEFAULT_PERMISSIONS: list[tuple[str, str, str]] = [
    ("user", "manage", "Create/update/unlock users and assign roles"),
    ("role", "manage", "Create/update role definitions"),
    ("audit", "read", "Read audit log entries"),
    ("backup", "manage", "Create, stage, commit, abort backups"),
    ("cycle", "manage", "Create/update evaluation cycles"),
    ("cycle", "participate", "Act on an evaluation assignment"),
    ("cycle", "review", "Approve or return submissions"),
    ("template", "manage", "Create/update templates"),
    ("build_plan", "manage", "Create/update build plans"),
    ("build_plan", "view", "View build plans"),
    ("build_plan", "view_shared", "Open a shared build plan link"),
    ("model", "register", "Register a model version"),
    ("model", "promote", "Promote a model version to APPROVED"),
    ("model", "route", "Modify inference routing"),
    ("model", "rollback", "Trigger one-click rollback"),
    ("feedback", "submit", "Submit end-user feedback events"),
    ("experiment", "manage", "Toggle experiment ingest/apply"),
]


ROLE_PERMISSION_GRANTS: dict[str, list[tuple[str, str]]] = {
    "Administrator": [
        ("user", "manage"), ("role", "manage"), ("audit", "read"), ("backup", "manage"),
        ("cycle", "manage"), ("cycle", "participate"), ("cycle", "review"),
        ("template", "manage"), ("build_plan", "manage"), ("build_plan", "view"),
        ("build_plan", "view_shared"),
        ("model", "register"), ("model", "promote"), ("model", "route"),
        ("model", "rollback"), ("experiment", "manage"),
        ("feedback", "submit"),
    ],
    "ML Engineer": [
        ("model", "register"), ("model", "promote"), ("model", "route"),
        ("model", "rollback"), ("experiment", "manage"), ("audit", "read"),
    ],
    "Evaluator": [
        ("cycle", "participate"),
    ],
    "Reviewer": [
        ("cycle", "review"), ("cycle", "participate"),
    ],
    "Plan Owner": [
        ("build_plan", "manage"), ("build_plan", "view"), ("build_plan", "view_shared"),
    ],
}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(120), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("locked_until", TIMESTAMP, nullable=True),
        sa.Column("last_login_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("field_view_allowlist", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("issued_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        sa.Column("last_seen_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "failed_logins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username_attempted", sa.String(120), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("attempted_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_failed_logins_username_attempted", "failed_logins", ["username_attempted"])
    op.create_index("ix_failed_logins_attempted_at", "failed_logins", ["attempted_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Enforce append-only audit: block UPDATE/DELETE via trigger.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_update
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();
        """
    )

    # Seed roles.
    conn = op.get_bind()
    from sqlalchemy import select, literal_column, text as sqltext
    import json

    roles_table = sa.table(
        "roles",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("field_view_allowlist", JSONB),
    )
    permissions_table = sa.table(
        "permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.String),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", UUID(as_uuid=True)),
        sa.column("permission_id", UUID(as_uuid=True)),
    )

    for name, desc, allowlist in DEFAULT_ROLES:
        conn.execute(
            sqltext(
                "INSERT INTO roles (name, description, field_view_allowlist) "
                "VALUES (:name, :desc, CAST(:allow AS jsonb))"
            ),
            {"name": name, "desc": desc, "allow": json.dumps(allowlist)},
        )

    for resource, action, desc in DEFAULT_PERMISSIONS:
        conn.execute(
            sqltext(
                "INSERT INTO permissions (resource, action, description) "
                "VALUES (:r, :a, :d)"
            ),
            {"r": resource, "a": action, "d": desc},
        )

    for role_name, perms in ROLE_PERMISSION_GRANTS.items():
        for resource, action in perms:
            conn.execute(
                sqltext(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.name = :role AND p.resource = :resource AND p.action = :action"
                ),
                {"role": role_name, "resource": resource, "action": action},
            )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only()")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_failed_logins_attempted_at", table_name="failed_logins")
    op.drop_index("ix_failed_logins_username_attempted", table_name="failed_logins")
    op.drop_table("failed_logins")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
