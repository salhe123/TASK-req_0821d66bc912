"""Covers admin user-management surfaces: listing shape, unlock after lockout,
404 on unknown, permission-gated."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import httpx
import psycopg
import pytest


@pytest.mark.asyncio
async def test_list_users_payload_shape(admin_client) -> None:
    client, _ = admin_client
    r = await client.get("/api/admin/users")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    # Admin seeded by fixture is present and carries expected fields.
    admin_rows = [u for u in body["items"] if "Administrator" in u["roles"]]
    assert admin_rows
    sample = admin_rows[0]
    assert set(sample.keys()) == {
        "id", "username", "display_name", "is_active", "locked", "roles", "last_login_at"
    }


@pytest.mark.asyncio
async def test_create_user_without_display_name_defaults_empty(admin_client) -> None:
    client, _ = admin_client
    username = f"defaultname_{secrets.token_hex(3)}"
    r = await client.post(
        "/api/admin/users",
        json={"username": username, "password": "Solid-test-pwd-1", "roles": ["Evaluator"]},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["display_name"] == ""
    assert body["locked"] is False
    assert body["roles"] == ["Evaluator"]


@pytest.mark.asyncio
async def test_create_user_weak_password_rejected(admin_client) -> None:
    client, _ = admin_client
    r = await client.post(
        "/api/admin/users",
        json={"username": f"weak_{secrets.token_hex(3)}", "password": "short", "roles": []},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"


@pytest.mark.asyncio
async def test_unlock_user_clears_locked_until(admin_client, db_dsn: str) -> None:
    client, _ = admin_client
    username = f"unlock_{secrets.token_hex(3)}"
    create = await client.post(
        "/api/admin/users",
        json={"username": username, "password": "Pwd-for-unlock-1", "roles": ["Evaluator"]},
    )
    assert create.status_code == 201
    uid = create.json()["id"]

    # Mark the user locked directly in DB so we can test the unlock path.
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET locked_until = %s WHERE id = %s", (future, uid)
        )

    listing_before = (await client.get("/api/admin/users")).json()
    assert any(u["id"] == uid and u["locked"] is True for u in listing_before["items"])

    unlock = await client.post(f"/api/admin/users/{uid}/unlock")
    assert unlock.status_code == 200
    assert unlock.json() == {"id": uid, "unlocked": True}

    listing_after = (await client.get("/api/admin/users")).json()
    assert any(u["id"] == uid and u["locked"] is False for u in listing_after["items"])


@pytest.mark.asyncio
async def test_unlock_unknown_user_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.post("/api/admin/users/00000000-0000-0000-0000-000000000000/unlock")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


@pytest.mark.asyncio
async def test_unlock_malformed_id_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.post("/api/admin/users/not-a-uuid/unlock")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_cannot_list_users(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.get("/api/admin/users")
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_non_admin_cannot_unlock(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.post("/api/admin/users/00000000-0000-0000-0000-000000000000/unlock")
    assert r.status_code == 403
