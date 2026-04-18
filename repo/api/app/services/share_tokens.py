"""Plan share-link tokens.

A share link is a URL-safe random bearer issued to a specific plan_version + role
with an expiry (≤ 7 days). We persist only the sha256 of the token so the DB
row cannot be converted back into a usable URL.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


MAX_TTL_DAYS = 7


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compute_expiry(requested_days: int) -> datetime:
    days = max(1, min(int(requested_days), MAX_TTL_DAYS))
    return datetime.now(timezone.utc) + timedelta(days=days)


def is_usable(*, expires_at: datetime, revoked_at: datetime | None, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    if revoked_at is not None:
        return False
    if current >= expires_at:
        return False
    return True
