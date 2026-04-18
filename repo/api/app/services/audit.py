from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import request_id_ctx
from app.models.audit import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        actor_user_id=actor_user_id,
        request_id=request_id_ctx.get(),
        payload=payload or {},
    )
    db.add(row)
    await db.flush()
    return row
