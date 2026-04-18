from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.middleware.auth import get_auth
from app.models.audit import AuditLog
from app.services.masking import mask_list
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/admin/audit", tags=["admin"])

AUDIT_SENSITIVE_FIELDS = ("payload", "actor_user_id")


@router.get("/logs")
async def list_audit_logs(
    actor_user_id: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "audit", "read")

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if actor_user_id:
        try:
            stmt = stmt.where(AuditLog.actor_user_id == uuid.UUID(actor_user_id))
        except ValueError:
            return {"items": []}
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at <= until)

    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": str(r.id),
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "request_id": r.request_id,
            "payload": r.payload or {},
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return {"items": mask_list(items, AUDIT_SENSITIVE_FIELDS, auth)}
