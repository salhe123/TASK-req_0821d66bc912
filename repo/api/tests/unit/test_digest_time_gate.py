"""Pure unit test of the 9:00-local gate in build_digest using a fake session."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import digest as digest_module


class _FakeUser:
    def __init__(self, uid: uuid.UUID, digest_last_shown_date: date | None):
        self.id = uid
        self.digest_last_shown_date = digest_last_shown_date


class _FakeExecuteResult:
    def __init__(self, payload: Any):
        self._payload = payload

    def scalar_one_or_none(self):
        return self._payload

    def all(self):
        return []


class _FakeSession:
    def __init__(self, user: _FakeUser | None):
        self.user = user
        self.flushed = False

    async def execute(self, _stmt):
        return _FakeExecuteResult(self.user)

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_hidden_before_nine_local():
    uid = uuid.uuid4()
    user = _FakeUser(uid, digest_last_shown_date=None)
    db = _FakeSession(user)
    # 06:00 UTC = 06:00 UTC in UTC tz
    now = datetime(2026, 4, 18, 6, 0, tzinfo=timezone.utc)
    result = await digest_module.build_digest(db, user_id=uid, tz_name="UTC", now_utc=now)
    assert result.show is False
    assert user.digest_last_shown_date is None


@pytest.mark.asyncio
async def test_shown_after_nine_local_and_stamps_date():
    uid = uuid.uuid4()
    user = _FakeUser(uid, digest_last_shown_date=None)
    db = _FakeSession(user)
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    result = await digest_module.build_digest(db, user_id=uid, tz_name="UTC", now_utc=now)
    assert result.show is True
    assert user.digest_last_shown_date == date(2026, 4, 18)
    assert db.flushed


@pytest.mark.asyncio
async def test_not_shown_twice_same_day():
    uid = uuid.uuid4()
    user = _FakeUser(uid, digest_last_shown_date=date(2026, 4, 18))
    db = _FakeSession(user)
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    result = await digest_module.build_digest(db, user_id=uid, tz_name="UTC", now_utc=now)
    assert result.show is False


@pytest.mark.asyncio
async def test_resurfaces_next_day():
    uid = uuid.uuid4()
    user = _FakeUser(uid, digest_last_shown_date=date(2026, 4, 17))
    db = _FakeSession(user)
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    result = await digest_module.build_digest(db, user_id=uid, tz_name="UTC", now_utc=now)
    assert result.show is True
    assert user.digest_last_shown_date == date(2026, 4, 18)


@pytest.mark.asyncio
async def test_tz_shifts_the_nine_am_gate():
    # In New York, 13:00 UTC = 09:00 local during standard time.
    uid = uuid.uuid4()
    user = _FakeUser(uid, digest_last_shown_date=None)
    db = _FakeSession(user)
    now = datetime(2026, 4, 18, 12, 30, tzinfo=timezone.utc)  # 08:30 EDT
    result = await digest_module.build_digest(db, user_id=uid, tz_name="America/New_York", now_utc=now)
    assert result.show is False
    # 13:30 UTC = 09:30 EDT — after the gate
    now2 = datetime(2026, 4, 18, 13, 30, tzinfo=timezone.utc)
    result2 = await digest_module.build_digest(db, user_id=uid, tz_name="America/New_York", now_utc=now2)
    assert result2.show is True
