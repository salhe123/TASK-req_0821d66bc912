from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Forbidden, NotFound
from app.middleware.auth import get_auth
from app.models.plans import PlanShareLink, PlanVersion
from app.services.audit import write_audit
from app.services.rbac import AuthContext, ensure_permission
from app.services.share_tokens import hash_token, is_usable

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}")
async def resolve_share(
    token: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    # Resolution requires an active session AND the view_shared permission.
    ensure_permission(auth, "build_plan", "view_shared")

    link = (
        await db.execute(
            select(PlanShareLink).where(PlanShareLink.token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    if link is None:
        raise NotFound(message="share link not found")
    if not is_usable(expires_at=link.expires_at, revoked_at=link.revoked_at):
        raise Forbidden(
            error="share_link_invalid",
            message="share link is expired or revoked",
        )
    # The link was issued for a specific role context. The caller must either
    # hold that role (exact match) or have an admin wildcard permission.
    if link.role and link.role not in auth.roles and not auth.has_permission("*", "*"):
        raise Forbidden(
            error="share_link_role_mismatch",
            message="share link is bound to a different role",
            details={"required_role": link.role},
        )

    version = (
        await db.execute(
            select(PlanVersion)
            .where(PlanVersion.id == link.plan_version_id)
            .options(selectinload(PlanVersion.lines))
        )
    ).scalar_one()

    link.opened_at = datetime.now(timezone.utc)
    await write_audit(
        db,
        action="SHARE_LINK_OPEN",
        resource_type="plan_share_link",
        resource_id=link.id,
        actor_user_id=__import__("uuid").UUID(auth.user_id),
        payload={"plan_version_id": str(link.plan_version_id)},
    )
    await db.commit()
    return {
        "share_link_id": str(link.id),
        "plan_version_id": str(version.id),
        "role": link.role,
        "expires_at": link.expires_at.isoformat(),
        "version": {
            "id": str(version.id),
            "plan_id": str(version.plan_id),
            "version_no": version.version_no,
            "note": version.note,
            "created_at": version.created_at.isoformat(),
            "lines": [
                {
                    "line_identity_key": l.line_identity_key,
                    "part_number": l.part_number,
                    "description": l.description,
                    "quantity": str(l.quantity),
                    "unit": l.unit,
                    "notes": l.notes,
                    "tags": list(l.tags or []),
                }
                for l in sorted(version.lines, key=lambda x: x.line_identity_key)
            ],
        },
    }
