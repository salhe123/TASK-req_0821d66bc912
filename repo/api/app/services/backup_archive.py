"""Backup archive helpers.

Archives capture a **real** Postgres dump (`pg_dump -Fc`) of the application
database, compressed and then AES-GCM encrypted under a key derived from the
KEK. The framing on disk is:

    MAGIC (4 bytes)  = b"MGEW"
    VERSION (1 byte) = 0x01
    NONCE  (12 bytes) = random per write
    CIPHERTEXT+TAG   = AES-GCM(plaintext) with 16-byte auth tag appended

`restore_archive` is the inverse: it reads the encrypted file from
`BACKUP_VOLUME`, authenticates + decrypts, and shells out to `pg_restore` to
rehydrate the target database in place (non-destructive clean-and-restore).

The KEK fingerprint is bound as AEAD associated data so an archive cannot
be silently restored under a different KEK. The file name is recorded on the
`backup_archives` row; rotation/prune removes both metadata and on-disk file.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.models.backup import BackupArchive
from app.services.kek import kek_fingerprint, load_kek


logger = logging.getLogger("api.backup_archive")

RETENTION_DAYS = 30
MAGIC = b"MGEW"
VERSION = 0x01
NONCE_LEN = 12
KEY_LEN = 32
HEADER_LEN = len(MAGIC) + 1 + NONCE_LEN  # magic + version + nonce
PG_DUMP_TIMEOUT_SECONDS = 300
PG_RESTORE_TIMEOUT_SECONDS = 600


class BackupDecryptError(Exception):
    """Raised when an archive cannot be decrypted (wrong KEK, tampering, or
    malformed framing)."""


class BackupRestoreError(Exception):
    """Raised when pg_dump/pg_restore fails or the archive is missing."""


def manifest_hash_for_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _derive_key() -> bytes:
    return hashlib.sha256(load_kek()).digest()


def encrypt_payload(plaintext: bytes) -> bytes:
    nonce = os.urandom(NONCE_LEN)
    aesgcm = AESGCM(_derive_key())
    ct = aesgcm.encrypt(nonce, plaintext, kek_fingerprint().encode("ascii"))
    return MAGIC + bytes([VERSION]) + nonce + ct


def decrypt_payload(blob: bytes) -> bytes:
    if len(blob) < HEADER_LEN + 16:
        raise BackupDecryptError("archive too small")
    if blob[:4] != MAGIC:
        raise BackupDecryptError("bad magic")
    if blob[4] != VERSION:
        raise BackupDecryptError(f"unsupported version {blob[4]}")
    nonce = blob[5 : 5 + NONCE_LEN]
    ct = blob[HEADER_LEN:]
    aesgcm = AESGCM(_derive_key())
    try:
        return aesgcm.decrypt(nonce, ct, kek_fingerprint().encode("ascii"))
    except InvalidTag as exc:
        raise BackupDecryptError(
            "authentication failed — wrong KEK or tampered archive"
        ) from exc


def read_archive_bytes(path: Path) -> bytes:
    return path.read_bytes()


def verify_kek_fingerprint(expected_fingerprint: str) -> bool:
    return hmac.compare_digest(kek_fingerprint(), expected_fingerprint)


def _postgres_env_from_url(url: str) -> dict[str, str]:
    """Translate the SQLAlchemy sync DSN into libpq env vars that pg_dump /
    pg_restore understand. We don't pass credentials on the command line."""
    parsed = urlparse(url.split("+", 1)[-1] if "+" in url else url)
    env: dict[str, str] = {}
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = parsed.username
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    if parsed.path and len(parsed.path) > 1:
        env["PGDATABASE"] = parsed.path.lstrip("/")
    return env


def _pg_dump_bytes() -> bytes:
    """Run `pg_dump -Fc` against the configured database and return the
    compressed custom-format archive bytes."""
    settings = get_settings()
    env = {**os.environ, **_postgres_env_from_url(settings.database_url_sync)}
    try:
        result = subprocess.run(
            ["pg_dump", "-Fc", "--no-owner", "--no-acl"],
            env=env,
            capture_output=True,
            timeout=PG_DUMP_TIMEOUT_SECONDS,
            check=True,
        )
    except FileNotFoundError as exc:
        raise BackupRestoreError(
            "pg_dump binary not found — install postgresql-client in the api image"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupRestoreError(f"pg_dump timed out after {PG_DUMP_TIMEOUT_SECONDS}s") from exc
    except subprocess.CalledProcessError as exc:
        raise BackupRestoreError(
            f"pg_dump failed ({exc.returncode}): {exc.stderr.decode('utf-8', 'replace')[:2000]}"
        ) from exc
    return result.stdout


def _pg_restore_bytes(dump_bytes: bytes) -> None:
    """Apply a `pg_dump -Fc` archive in-place with `pg_restore --clean
    --if-exists`. This drops + recreates each object rather than requiring a
    fully empty target."""
    settings = get_settings()
    env = {**os.environ, **_postgres_env_from_url(settings.database_url_sync)}
    try:
        subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                "--single-transaction",
                "--dbname",
                env.get("PGDATABASE", ""),
            ],
            env=env,
            input=dump_bytes,
            capture_output=True,
            timeout=PG_RESTORE_TIMEOUT_SECONDS,
            check=True,
        )
    except FileNotFoundError as exc:
        raise BackupRestoreError(
            "pg_restore binary not found — install postgresql-client in the api image"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupRestoreError(
            f"pg_restore timed out after {PG_RESTORE_TIMEOUT_SECONDS}s"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise BackupRestoreError(
            f"pg_restore failed ({exc.returncode}): {exc.stderr.decode('utf-8', 'replace')[:2000]}"
        ) from exc


async def create_archive(
    db: AsyncSession, *, contents: bytes | None = None
) -> BackupArchive:
    """Dump the database (or use a caller-supplied payload for tests),
    encrypt it under the KEK, persist the file, and record a metadata row."""
    settings = get_settings()
    backup_dir: Path = settings.backup_volume
    backup_dir.mkdir(parents=True, exist_ok=True)

    payload = contents if contents is not None else _pg_dump_bytes()
    encrypted = encrypt_payload(payload)

    name = f"mgew-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.bin"
    path = backup_dir / name
    path.write_bytes(encrypted)

    row = BackupArchive(
        filename=name,
        size_bytes=len(encrypted),
        manifest_hash=manifest_hash_for_bytes(encrypted),
        kek_fingerprint=kek_fingerprint(),
    )
    db.add(row)
    await db.flush()
    logger.info(
        "backup_archive_created filename=%s plaintext_bytes=%d encrypted_bytes=%d",
        name,
        len(payload),
        len(encrypted),
    )
    return row


# Back-compat alias — the old name is still referenced by a couple of call
# sites and legacy tests. New code should call `create_archive` directly.
create_dummy_archive = create_archive


def restore_archive(archive: BackupArchive) -> None:
    """Load the archive from disk, decrypt under the current KEK, and
    rehydrate the target database via pg_restore. Raises on any failure."""
    settings = get_settings()
    path = Path(settings.backup_volume) / archive.filename
    if not path.exists():
        raise BackupRestoreError(f"archive file missing: {path}")
    blob = path.read_bytes()
    if manifest_hash_for_bytes(blob) != archive.manifest_hash:
        raise BackupRestoreError("archive manifest hash mismatch — file has been altered")
    if not verify_kek_fingerprint(archive.kek_fingerprint):
        raise BackupRestoreError(
            "archive was encrypted with a different KEK than the live fingerprint"
        )
    try:
        plaintext = decrypt_payload(blob)
    except BackupDecryptError as exc:
        raise BackupRestoreError(str(exc)) from exc
    _pg_restore_bytes(plaintext)
    logger.info(
        "backup_archive_restored filename=%s plaintext_bytes=%d",
        archive.filename,
        len(plaintext),
    )


async def prune_old(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Delete backup_archives rows older than the retention window and remove
    the matching on-disk files. Returns the number of rows pruned."""
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=RETENTION_DAYS)
    rows = (
        await db.execute(
            select(BackupArchive.id, BackupArchive.filename).where(
                BackupArchive.created_at < cutoff
            )
        )
    ).all()
    if not rows:
        return 0
    settings = get_settings()
    backup_dir: Path = settings.backup_volume
    for _id, filename in rows:
        p = backup_dir / filename
        try:
            p.unlink(missing_ok=True)
        except OSError as exc:
            # Log and continue — the metadata row is still cleared so we
            # don't leak stale references. Orphan files can be removed by
            # the operator.
            logger.warning(
                "backup_archive_unlink_failed filename=%s err=%s", filename, exc
            )
    await db.execute(
        delete(BackupArchive).where(BackupArchive.id.in_([r[0] for r in rows]))
    )
    return len(rows)
