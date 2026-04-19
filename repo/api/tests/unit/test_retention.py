"""Unit test for retention-pruning logic using a fake async session."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


class _FakeSelectResult:
    def __init__(self, ids):
        self._ids = ids

    def scalars(self):
        class _S:
            def __init__(s, ids):
                s._ids = ids

            def all(s):
                return s._ids
        return _S(self._ids)

    def all(self):
        # Post-audit `prune_old` selects `(id, filename)` tuples and calls
        # `.all()` directly. Synthesise a filename so the unlink loop is a
        # no-op against the non-existent BACKUP_VOLUME path in this unit env.
        return [(str(i), f"mgew-{i}.bin") for i in self._ids]


class _FakeSession:
    def __init__(self, ids_to_return):
        self._ids = ids_to_return
        self.deleted = 0

    async def execute(self, stmt):
        # First execute returns the select; second is the delete
        if self.deleted == 0:
            self.deleted = -1
            return _FakeSelectResult(self._ids)
        return None


@pytest.mark.asyncio
async def test_prune_old_noop_when_no_rows():
    from app.services.backup_archive import prune_old

    # First call returns empty → prune does nothing and never executes the delete
    session = _FakeSession([])
    n = await prune_old(session, now=datetime.now(timezone.utc))
    assert n == 0


@pytest.mark.asyncio
async def test_prune_old_reports_count():
    from app.services.backup_archive import prune_old

    fake_ids = ["1", "2", "3"]
    session = _FakeSession(fake_ids)
    n = await prune_old(session, now=datetime.now(timezone.utc))
    assert n == 3


def test_retention_window_is_30_days():
    from app.services.backup_archive import RETENTION_DAYS

    assert RETENTION_DAYS == 30
