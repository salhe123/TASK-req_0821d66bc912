"""Pure unit tests for the feedback rate-limit math using a fake session."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


class _FakeCountResult:
    def __init__(self, n: int):
        self.n = n

    def scalar_one(self):
        return self.n


class _FakeSession:
    def __init__(self, window_count: int):
        self._count = window_count

    async def execute(self, _stmt):
        return _FakeCountResult(self._count)


import pytest

from app.services.feedback import _window_count


@pytest.mark.asyncio
async def test_window_count_returns_scalar():
    s = _FakeSession(window_count=42)
    assert await _window_count(s, "subj", datetime.now(timezone.utc)) == 42
