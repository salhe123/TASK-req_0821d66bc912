"""Third-round audit regression tests:

* Unassigned reviewer cannot read assignment detail/form.
* List endpoints (templates, cycles, models, experiments) are gated.
* Rule-set management endpoints round-trip with audit.
* User timezone preference updates are validated + persisted.
* Request counter increments on every request.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _make_user(db_dsn: str, username: str, password: str, role: str) -> str:
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
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


async def _login(base: str, username: str, password: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=base, timeout=10.0)
    resp = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    body = resp.json()
    client.headers["Authorization"] = f"Bearer {body['session_token']}"
    client.headers["X-CSRF-Token"] = body["csrf_token"]
    return client


# ---------------------------------------------------------------------------
# Unassigned reviewer — read paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unassigned_reviewer_cannot_read_assignment_detail(
    admin_client, db_dsn, api_base_url
) -> None:
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"tpl_{secrets.token_hex(3)}",
                "items": [
                    {"key": "a", "label": "A", "weight": 1.0, "required": True,
                     "missing_strategy": "ZERO_FILL"}
                ],
            },
        )
    ).json()
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": f"cycle_{secrets.token_hex(3)}",
                "starts_on": str(date.today()),
                "ends_on": str(date.today() + timedelta(days=30)),
                "deadline_at": _iso(datetime.now(timezone.utc) + timedelta(days=20)),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()
    pw = "Pass-phrase-99"
    evaluator = f"ev_{secrets.token_hex(3)}"
    assigned_rev = f"ar_{secrets.token_hex(3)}"
    other_rev = f"or_{secrets.token_hex(3)}"
    ev_id = _make_user(db_dsn, evaluator, pw, "Evaluator")
    ar_id = _make_user(db_dsn, assigned_rev, pw, "Reviewer")
    _make_user(db_dsn, other_rev, pw, "Reviewer")

    assignment = (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": ev_id, "reviewer_user_id": ar_id},
        )
    ).json()

    async with await _login(api_base_url, other_rev, pw) as client_or:
        r = await client_or.get(f"/api/assignments/{assignment['id']}")
        assert r.status_code == 403
        assert r.json()["error"] == "not_your_assignment"
        r = await client_or.get(f"/api/assignments/{assignment['id']}/form")
        assert r.status_code == 403
        assert r.json()["error"] == "not_your_assignment"

    # Assigned reviewer can read.
    async with await _login(api_base_url, assigned_rev, pw) as client_ar:
        r = await client_ar.get(f"/api/assignments/{assignment['id']}")
        assert r.status_code == 200
        r = await client_ar.get(f"/api/assignments/{assignment['id']}/form")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# List endpoint gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_templates_listing_requires_template_manage(
    admin_client, db_dsn, api_base_url
) -> None:
    pw = "Pass-phrase-99"
    ev = f"ev_{secrets.token_hex(3)}"
    _make_user(db_dsn, ev, pw, "Evaluator")
    async with await _login(api_base_url, ev, pw) as c:
        r = await c.get("/api/templates")
        assert r.status_code == 403
        assert r.json()["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_cycles_listing_empty_for_non_participant(
    admin_client, db_dsn, api_base_url
) -> None:
    pw = "Pass-phrase-99"
    po = f"po_{secrets.token_hex(3)}"
    # Plan Owner has no cycle:* permission.
    _make_user(db_dsn, po, pw, "Plan Owner")
    async with await _login(api_base_url, po, pw) as c:
        r = await c.get("/api/cycles")
        assert r.status_code == 200
        assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_models_listing_empty_for_unrelated_role(
    admin_client, db_dsn, api_base_url
) -> None:
    pw = "Pass-phrase-99"
    ev = f"ev_{secrets.token_hex(3)}"
    _make_user(db_dsn, ev, pw, "Evaluator")
    async with await _login(api_base_url, ev, pw) as c:
        r = await c.get("/api/models")
        assert r.status_code == 200
        assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_experiments_listing_empty_for_unrelated_role(
    admin_client, db_dsn, api_base_url
) -> None:
    pw = "Pass-phrase-99"
    rev = f"rev_{secrets.token_hex(3)}"
    # Reviewer has cycle:review but no experiment/feedback/model perms.
    _make_user(db_dsn, rev, pw, "Reviewer")
    async with await _login(api_base_url, rev, pw) as c:
        r = await c.get("/api/experiments")
        assert r.status_code == 200
        assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# Rule-set management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule_set_lifecycle_create_and_publish_version(admin_client) -> None:
    client, _ = admin_client
    name = f"rs_{secrets.token_hex(3)}"
    created = await client.post(
        "/api/rule_sets",
        json={"name": name, "description": "", "rules": {"outlier_z_default": "2.5"}},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["latest_version_no"] == 1
    published = await client.post(
        f"/api/rule_sets/{body['id']}/versions",
        json={"rules": {"outlier_z_default": "3.5"}},
    )
    assert published.status_code == 201
    assert published.json()["version_no"] == 2

    listing = (await client.get("/api/rule_sets")).json()
    entry = next(r for r in listing["items"] if r["name"] == name)
    assert entry["latest_version_no"] == 2


@pytest.mark.asyncio
async def test_rule_set_requires_permission(
    admin_client, db_dsn, api_base_url
) -> None:
    pw = "Pass-phrase-99"
    ev = f"ev_{secrets.token_hex(3)}"
    _make_user(db_dsn, ev, pw, "Evaluator")
    async with await _login(api_base_url, ev, pw) as c:
        r = await c.post(
            "/api/rule_sets",
            json={"name": f"x_{secrets.token_hex(3)}", "rules": {}},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# User timezone preference
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_timezone_round_trip(admin_client) -> None:
    client, _ = admin_client
    me = (await client.get("/api/auth/me")).json()
    assert me["timezone"] == "UTC"
    ok = await client.post("/api/auth/me/timezone", json={"timezone": "America/Los_Angeles"})
    assert ok.status_code == 200
    assert ok.json()["timezone"] == "America/Los_Angeles"
    me2 = (await client.get("/api/auth/me")).json()
    assert me2["timezone"] == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_user_timezone_invalid_rejected(admin_client) -> None:
    client, _ = admin_client
    r = await client.post("/api/auth/me/timezone", json={"timezone": "Not/A_Zone"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_timezone"


# ---------------------------------------------------------------------------
# Request counter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_requests_total_increments(admin_client) -> None:
    client, _ = admin_client
    before = (await client.get("/api/metrics")).json()["requestsTotal"]
    await client.get("/api/health")
    await client.get("/api/health")
    after = (await client.get("/api/metrics")).json()["requestsTotal"]
    # Three GETs since `before` were made. Counter must have advanced by at
    # least 2 (health endpoints are not gated).
    assert after >= before + 2
