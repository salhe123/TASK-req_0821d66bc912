from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _seed(dsn, username, password, role):
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
            "SELECT %s, id FROM roles WHERE name = %s",
            (uid, role),
        )
    return uid


@pytest.mark.asyncio
async def test_submit_writes_trace_and_returns_hash(admin_client, db_dsn, api_base_url):
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"scoretpl_{secrets.token_hex(3)}",
                "items": [
                    {"key": "q1", "label": "Q1", "weight": 1.0, "required": True,
                     "missing_strategy": "ZERO_FILL", "min_value": 0, "max_value": 10},
                    {"key": "q2", "label": "Q2", "weight": 2.0, "required": True,
                     "missing_strategy": "EXCLUDE_FROM_DENOMINATOR"},
                ],
            },
        )
    ).json()

    deadline = datetime.now(timezone.utc) + timedelta(days=10)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "scoring cycle",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=30)),
                "deadline_at": _iso(deadline),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()
    assert cycle["rule_set_version_id"]

    evaluator = f"scoreev_{secrets.token_hex(3)}"
    pw = "Submit-pass-99"
    uid = _seed(db_dsn, evaluator, pw, "Evaluator")
    (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": uid},
        )
    ).raise_for_status()

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e:
        login = await e.post("/api/auth/login", json={"username": evaluator, "password": pw})
        e.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        mine = (await e.get("/api/assignments/mine/active")).json()
        aid = mine[0]["id"]

        # Submit with q2 missing + q1 at threshold value
        await e.post(f"/api/assignments/{aid}/save", json={"values": {"q1": 15}})
        resp = await e.post(f"/api/assignments/{aid}/submit", json={"values": {"q1": 15}})
        assert resp.status_code == 200, resp.text
        assert resp.json()["state"] == "SUBMITTED"

    # Fetch submission + trace via admin
    subs = None
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM submissions WHERE assignment_id = %s LIMIT 1", (aid,)
        )
        subs = str(cur.fetchone()[0])

    trace_resp = await client.get(f"/api/submissions/{subs}/trace")
    assert trace_resp.status_code == 200
    body = trace_resp.json()
    assert set(body.keys()) == {
        "submission_id", "template_version_id", "rule_set_version_id",
        "trace", "trace_hash", "computed_at",
    }
    assert len(body["trace_hash"]) == 64

    trace = body["trace"]
    # Steps present for both items, sorted
    keys = [s["item_key"] for s in trace["steps"]]
    assert keys == ["q1", "q2"]

    q1_step = trace["steps"][0]
    q2_step = trace["steps"][1]

    # q1 raw preserved + threshold_exceeded flag
    assert q1_step["raw_present"] is True
    assert q1_step["raw_value"] == "15"
    assert "threshold_exceeded" in q1_step["flags"]

    # q2 missing + EXCLUDE_FROM_DENOMINATOR: effective_weight 0, missing flag
    assert q2_step["raw_present"] is False
    assert q2_step["missing_strategy"] == "EXCLUDE_FROM_DENOMINATOR"
    assert "missing" in q2_step["flags"]
    assert q2_step["effective_weight"] == "0"

    # Totals: only q1 contributes → score = 15
    assert trace["totals"]["score"] == "15"


@pytest.mark.asyncio
async def test_trace_hash_stable_across_reruns(admin_client, db_dsn, api_base_url):
    """Two separate submissions with identical template + rule set + inputs produce
    identical trace hashes."""
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"stbltpl_{secrets.token_hex(3)}",
                "items": [
                    {"key": "q1", "label": "Q1", "weight": 1.0, "required": True,
                     "missing_strategy": "ZERO_FILL"},
                ],
            },
        )
    ).json()
    deadline = datetime.now(timezone.utc) + timedelta(days=10)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "stable cycle",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=30)),
                "deadline_at": _iso(deadline),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()

    hashes: list[str] = []
    for i in range(2):
        evaluator = f"stbl_{secrets.token_hex(3)}"
        pw = "Submit-pass-99"
        uid = _seed(db_dsn, evaluator, pw, "Evaluator")
        (
            await client.post(
                f"/api/cycles/{cycle['id']}/assignments",
                json={"evaluator_user_id": uid},
            )
        ).raise_for_status()

        async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e:
            login = await e.post("/api/auth/login", json={"username": evaluator, "password": pw})
            e.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
            e.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            mine = (await e.get("/api/assignments/mine/active")).json()
            aid = mine[0]["id"]
            await e.post(f"/api/assignments/{aid}/save", json={"values": {"q1": 7}})
            await e.post(f"/api/assignments/{aid}/submit", json={"values": {"q1": 7}})

        with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM submissions WHERE assignment_id = %s LIMIT 1", (aid,)
            )
            sid = str(cur.fetchone()[0])
        tr = (await client.get(f"/api/submissions/{sid}/trace")).json()
        hashes.append(tr["trace_hash"])

    # Without outlier priors, both should be deterministic. With priors on run 2,
    # the first prior values come from run 1, potentially flagging run 2 as outlier
    # — but with n=1 prior, z-score is skipped. Hashes must match.
    assert hashes[0] == hashes[1]


@pytest.mark.asyncio
async def test_grade_edit_audits_content_hash_not_raw(admin_client, db_dsn, api_base_url):
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"edittpl_{secrets.token_hex(3)}",
                "items": [
                    {"key": "q1", "label": "Q1", "weight": 1.0, "required": True,
                     "missing_strategy": "ZERO_FILL"},
                ],
            },
        )
    ).json()
    deadline = datetime.now(timezone.utc) + timedelta(days=10)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "edit cycle",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=30)),
                "deadline_at": _iso(deadline),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()

    evaluator = f"ed_{secrets.token_hex(3)}"
    pw = "Submit-pass-99"
    uid = _seed(db_dsn, evaluator, pw, "Evaluator")
    (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": uid},
        )
    ).raise_for_status()

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e:
        login = await e.post("/api/auth/login", json={"username": evaluator, "password": pw})
        e.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        mine = (await e.get("/api/assignments/mine/active")).json()
        aid = mine[0]["id"]
        await e.post(f"/api/assignments/{aid}/save", json={"values": {"q1": 5}})
        await e.post(f"/api/assignments/{aid}/submit", json={"values": {"q1": 5}})

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM submissions WHERE assignment_id = %s LIMIT 1", (aid,))
        sid = str(cur.fetchone()[0])

    # Admin (has cycle:review wildcard) edits the grade
    resp = await client.post(
        f"/api/submissions/{sid}/grades/q1", json={"value": "7"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "content_hash" in body
    assert len(body["content_hash"]) == 64

    # Audit row should have the content hash, not the raw value
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs WHERE action = 'GRADE_EDIT' AND resource_id = %s",
            (sid,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        payload = rows[0][0]
        assert payload["content_hash"] == body["content_hash"]
        # Audit payload carries only the content_hash of the new value, never
        # the raw value or plaintext.
        assert "raw_value" not in payload
        assert "value" not in payload
        assert "plaintext" not in payload


@pytest.mark.asyncio
async def test_evaluator_cannot_edit_grade(admin_client, db_dsn, api_base_url, evaluator_client):
    e_client, _ = evaluator_client
    # Just hit the endpoint — we expect 403 with permission_denied before NotFound
    resp = await e_client.post(
        "/api/submissions/00000000-0000-0000-0000-000000000000/grades/q1",
        json={"value": 1},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "permission_denied"
