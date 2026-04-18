"""Pure unit test for lockout arithmetic — `is_locked` only inspects
`locked_until`, so we pass a duck-typed stand-in rather than touching the
SQLAlchemy-instrumented User model."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.lockout import is_locked


def _user(locked_until):
    return SimpleNamespace(locked_until=locked_until)


def test_not_locked_when_locked_until_is_none():
    assert is_locked(_user(None)) is False


def test_locked_when_locked_until_in_future():
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert is_locked(_user(future)) is True


def test_not_locked_when_locked_until_in_past():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert is_locked(_user(past)) is False


def test_uses_provided_now():
    t = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    assert is_locked(_user(t + timedelta(seconds=1)), now=t) is True
    assert is_locked(_user(t - timedelta(seconds=1)), now=t) is False
