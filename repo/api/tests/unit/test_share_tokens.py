from datetime import datetime, timedelta, timezone

from app.services.share_tokens import (
    MAX_TTL_DAYS,
    compute_expiry,
    hash_token,
    is_usable,
    new_token,
)


def test_new_token_length():
    t = new_token()
    assert len(t) >= 32


def test_hash_is_deterministic_64_chars_hex():
    t = "abc123"
    assert hash_token(t) == hash_token(t)
    h = hash_token(t)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_expiry_caps_at_7_days():
    exp = compute_expiry(365)
    delta = exp - datetime.now(timezone.utc)
    assert delta <= timedelta(days=MAX_TTL_DAYS) + timedelta(seconds=5)


def test_compute_expiry_floor_of_1_day():
    exp = compute_expiry(0)
    delta = exp - datetime.now(timezone.utc)
    assert delta >= timedelta(hours=23)


def test_is_usable_rejects_revoked():
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=1)
    assert is_usable(expires_at=exp, revoked_at=now, now=now) is False


def test_is_usable_rejects_expired():
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=1)
    assert is_usable(expires_at=past, revoked_at=None, now=now) is False


def test_is_usable_accepts_active_unrevoked():
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)
    assert is_usable(expires_at=future, revoked_at=None, now=now) is True
