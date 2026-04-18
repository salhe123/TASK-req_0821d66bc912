from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.backup import BackupArchive, RestoreEvent, RestoreState
from app.core.settings import get_settings
from app.services import maintenance
from app.services.audit import write_audit
from app.services.backup_archive import (
    BackupRestoreError,
    create_archive,
    manifest_hash_for_bytes,
    prune_old,
    read_archive_bytes,
    restore_archive,
    verify_kek_fingerprint,
)
from app.core.errors import ApiError
from app.services.kek import kek_fingerprint
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/admin/backups", tags=["admin"])


def _archive_out(r: BackupArchive) -> dict:
    return {
        "id": str(r.id),
        "filename": r.filename,
        "size_bytes": r.size_bytes,
        "manifest_hash": r.manifest_hash,
        "kek_fingerprint": r.kek_fingerprint,
        "created_at": r.created_at.isoformat(),
    }


def _restore_out(r: RestoreEvent) -> dict:
    return {
        "id": str(r.id),
        "archive_id": str(r.archive_id),
        "state": r.state,
        "started_by": str(r.started_by) if r.started_by else None,
        "kek_fingerprint": r.kek_fingerprint,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "notes": r.notes or {},
    }


async def _active_staged(db: AsyncSession) -> RestoreEvent | None:
    stmt = (
        select(RestoreEvent)
        .where(RestoreEvent.state == RestoreState.STAGED.value)
        .order_by(RestoreEvent.started_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@router.get("")
async def list_backups(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "backup", "manage")
    rows = (
        await db.execute(select(BackupArchive).order_by(BackupArchive.created_at.desc()))
    ).scalars().all()
    return {"items": [_archive_out(r) for r in rows]}


@router.post("", status_code=201)
async def create_archive_now(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "backup", "manage")
    archive = await create_archive(db)
    await write_audit(
        db,
        action="BACKUP_CREATE",
        resource_type="backup_archive",
        resource_id=archive.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"filename": archive.filename, "size_bytes": archive.size_bytes},
    )
    await db.commit()
    return _archive_out(archive)


@router.post("/{archive_id}/stage")
async def stage_restore(
    archive_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "backup", "manage")
    try:
        aid = uuid.UUID(archive_id)
    except ValueError:
        raise NotFound(message="archive not found")

    if await _active_staged(db):
        raise Conflict(error="restore_already_staged", message="a restore is already staged")

    archive = (
        await db.execute(select(BackupArchive).where(BackupArchive.id == aid))
    ).scalar_one_or_none()
    if archive is None:
        raise NotFound(message="archive not found")

    if not verify_kek_fingerprint(archive.kek_fingerprint):
        raise Conflict(
            error="kek_fingerprint_mismatch",
            message="archive was encrypted with a different KEK",
            details={
                "archive_fingerprint": archive.kek_fingerprint,
                "current_fingerprint": kek_fingerprint(),
            },
        )

    # Recompute manifest hash from the on-disk file and compare
    from pathlib import Path
    settings = get_settings()
    path = Path(settings.backup_volume) / archive.filename
    if path.exists():
        actual_hash = manifest_hash_for_bytes(read_archive_bytes(path))
        if actual_hash != archive.manifest_hash:
            raise Conflict(
                error="manifest_hash_mismatch",
                message="archive bytes do not match recorded manifest hash",
            )

    event = RestoreEvent(
        archive_id=archive.id,
        state=RestoreState.STAGED.value,
        started_by=uuid.UUID(auth.user_id),
        kek_fingerprint=kek_fingerprint(),
        notes={"stage": "entered maintenance mode"},
    )
    db.add(event)
    await db.flush()

    maintenance.enter(
        archive_id=str(archive.id),
        started_by=auth.user_id,
        reason="backup restore staged",
    )
    await db.commit()
    return {"maintenance": maintenance.snapshot(), "restore": _restore_out(event)}


@router.post("/{archive_id}/commit")
async def commit_restore(
    archive_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "backup", "manage")
    event = await _active_staged(db)
    if event is None or str(event.archive_id) != archive_id:
        raise NotFound(message="no staged restore for this archive")

    settings = get_settings()
    restore_notes: dict[str, str] = {}
    if settings.backup_restore_execute:
        archive = (
            await db.execute(
                select(BackupArchive).where(BackupArchive.id == event.archive_id)
            )
        ).scalar_one()
        # Actually perform the restore. On failure we leave maintenance mode
        # on and mark the event aborted; operator must intervene.
        try:
            restore_archive(archive)
            restore_notes["commit"] = "pg_restore applied"
        except BackupRestoreError as exc:
            event.state = RestoreState.ABORTED.value
            event.completed_at = datetime.now(timezone.utc)
            event.notes = {**(event.notes or {}), "commit_failed": str(exc)}
            await db.flush()
            await write_audit(
                db,
                action="BACKUP_RESTORE",
                resource_type="backup_archive",
                resource_id=event.archive_id,
                actor_user_id=uuid.UUID(auth.user_id),
                payload={
                    "restore_event_id": str(event.id),
                    "final_state": "aborted",
                    "error": str(exc),
                    "kek_fingerprint": event.kek_fingerprint,
                    "administrator_id": auth.user_id,
                },
            )
            await db.commit()
            maintenance.exit_()
            raise ApiError(
                error="restore_failed",
                message=f"backup restore failed: {exc}",
                status_code=500,
            )
    else:
        restore_notes["commit"] = "state-machine only (backup_restore_execute=false)"

    event.state = RestoreState.COMMITTED.value
    event.completed_at = datetime.now(timezone.utc)
    event.notes = {**(event.notes or {}), **restore_notes}
    await db.flush()

    await write_audit(
        db,
        action="BACKUP_RESTORE",
        resource_type="backup_archive",
        resource_id=event.archive_id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "restore_event_id": str(event.id),
            "final_state": "committed",
            "kek_fingerprint": event.kek_fingerprint,
            "administrator_id": auth.user_id,
        },
    )
    await db.commit()
    maintenance.exit_()
    return _restore_out(event)


@router.post("/{archive_id}/abort")
async def abort_restore(
    archive_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "backup", "manage")
    event = await _active_staged(db)
    if event is None or str(event.archive_id) != archive_id:
        raise NotFound(message="no staged restore for this archive")

    event.state = RestoreState.ABORTED.value
    event.completed_at = datetime.now(timezone.utc)
    event.notes = {**(event.notes or {}), "abort": "no swap performed"}
    await db.flush()

    await write_audit(
        db,
        action="BACKUP_RESTORE",
        resource_type="backup_archive",
        resource_id=event.archive_id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "restore_event_id": str(event.id),
            "final_state": "aborted",
            "kek_fingerprint": event.kek_fingerprint,
            "administrator_id": auth.user_id,
        },
    )
    await db.commit()
    maintenance.exit_()
    return _restore_out(event)


@router.post("/prune")
async def prune_backups(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "backup", "manage")
    pruned = await prune_old(db)
    if pruned:
        await write_audit(
            db,
            action="BACKUP_PRUNE",
            resource_type="backup_archive",
            resource_id=None,
            actor_user_id=uuid.UUID(auth.user_id),
            payload={"pruned_count": pruned},
        )
    await db.commit()
    return {"pruned": pruned}
