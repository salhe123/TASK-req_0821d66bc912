from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.middleware.auth import get_auth
from app.models.rbac import Permission, Role
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "role", "manage")
    rows = (
        await db.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "field_view_allowlist": list(r.field_view_allowlist or []),
                "permissions": [
                    {"resource": p.resource, "action": p.action} for p in r.permissions
                ],
            }
            for r in rows
        ]
    }


@router.get("/permissions")
async def list_permissions(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "role", "manage")
    rows = (
        await db.execute(
            select(Permission).order_by(Permission.resource, Permission.action)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(p.id),
                "resource": p.resource,
                "action": p.action,
                "description": p.description,
            }
            for p in rows
        ]
    }
