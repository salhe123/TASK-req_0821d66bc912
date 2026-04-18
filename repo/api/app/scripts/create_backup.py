"""Create a backup archive row. Runs inside the api container.

Usage:
    python -m app.scripts.create_backup

In production this is wrapped by a cron job in the db container that invokes
`pg_dump | gzip | openssl enc`; here we produce a dummy encrypted blob so the
admin UI and restore flow can exercise the full path offline.
"""
from __future__ import annotations

import asyncio
import sys

from app.core.db import get_session_maker
from app.services.audit import write_audit
from app.services.backup_archive import create_archive
from app.services.kek import load_kek


async def main() -> int:
    load_kek()
    maker = get_session_maker()
    async with maker() as db:
        archive = await create_archive(db)
        await write_audit(
            db,
            action="BACKUP_CREATE",
            resource_type="backup_archive",
            resource_id=archive.id,
            actor_user_id=None,
            payload={"filename": archive.filename, "size_bytes": archive.size_bytes,
                     "source": "cli"},
        )
        await db.commit()
        print(f"created {archive.filename} ({archive.size_bytes} bytes)")
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(main()))
