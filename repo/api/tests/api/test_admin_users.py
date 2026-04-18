import secrets

import httpx
import pytest


@pytest.mark.asyncio
async def test_admin_creates_user_and_audits(admin_client) -> None:
    client, _ = admin_client
    username = f"created_{secrets.token_hex(3)}"
    resp = await client.post(
        "/api/admin/users",
        json={
            "username": username,
            "display_name": "Created User",
            "password": "Fresh-Password-99",
            "roles": ["Evaluator"],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == username
    assert body["roles"] == ["Evaluator"]
    assert body["is_active"] is True
    assert body["locked"] is False


@pytest.mark.asyncio
async def test_admin_lists_users(admin_client) -> None:
    client, _ = admin_client
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert any(u["roles"] == ["Administrator"] for u in body["items"])


@pytest.mark.asyncio
async def test_non_admin_forbidden_on_user_management(evaluator_client) -> None:
    client, _ = evaluator_client
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_duplicate_username_returns_conflict(admin_client) -> None:
    client, _ = admin_client
    username = f"dup_{secrets.token_hex(3)}"
    body = {
        "username": username,
        "display_name": "d",
        "password": "Fresh-Password-99",
        "roles": ["Evaluator"],
    }
    r1 = await client.post("/api/admin/users", json=body)
    assert r1.status_code == 201
    r2 = await client.post("/api/admin/users", json=body)
    assert r2.status_code == 409
    assert r2.json()["error"] == "username_taken"


@pytest.mark.asyncio
async def test_unknown_role_returns_404(admin_client) -> None:
    client, _ = admin_client
    resp = await client.post(
        "/api/admin/users",
        json={
            "username": f"x_{secrets.token_hex(3)}",
            "display_name": "d",
            "password": "Fresh-Password-99",
            "roles": ["NoSuchRole"],
        },
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "not_found"
    assert body["details"]["roles"] == ["NoSuchRole"]
