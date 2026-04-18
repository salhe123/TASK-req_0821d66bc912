"""GET /api/submissions/{id} + /api/submissions/{id}/trace detail payload."""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _seed_evaluator(dsn: str, username: str, password: str) -> str:
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


async def _produce_submission(admin_client, db_dsn, api_base_url):
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"sdtpl_{secrets.token_hex(3)}",
                "items": [{"key": "q1", "label": "Q", "weight": 1, "required": True,
                           "missing_strategy": "ZERO_FILL"}],
            },
        )
    ).json()
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "sd cycle",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=30)),
                "deadline_at": _iso(datetime.now(timezone.utc) + timedelta(days=10)),
                "timezone": "UTC",
                "makeup_enabled": False, "makeup_business_days": 5, "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()
    eval_user = f"sd_{secrets.token_hex(3)}"
    pw = "Detail-test-pwd-1"
    uid = _seed_evaluator(db_dsn, eval_user, pw)
    (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": uid},
        )
    ).raise_for_status()
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e:
        login = await e.post("/api/auth/login", json={"username": eval_user, "password": pw})
        e.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        mine = (await e.get("/api/assignments/mine/active")).json()
        aid = mine[0]["id"]
        await e.post(f"/api/assignments/{aid}/save", json={"values": {"q1": 6}})
        await e.post(f"/api/assignments/{aid}/submit", json={"values": {"q1": 6}})
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM submissions WHERE assignment_id = %s LIMIT 1", (aid,))
        return str(cur.fetchone()[0])


@pytest.mark.asyncio
async def test_submission_detail_payload_shape(admin_client, db_dsn, api_base_url) -> None:
    client, _ = admin_client
    sid = await _produce_submission(admin_client, db_dsn, api_base_url)
    r = await client.get(f"/api/submissions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {
        "id", "assignment_id", "template_version_id", "rule_set_version_id",
        "actor_user_id", "submitted_at",
    }
    assert body["id"] == sid


@pytest.mark.asyncio
async def test_submission_trace_payload_shape(admin_client, db_dsn, api_base_url) -> None:
    client, _ = admin_client
    sid = await _produce_submission(admin_client, db_dsn, api_base_url)
    r = await client.get(f"/api/submissions/{sid}/trace")
    assert r.status_code == 200
    body = r.json()
    assert body["submission_id"] == sid
    assert len(body["trace_hash"]) == 64
    trace = body["trace"]
    assert "engine_version" in trace
    assert "steps" in trace
    assert any(s["item_key"] == "q1" for s in trace["steps"])
    assert "totals" in trace


@pytest.mark.asyncio
async def test_submission_unknown_id_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.get("/api/submissions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    r2 = await client.get("/api/submissions/00000000-0000-0000-0000-000000000000/trace")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_submission_malformed_id_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.get("/api/submissions/not-a-uuid")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_trace_for_submission_missing_trace_returns_404(admin_client, db_dsn, api_base_url):
    """Edge case: if the trace row is missing the endpoint should surface 404
    not throw 500."""
    sid = await _produce_submission(admin_client, db_dsn, api_base_url)
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM calculation_traces WHERE submission_id = %s", (sid,))
    client, _ = admin_client
    r = await client.get(f"/api/submissions/{sid}/trace")
    assert r.status_code == 404
