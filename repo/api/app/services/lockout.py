from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.models.user import FailedLogin, User


async def count_failed_within_window(session: AsyncSession, username: str) -> int:
    settings = get_settings()
    window_start = datetime.now(timezone.utc) - timedelta(
        seconds=settings.login_lockout_window_seconds
    )
    stmt = select(func.count()).select_from(FailedLogin).where(
        FailedLogin.username_attempted == username,
        FailedLogin.attempted_at >= window_start,
    )
    return int((await session.execute(stmt)).scalar_one())


async def record_failed(session: AsyncSession, username: str, ip: str | None) -> None:
    session.add(FailedLogin(username_attempted=username, ip_address=ip))
    await session.flush()


async def clear_failures(session: AsyncSession, username: str) -> None:
    await session.execute(
        delete(FailedLogin).where(FailedLogin.username_attempted == username)
    )


def is_locked(user: User, now: datetime | None = None) -> bool:
    if user.locked_until is None:
        return False
    current = now or datetime.now(timezone.utc)
    return current < user.locked_until


async def apply_lockout_if_threshold(
    session: AsyncSession, user: User | None, username: str
) -> User | None:
    settings = get_settings()
    count = await count_failed_within_window(session, username)
    if count >= settings.login_lockout_threshold and user is not None:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            seconds=settings.login_lockout_window_seconds
        )
        await session.flush()
    return user
