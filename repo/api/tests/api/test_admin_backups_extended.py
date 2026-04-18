"""Additional coverage for the backup surface: prune, list sort, non-admin
access, stage failure on unknown archive, commit without staged is 404."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
import pytest


@pytest.mark.asyncio
async def test_list_backups_orders_newest_first(admin_client) -> None:
    client, _ = admin_client
    first = (await client.post("/api/admin/backups")).json()
    second = (await client.post("/api/admin/backups")).json()

    listing = (await client.get("/api/admin/backups")).json()
    ids = [i["id"] for i in listing["items"]]
    idx_first = ids.index(first["id"])
    idx_second = ids.index(second["id"])
    # Newest (second) appears before first.
    assert idx_second < idx_first


@pytest.mark.asyncio
async def test_prune_no_op_when_nothing_older_than_retention(admin_client) -> None:
    client, _ = admin_client
    r = await client.post("/api/admin/backups/prune")
    assert r.status_code == 200
    assert r.json() == {"pruned": 0}


@pytest.mark.asyncio
async def test_prune_removes_rows_older_than_retention(
    admin_client, db_dsn: str
) -> None:
    client, _ = admin_client
    created = (await client.post("/api/admin/backups")).json()
    aid = created["id"]
    # Artificially age the row past the 30-day retention window.
    past = datetime.now(timezone.utc) - timedelta(days=45)
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("UPDATE backup_archives SET created_at = %s WHERE id = %s", (past, aid))

    r = await client.post("/api/admin/backups/prune")
    assert r.status_code == 200
    assert r.json()["pruned"] >= 1
    # Audit entry recorded the prune.
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs WHERE action = 'BACKUP_PRUNE' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0]["pruned_count"] >= 1


@pytest.mark.asyncio
async def test_stage_unknown_archive_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.post("/api/admin/backups/00000000-0000-0000-0000-000000000000/stage")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


@pytest.mark.asyncio
async def test_commit_without_staged_404(admin_client) -> None:
    client, _ = admin_client
    archive = (await client.post("/api/admin/backups")).json()
    r = await client.post(f"/api/admin/backups/{archive['id']}/commit")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


@pytest.mark.asyncio
async def test_archive_payload_carries_kek_fingerprint(admin_client) -> None:
    client, _ = admin_client
    created = (await client.post("/api/admin/backups")).json()
    assert len(created["kek_fingerprint"]) == 64
    assert len(created["manifest_hash"]) == 64
    # Fingerprint is stable per-run (same KEK)
    again = (await client.post("/api/admin/backups")).json()
    assert again["kek_fingerprint"] == created["kek_fingerprint"]
    assert again["manifest_hash"] != created["manifest_hash"]  # different random payload


@pytest.mark.asyncio
async def test_non_admin_forbidden_on_prune(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.post("/api/admin/backups/prune")
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"
