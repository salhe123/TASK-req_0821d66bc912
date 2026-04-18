from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import ApiError, Locked, Unauthorized
from app.core.settings import get_settings
from app.middleware.auth import CSRF_HEADER, SESSION_COOKIE_NAME, get_auth
from app.models.rbac import Role
from app.models.user import Session as DbSession
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    UpdateTimezoneRequest,
)
from app.services.audit import write_audit
from app.services import metrics
from app.services.lockout import (
    apply_lockout_if_threshold,
    clear_failures,
    count_failed_within_window,
    is_locked,
    record_failed,
)
from app.services.passwords import hash_password, verify_password, needs_rehash
from app.services.rbac import AuthContext
from app.services.session_tokens import issue_token, new_csrf_token

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_TTL_SECONDS = 12 * 3600


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> LoginResponse:
    ip = _client_ip(request)
    user = (
        await db.execute(
            select(User)
            .where(User.username == payload.username)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
    ).scalar_one_or_none()

    if user is not None and is_locked(user):
        raise Locked(message="account is locked, try again later")

    password_ok = user is not None and user.is_active and verify_password(
        payload.password, user.password_hash
    )

    if not password_ok:
        await record_failed(db, payload.username, ip)
        await apply_lockout_if_threshold(db, user, payload.username)
        await db.commit()
        count = await count_failed_within_window(db, payload.username)
        if user is not None and is_locked(user):
            raise Locked(message="account locked after too many failed attempts")
        raise Unauthorized(
            error="invalid_credentials",
            message="invalid username or password",
        )

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    await clear_failures(db, payload.username)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=SESSION_TTL_SECONDS)
    csrf = new_csrf_token()
    db_session = DbSession(
        user_id=user.id,
        csrf_token=csrf,
        expires_at=expires_at,
    )
    db.add(db_session)
    await db.flush()
    user.last_login_at = now

    token = issue_token(str(db_session.id), str(user.id), nonce=csrf)

    await write_audit(
        db,
        action="USER_LOGIN",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        payload={"ip": ip},
    )
    await db.commit()
    await _refresh_active_session_gauge(db)

    settings = get_settings()
    cookie_secure = settings.cookie_secure or settings.environment == "production"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=cookie_secure,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )

    return LoginResponse(
        user_id=str(user.id),
        username=user.username,
        roles=[r.name for r in user.roles],
        csrf_token=csrf,
        session_token=token,
        expires_at=expires_at.isoformat(),
    )


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict[str, bool]:
    session = (
        await db.execute(select(DbSession).where(DbSession.id == auth.session_id))
    ).scalar_one_or_none()
    if session is not None:
        session.revoked_at = datetime.now(timezone.utc)
    await write_audit(
        db,
        action="USER_LOGOUT",
        resource_type="user",
        resource_id=auth.user_id,
        actor_user_id=_uuid(auth.user_id),
        payload={},
    )
    await db.commit()
    await _refresh_active_session_gauge(db)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict[str, bool]:
    user = (
        await db.execute(select(User).where(User.id == _uuid(auth.user_id)))
    ).scalar_one_or_none()
    if user is None:
        raise Unauthorized(error="user_inactive", message="user inactive")
    if not verify_password(payload.current_password, user.password_hash):
        raise ApiError(
            error="invalid_current_password",
            message="current password is incorrect",
            status_code=400,
        )
    user.password_hash = hash_password(payload.new_password)
    await write_audit(
        db,
        action="USER_PASSWORD_CHANGE",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        payload={},
    )
    await db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> MeResponse:
    tz = (
        await db.execute(select(User.timezone).where(User.id == _uuid(auth.user_id)))
    ).scalar_one_or_none() or "UTC"
    return MeResponse(
        user_id=auth.user_id,
        username=auth.username,
        display_name="",
        roles=list(auth.roles),
        permissions=[{"resource": r, "action": a} for (r, a) in sorted(auth.permissions)],
        field_view_allowlist=sorted(auth.field_view_allowlist),
        timezone=tz,
    )


@router.post("/me/timezone")
async def update_timezone(
    body: UpdateTimezoneRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict[str, str]:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError:
        raise ApiError(
            error="invalid_timezone",
            message=f"unknown IANA timezone: {body.timezone}",
            status_code=400,
        )
    user = (
        await db.execute(select(User).where(User.id == _uuid(auth.user_id)))
    ).scalar_one_or_none()
    if user is None:
        raise Unauthorized(error="user_inactive", message="user inactive")
    user.timezone = body.timezone
    await write_audit(
        db,
        action="USER_TIMEZONE_UPDATE",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        payload={"timezone": body.timezone},
    )
    await db.commit()
    return {"timezone": body.timezone}


def _uuid(value: str):
    import uuid as _u

    return _u.UUID(value)


async def _refresh_active_session_gauge(db: AsyncSession) -> None:
    from sqlalchemy import func
    now = datetime.now(timezone.utc)
    row = (
        await db.execute(
            select(func.count(DbSession.id)).where(
                DbSession.revoked_at.is_(None),
                DbSession.expires_at > now,
            )
        )
    ).scalar_one()
    metrics.set_active_sessions(int(row or 0))
