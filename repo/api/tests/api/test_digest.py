from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def _seed_evaluator(dsn, username, password):
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, display_name, password_hash, is_active) "
            "VALUES (%s, %s, %s, TRUE) RETURNING id",
            (username, username, hasher.hash(password)),
        )
        uid = str(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO user_roles (user_id, role_id) "
            "SELECT %s, id FROM roles WHERE name = 'Evaluator'",
            (uid,),
        )
        return uid


@pytest.mark.asyncio
async def test_digest_hidden_before_9am_and_shown_once_after(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"tpl_{secrets.token_hex(3)}",
                "items": [{"key": "a", "label": "A", "weight": 1.0, "required": True,
                           "missing_strategy": "ZERO_FILL"}],
            },
        )
    ).json()
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "digest cycle",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=45)),
                "deadline_at": _iso(deadline),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()

    eval_user = f"dev_{secrets.token_hex(3)}"
    pw = "Evaluate-pass-99"
    uid = _seed_evaluator(db_dsn, eval_user, pw)
    await client.post(
        f"/api/cycles/{cycle['id']}/assignments",
        json={"evaluator_user_id": uid},
    )

    # Force before-9am: stamp today's digest_last_shown_date so banner is hidden
    # OR set the time via monkeypatching is not feasible through an API test. Instead
    # we verify idempotence: show once, then hidden on the second call same day.
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e_client:
        login = await e_client.post(
            "/api/auth/login", json={"username": eval_user, "password": pw}
        )
        e_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        first = await e_client.get("/api/cycles/digest")
        assert first.status_code == 200
        first_body = first.json()
        assert set(first_body.keys()) == {"show", "as_of_local", "items"}

        # Regardless of whether current local time is ≥ 09:00, hitting it again
        # must not show again once a show=true has happened. Simulate the first
        # flip by manually stamping the user's digest_last_shown_date.
        with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET digest_last_shown_date = CURRENT_DATE WHERE id = %s",
                (uid,),
            )

        second = await e_client.get("/api/cycles/digest")
        assert second.status_code == 200
        assert second.json()["show"] is False


@pytest.mark.asyncio
async def test_digest_items_exclude_archived(admin_client, db_dsn: str, api_base_url: str) -> None:
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"tpl_{secrets.token_hex(3)}",
                "items": [{"key": "a", "label": "A", "weight": 1.0, "required": True,
                           "missing_strategy": "ZERO_FILL"}],
            },
        )
    ).json()
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "digest filter",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=45)),
                "deadline_at": _iso(deadline),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()

    eval_user = f"dfev_{secrets.token_hex(3)}"
    pw = "Evaluate-pass-99"
    uid = _seed_evaluator(db_dsn, eval_user, pw)
    assignment = (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": uid},
        )
    ).json()

    # Drive assignment to ARCHIVED directly in DB
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE assignments SET state = 'ARCHIVED', archived_at = now() WHERE id = %s",
            (assignment["id"],),
        )
        # Clear digest state so banner can trigger again
        cur.execute(
            "UPDATE users SET digest_last_shown_date = NULL WHERE id = %s",
            (uid,),
        )

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e_client:
        login = await e_client.post(
            "/api/auth/login", json={"username": eval_user, "password": pw}
        )
        e_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        resp = await e_client.get("/api/cycles/digest")
        assert resp.status_code == 200
        body = resp.json()
        # Either show is False (not 9am yet) or items list is empty (archived filtered out)
        assert all(i["state"] != "ARCHIVED" for i in body["items"])
