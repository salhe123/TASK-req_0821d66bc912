"""Nightly backup scheduler.

A lightweight asyncio loop that wakes up at the configured local hour and
invokes :func:`create_archive` + :func:`prune_old`. The scheduler is started
by the FastAPI lifespan hook and stopped when the app shuts down. If the
`backup_scheduler_enabled` setting is false (test mode) it never runs.

The scheduler is intentionally simple — one tick per minute, a single
per-day guard (`_last_run_date`) so an error or a restart near the trigger
hour cannot produce duplicate nightly archives.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.db import get_session_maker
from app.core.settings import get_settings
from app.services.audit import write_audit
from app.services.backup_archive import create_archive, prune_old

logger = logging.getLogger("api.backup_scheduler")


class BackupScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_run_date: date | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="backup_scheduler")
        logger.info("backup_scheduler_started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except asyncio.TimeoutError:
            self._task.cancel()
        self._task = None
        logger.info("backup_scheduler_stopped")

    async def _run(self) -> None:
        settings = get_settings()
        tz = ZoneInfo(settings.backup_scheduler_timezone)
        trigger_hour = settings.backup_scheduler_hour
        while not self._stop.is_set():
            try:
                await self._tick(tz, trigger_hour)
            except Exception:
                logger.exception("backup_scheduler_tick_failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                continue

    async def _tick(self, tz: ZoneInfo, trigger_hour: int) -> None:
        now_local = datetime.now(tz)
        if now_local.hour < trigger_hour:
            return
        if self._last_run_date == now_local.date():
            return
        logger.info(
            "backup_scheduler_running local_time=%s", now_local.isoformat()
        )
        maker = get_session_maker()
        async with maker() as db:
            archive = await create_archive(db)
            await write_audit(
                db,
                action="BACKUP_CREATE",
                resource_type="backup_archive",
                resource_id=archive.id,
                actor_user_id=None,
                payload={
                    "filename": archive.filename,
                    "size_bytes": archive.size_bytes,
                    "source": "scheduler",
                },
            )
            pruned = await prune_old(db)
            if pruned:
                await write_audit(
                    db,
                    action="BACKUP_PRUNE",
                    resource_type="backup_archive",
                    resource_id=None,
                    actor_user_id=None,
                    payload={"pruned_count": pruned, "source": "scheduler"},
                )
            await db.commit()
        self._last_run_date = now_local.date()


_singleton: BackupScheduler | None = None


def get_scheduler() -> BackupScheduler:
    global _singleton
    if _singleton is None:
        _singleton = BackupScheduler()
    return _singleton
