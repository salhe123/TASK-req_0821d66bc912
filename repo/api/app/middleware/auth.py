from __future__ import annotations

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Forbidden, Unauthorized
from app.services.auth_context import build_auth_context
from app.services.rbac import AuthContext
from app.services.session_tokens import verify_token

SESSION_COOKIE_NAME = "mgew_session"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _extract_token(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return cookie


async def get_optional_auth(
    request: Request,
    db: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> AuthContext | None:
    token = _extract_token(request, authorization)
    if not token:
        return None
    payload = verify_token(token)
    return await build_auth_context(db, payload)


async def get_auth(
    request: Request,
    db: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    token = _extract_token(request, authorization)
    if not token:
        raise Unauthorized(error="missing_session", message="session token missing")
    payload = verify_token(token)
    auth = await build_auth_context(db, payload)
    if request.method not in SAFE_METHODS:
        presented = request.headers.get(CSRF_HEADER, "")
        if not presented or presented != auth.csrf_token:
            raise Forbidden(error="csrf_missing", message="CSRF token missing or invalid")
    return auth
