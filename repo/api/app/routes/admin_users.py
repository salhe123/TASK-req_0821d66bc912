from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.rbac import Role
from app.models.user import User
from app.schemas.admin import (
    UserCreateRequest,
    UserListResponse,
    UserSummary,
    UserUnlockResponse,
)
from app.services.audit import write_audit
from app.services.passwords import hash_password
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _summary(u: User) -> UserSummary:
    return UserSummary(
        id=str(u.id),
        username=u.username,
        display_name=u.display_name,
        is_active=u.is_active,
        locked=bool(u.locked_until is not None),
        roles=[r.name for r in u.roles],
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> UserListResponse:
    ensure_permission(auth, "user", "manage")
    users = (
        (await db.execute(select(User).options(selectinload(User.roles)).order_by(User.username)))
        .scalars()
        .all()
    )
    return UserListResponse(items=[_summary(u) for u in users])


@router.post("", response_model=UserSummary, status_code=201)
async def create_user(
    body: UserCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> UserSummary:
    ensure_permission(auth, "user", "manage")

    exists = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if exists is not None:
        raise Conflict(error="username_taken", message="username already exists")

    roles: list[Role] = []
    if body.roles:
        roles = list(
            (
                await db.execute(select(Role).where(Role.name.in_(body.roles)))
            ).scalars()
        )
        missing = set(body.roles) - {r.name for r in roles}
        if missing:
            raise NotFound(
                message="unknown role(s)",
                details={"roles": sorted(missing)},
            )

    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    user.roles = roles
    db.add(user)
    await db.flush()
    await write_audit(
        db,
        action="USER_CREATE",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"username": body.username, "roles": [r.name for r in roles]},
    )
    await db.commit()
    # refresh roles relationship
    user = (
        await db.execute(
            select(User).where(User.id == user.id).options(selectinload(User.roles))
        )
    ).scalar_one()
    return _summary(user)


@router.post("/{user_id}/unlock", response_model=UserUnlockResponse)
async def unlock_user(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> UserUnlockResponse:
    ensure_permission(auth, "user", "manage")
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFound(message="user not found")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        raise NotFound(message="user not found")
    user.locked_until = None
    await write_audit(
        db,
        action="USER_UNLOCK",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={},
    )
    await db.commit()
    return UserUnlockResponse(id=str(user.id), unlocked=True)
