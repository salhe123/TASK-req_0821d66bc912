from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Unauthorized
from app.models.rbac import Role
from app.models.user import Session as DbSession
from app.models.user import User
from app.services.rbac import AuthContext
from app.services.session_tokens import TokenPayload


async def build_auth_context(
    db: AsyncSession, token_payload: TokenPayload
) -> AuthContext:
    session = (
        await db.execute(
            select(DbSession).where(DbSession.id == token_payload.session_id)
        )
    ).scalar_one_or_none()
    if session is None:
        raise Unauthorized(error="session_not_found", message="session not found")
    now = datetime.now(timezone.utc)
    if session.revoked_at is not None:
        raise Unauthorized(error="session_revoked", message="session revoked")
    if session.expires_at <= now:
        raise Unauthorized(error="session_expired", message="session expired")
    # Anti-replay: token must carry the session's current nonce. Tokens
    # issued for a prior incarnation of this session id will fail here.
    if token_payload.nonce and token_payload.nonce != session.csrf_token:
        raise Unauthorized(error="token_nonce_mismatch", message="session token nonce mismatch")

    user = (
        await db.execute(
            select(User)
            .where(User.id == session.user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise Unauthorized(error="user_inactive", message="user inactive")

    permissions: set[tuple[str, str]] = set()
    allowlist: set[str] = set()
    role_names: list[str] = []
    for role in user.roles:
        role_names.append(role.name)
        for p in role.permissions:
            permissions.add((p.resource, p.action))
        for f in role.field_view_allowlist or []:
            allowlist.add(f)

    session.last_seen_at = now
    await db.flush()

    return AuthContext(
        user_id=str(user.id),
        username=user.username,
        roles=tuple(role_names),
        permissions=frozenset(permissions),
        field_view_allowlist=frozenset(allowlist),
        session_id=str(session.id),
        csrf_token=session.csrf_token,
    )
