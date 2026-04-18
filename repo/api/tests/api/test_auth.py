import secrets

import httpx
import psycopg
import pytest

from argon2 import PasswordHasher


def _seed_user(dsn: str, username: str, password: str, role: str = "Evaluator") -> str:
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_active) "
                "VALUES (%s, %s, %s, TRUE) RETURNING id",
                (username, username, hasher.hash(password)),
            )
            uid = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT %s, id FROM roles WHERE name = %s",
                (uid, role),
            )
    return uid


@pytest.mark.asyncio
async def test_login_returns_full_envelope(api_base_url: str, db_dsn: str) -> None:
    username = f"login_{secrets.token_hex(4)}"
    password = "Test-Password-1234"
    uid = _seed_user(db_dsn, username, password)

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "user_id", "username", "roles", "csrf_token", "session_token", "expires_at"
    }
    assert body["user_id"] == uid
    assert body["username"] == username
    assert body["roles"] == ["Evaluator"]
    assert len(body["csrf_token"]) >= 16
    assert body["session_token"].count(".") == 1


@pytest.mark.asyncio
async def test_login_invalid_credentials_envelope(api_base_url: str, db_dsn: str) -> None:
    username = f"bad_{secrets.token_hex(4)}"
    _seed_user(db_dsn, username, "Test-Password-1234")
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.post(
            "/api/auth/login", json={"username": username, "password": "wrong"}
        )
    assert resp.status_code == 401
    body = resp.json()
    assert body == {
        "error": "invalid_credentials",
        "message": "invalid username or password",
        "details": {},
    }


@pytest.mark.asyncio
async def test_lockout_after_five_failures(api_base_url: str, db_dsn: str) -> None:
    username = f"lock_{secrets.token_hex(4)}"
    _seed_user(db_dsn, username, "Correct-Password-99")

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        for i in range(5):
            resp = await client.post(
                "/api/auth/login", json={"username": username, "password": "nope"}
            )
            if i < 4:
                assert resp.status_code == 401
            else:
                assert resp.status_code == 423

        # sixth attempt — already locked
        resp = await client.post(
            "/api/auth/login", json={"username": username, "password": "Correct-Password-99"}
        )
        assert resp.status_code == 423
        body = resp.json()
        assert body["error"] == "account_locked"


@pytest.mark.asyncio
async def test_me_returns_permissions_and_allowlist(admin_client) -> None:
    client, _ = admin_client
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "user_id", "username", "display_name", "roles", "permissions",
        "field_view_allowlist", "timezone",
    }
    assert body["roles"] == ["Administrator"]
    # Administrator role carries wildcard allowlist
    assert "*" in body["field_view_allowlist"]
    perms = body["permissions"]
    assert any(p["resource"] == "user" and p["action"] == "manage" for p in perms)


@pytest.mark.asyncio
async def test_csrf_missing_returns_403(admin_client) -> None:
    client, info = admin_client
    # Override the client-level CSRF header with an empty value for this request.
    resp = await client.post(
        "/api/admin/users",
        json={"username": "whatever", "password": "abcdefghijkl", "roles": []},
        headers={"X-CSRF-Token": ""},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "csrf_missing"


@pytest.mark.asyncio
async def test_logout_revokes_session(admin_client) -> None:
    client, _ = admin_client
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    # next call should be unauthorized
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] in ("session_revoked", "session_not_found")


@pytest.mark.asyncio
async def test_change_password_then_relogin(admin_client, api_base_url: str) -> None:
    client, info = admin_client
    new_pw = "New-Password-Value-1"
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": info["password"], "new_password": new_pw},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client2:
        resp = await client2.post(
            "/api/auth/login",
            json={"username": info["username"], "password": new_pw},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_session_token_rejected(api_base_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer garbage.token"},
        )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] in ("token_malformed", "token_invalid_signature")
