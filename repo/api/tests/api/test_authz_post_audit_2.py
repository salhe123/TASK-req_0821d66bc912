"""Second-round authorization regressions covering the delivery audit fixes:

* Cycle participant listing is restricted to participants unless caller has
  cycle:manage / cycle:review
* Share-link role is validated at resolution
* Share-link revocation is scoped to the issuer
* Model run listing requires model:run permission
* Error counter increments on exception envelope paths
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


def _feature(name: str) -> dict:
    return {"name": name, "dtype": "float", "transform": "identity", "source_query_hash": "q"}


# ---------------------------------------------------------------------------
# Cycle participant listing authz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cycle_assignment_listing_hides_other_participants(
    admin_client, db_dsn: str, api_base_url: str
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
    pw = "Evaluate-pass-99"
    owner = f"owner_{secrets.token_hex(3)}"
    other = f"other_{secrets.token_hex(3)}"
    outsider = f"outsider_{secrets.token_hex(3)}"
    owner_id = _make_user(db_dsn, owner, pw, "Evaluator")
    other_id = _make_user(db_dsn, other, pw, "Evaluator")
    _make_user(db_dsn, outsider, pw, "Evaluator")
    await client.post(
        f"/api/cycles/{cycle['id']}/assignments",
        json={"evaluator_user_id": owner_id},
    )
    await client.post(
        f"/api/cycles/{cycle['id']}/assignments",
        json={"evaluator_user_id": other_id},
    )

    # Owner sees only their own row, not `other`.
    async with await _login(api_base_url, owner, pw) as o:
        r = await o.get(f"/api/cycles/{cycle['id']}/assignments")
        assert r.status_code == 200
        ids = {a["evaluator_user_id"] for a in r.json()["items"]}
        assert ids == {owner_id}

    # Outsider with no assignment in the cycle gets an empty list.
    async with await _login(api_base_url, outsider, pw) as s:
        r = await s.get(f"/api/cycles/{cycle['id']}/assignments")
        assert r.status_code == 200
        assert r.json()["items"] == []

    # Admin still sees the full cycle.
    full = await client.get(f"/api/cycles/{cycle['id']}/assignments")
    assert full.status_code == 200
    assert len(full.json()["items"]) == 2


# ---------------------------------------------------------------------------
# Share-link role binding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_link_role_mismatch_is_rejected(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    client, _ = admin_client
    plan = (
        await client.post(
            "/api/plans",
            json={
                "name": f"plan_{secrets.token_hex(3)}",
                "lines": [
                    {"line_identity_key": "x", "part_number": "PN",
                     "quantity": "1", "unit": "ea"}
                ],
                "note": "init",
            },
        )
    ).json()
    # Share link bound to "Plan Owner" role.
    link = (
        await client.post(
            f"/api/plans/{plan['id']}/versions/{plan['head_version_id']}/share",
            json={"role": "Plan Owner", "expires_in_days": 7},
        )
    ).json()

    # Issue a second link bound to a role the Plan Owner does NOT hold.
    mismatched = (
        await client.post(
            f"/api/plans/{plan['id']}/versions/{plan['head_version_id']}/share",
            json={"role": "External Auditor", "expires_in_days": 7},
        )
    ).json()

    pw = "Plan-pass-99"
    owner_u = f"po_{secrets.token_hex(3)}"
    _make_user(db_dsn, owner_u, pw, "Plan Owner")

    async with await _login(api_base_url, owner_u, pw) as po_client:
        r = await po_client.get(f"/api/share/{mismatched['token']}")
        assert r.status_code == 403
        assert r.json()["error"] == "share_link_role_mismatch"
        # Matching "Plan Owner" link works.
        r2 = await po_client.get(f"/api/share/{link['token']}")
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Share-link revocation ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_link_revocation_is_scoped_to_issuer(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    client, _ = admin_client
    plan = (
        await client.post(
            "/api/plans",
            json={
                "name": f"plan_{secrets.token_hex(3)}",
                "lines": [
                    {"line_identity_key": "x", "part_number": "PN",
                     "quantity": "1", "unit": "ea"}
                ],
                "note": "init",
            },
        )
    ).json()
    link = (
        await client.post(
            f"/api/plans/{plan['id']}/versions/{plan['head_version_id']}/share",
            json={"role": "Plan Owner", "expires_in_days": 7},
        )
    ).json()
    # Admin is the creator — a non-admin Plan Owner cannot revoke the link.
    pw = "Plan-pass-99"
    other_owner = f"po_{secrets.token_hex(3)}"
    _make_user(db_dsn, other_owner, pw, "Plan Owner")
    async with await _login(api_base_url, other_owner, pw) as po_client:
        r = await po_client.delete(f"/api/plans/share-links/{link['id']}")
        assert r.status_code == 403
        assert r.json()["error"] == "share_link_not_yours"
    # Admin (wildcard) can revoke it.
    ok = await client.delete(f"/api/plans/share-links/{link['id']}")
    assert ok.status_code == 200
    assert ok.json()["revoked"] is True


# ---------------------------------------------------------------------------
# Model run listing requires model:run permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_listing_requires_model_run_permission(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    client, _ = admin_client
    model = (
        await client.post("/api/models", json={"name": f"m_{secrets.token_hex(3)}"})
    ).json()
    v1 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={"feature_schema": [_feature("a")], "artifact_params": {}},
        )
    ).json()
    pw = "Eval-pass-99"
    user = f"ev_{secrets.token_hex(3)}"
    _make_user(db_dsn, user, pw, "Evaluator")
    async with await _login(api_base_url, user, pw) as ec:
        r = await ec.get(f"/api/models/{model['id']}/versions/{v1['id']}/runs")
        assert r.status_code == 403
        assert r.json()["error"] == "permission_denied"


# ---------------------------------------------------------------------------
# Error counter wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_errors_total_increments_on_exception(admin_client) -> None:
    client, _ = admin_client
    before = (await client.get("/api/metrics")).json()["errorsTotal"]
    # Unknown UUID triggers NotFound (ApiError) — should bump errorsTotal.
    nf = await client.get("/api/submissions/00000000-0000-0000-0000-000000000000")
    assert nf.status_code == 404
    after = (await client.get("/api/metrics")).json()["errorsTotal"]
    assert after > before
