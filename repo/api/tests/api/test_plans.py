from __future__ import annotations

import secrets
import zipfile
from io import BytesIO

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


def _seed_plan_owner(dsn: str, username: str, password: str) -> str:
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
            "SELECT %s, id FROM roles WHERE name = 'Plan Owner'",
            (uid,),
        )
    return uid


@pytest.mark.asyncio
async def test_plan_lifecycle_create_version_compare(admin_client) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    # v1
    v1_resp = await client.post(
        "/api/plans",
        json={
            "name": name,
            "description": "first cut",
            "note": "init",
            "lines": [
                {"line_identity_key": "K1", "part_number": "P-A", "quantity": 10, "unit": "ea"},
                {"line_identity_key": "K2", "part_number": "P-B", "quantity": 2, "unit": "ea"},
            ],
        },
    )
    assert v1_resp.status_code == 201, v1_resp.text
    plan = v1_resp.json()
    plan_id = plan["id"]
    v1_id = plan["head_version_id"]

    # v2: rename K2 and change qty on K1
    v2_resp = await client.post(
        f"/api/plans/{plan_id}/versions",
        json={
            "parent_version_id": v1_id,
            "note": "rename",
            "lines": [
                {"line_identity_key": "K1", "part_number": "P-A", "quantity": 11, "unit": "ea"},
                {"line_identity_key": "K2", "part_number": "P-B-RENAMED", "quantity": 2, "unit": "ea"},
            ],
        },
    )
    assert v2_resp.status_code == 201, v2_resp.text
    v2 = v2_resp.json()

    diff_resp = await client.get(
        f"/api/plans/{plan_id}/versions/{v2['id']}/diff"
    )
    assert diff_resp.status_code == 200
    body = diff_resp.json()
    assert body["base_version_id"] == v1_id
    assert body["target_version_id"] == v2["id"]
    by_key = {e["line_identity_key"]: e for e in body["entries"]}
    assert "QUANTITY_CHANGED" in by_key["K1"]["changes"]
    assert "PART_CHANGED" in by_key["K2"]["changes"]
    assert by_key["K2"]["target"]["part_number"] == "P-B-RENAMED"


@pytest.mark.asyncio
async def test_export_bundle_signature_verifies(admin_client) -> None:
    from app.services.plan_export import verify_bundle

    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    v1 = (
        await client.post(
            "/api/plans",
            json={
                "name": name,
                "lines": [
                    {"line_identity_key": "K1", "part_number": "P-A", "quantity": 1},
                ],
            },
        )
    ).json()
    r = await client.get(f"/api/plans/{v1['id']}/versions/{v1['head_version_id']}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip")

    bundle = r.content
    assert verify_bundle(bundle) is True

    # Sanity: manifest file exists
    with zipfile.ZipFile(BytesIO(bundle)) as zf:
        names = zf.namelist()
        assert "plan.json" in names
        assert "diff.json" in names
        assert "manifest.json" in names
        assert "signature" in names


@pytest.mark.asyncio
async def test_rollback_creates_version_and_audits(admin_client, db_dsn) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    v1_plan = (
        await client.post(
            "/api/plans",
            json={
                "name": name,
                "lines": [{"line_identity_key": "K1", "part_number": "P-A", "quantity": 10}],
            },
        )
    ).json()
    v1_id = v1_plan["head_version_id"]
    plan_id = v1_plan["id"]

    # v2
    v2 = (
        await client.post(
            f"/api/plans/{plan_id}/versions",
            json={
                "parent_version_id": v1_id,
                "lines": [{"line_identity_key": "K1", "part_number": "P-A", "quantity": 99}],
            },
        )
    ).json()

    # Roll back to v1 → should create v3 with v1's lines
    rb = await client.post(
        f"/api/plans/{plan_id}/versions/{v1_id}/rollback",
        json={"note": "revert"},
    )
    assert rb.status_code == 201, rb.text
    new_version = rb.json()
    assert new_version["version_no"] == 3
    assert new_version["parent_version_id"] == v2["id"]

    detail = (
        await client.get(
            f"/api/plans/{plan_id}/versions/{new_version['id']}"
        )
    ).json()
    line = detail["lines"][0]
    assert line["quantity"] == "10"

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs WHERE action='PLAN_ROLLBACK' AND resource_id=%s",
            (plan_id,),
        )
        row = cur.fetchone()
        assert row is not None
        payload = row[0]
        assert payload["new_version_no"] == 3
        assert payload["restored_from_version_no"] == 1


@pytest.mark.asyncio
async def test_share_link_issue_revoke_and_resolution(
    admin_client, db_dsn, api_base_url
) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    p = (
        await client.post(
            "/api/plans",
            json={
                "name": name,
                "lines": [{"line_identity_key": "K1", "part_number": "P-A", "quantity": 1}],
            },
        )
    ).json()
    plan_id = p["id"]
    vid = p["head_version_id"]

    # Issue
    issue = await client.post(
        f"/api/plans/{plan_id}/versions/{vid}/share",
        json={"role": "Plan Owner", "expires_in_days": 1},
    )
    assert issue.status_code == 201
    body = issue.json()
    token = body["token"]
    link_id = body["id"]
    assert len(token) > 20

    # Seed a Plan Owner user (has view_shared permission)
    owner_user = f"po_{secrets.token_hex(3)}"
    owner_pw = "Shared-Password-9!"
    _seed_plan_owner(db_dsn, owner_user, owner_pw)

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as p_client:
        login = await p_client.post(
            "/api/auth/login", json={"username": owner_user, "password": owner_pw}
        )
        p_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        p_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        # Resolve with plan owner session → 200
        r = await p_client.get(f"/api/share/{token}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "Plan Owner"
        assert body["version"]["id"] == vid

    # Admin revokes → further resolution returns 403
    rev = await client.delete(f"/api/plans/share-links/{link_id}")
    assert rev.status_code == 200
    assert rev.json()["revoked"] is True

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as p_client:
        login = await p_client.post(
            "/api/auth/login", json={"username": owner_user, "password": owner_pw}
        )
        p_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        p_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        r = await p_client.get(f"/api/share/{token}")
        assert r.status_code == 403
        assert r.json()["error"] == "share_link_invalid"


@pytest.mark.asyncio
async def test_share_requires_view_shared_permission(
    admin_client, db_dsn, api_base_url, evaluator_client
) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    p = (
        await client.post(
            "/api/plans",
            json={
                "name": name,
                "lines": [{"line_identity_key": "K1", "part_number": "P-A", "quantity": 1}],
            },
        )
    ).json()
    issue = await client.post(
        f"/api/plans/{p['id']}/versions/{p['head_version_id']}/share",
        json={"role": "Plan Owner", "expires_in_days": 1},
    )
    token = issue.json()["token"]

    # Evaluator (no build_plan:view_shared) → 403
    e_client, _ = evaluator_client
    r = await e_client.get(f"/api/share/{token}")
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_copy_version_creates_sibling_with_same_lines(
    admin_client, db_dsn
) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    v1_plan = (
        await client.post(
            "/api/plans",
            json={
                "name": name,
                "lines": [
                    {"line_identity_key": "K1", "part_number": "P-A", "quantity": 3},
                    {"line_identity_key": "K2", "part_number": "P-B", "quantity": 7},
                ],
            },
        )
    ).json()
    plan_id = v1_plan["id"]
    v1_id = v1_plan["head_version_id"]

    # v2 diverges from v1
    v2 = (
        await client.post(
            f"/api/plans/{plan_id}/versions",
            json={
                "parent_version_id": v1_id,
                "lines": [
                    {"line_identity_key": "K1", "part_number": "P-A", "quantity": 3},
                    {"line_identity_key": "K2", "part_number": "P-B", "quantity": 99},
                ],
            },
        )
    ).json()

    # Copy v1 explicitly — new version's parent must be v1, not head (v2),
    # and lines must match v1 verbatim.
    copy = await client.post(
        f"/api/plans/{plan_id}/versions/{v1_id}/copy",
        json={"note": "fork for experiment"},
    )
    assert copy.status_code == 201, copy.text
    new_version = copy.json()
    assert new_version["version_no"] == 3
    assert new_version["parent_version_id"] == v1_id
    assert new_version["note"] == "fork for experiment"

    detail = (
        await client.get(f"/api/plans/{plan_id}/versions/{new_version['id']}")
    ).json()
    by_key = {l["line_identity_key"]: l for l in detail["lines"]}
    assert by_key["K1"]["quantity"] == "3"
    assert by_key["K2"]["quantity"] == "7"

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs "
            "WHERE action='PLAN_VERSION_COPY' AND resource_id=%s",
            (plan_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0]["source_version_no"] == 1
        assert row[0]["new_version_no"] == 3

    # Default note when body omits one.
    copy_default = await client.post(
        f"/api/plans/{plan_id}/versions/{v2['id']}/copy",
        json={},
    )
    assert copy_default.status_code == 201
    assert copy_default.json()["note"] == f"copy of v{v2['version_no']}"


@pytest.mark.asyncio
async def test_copy_version_requires_manage_permission(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.post(
        f"/api/plans/{secrets.token_hex(16)}/versions/{secrets.token_hex(16)}/copy",
        json={"note": "noop"},
    )
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_duplicate_plan_name_conflict(admin_client) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    body = {
        "name": name,
        "lines": [{"line_identity_key": "K1", "part_number": "P-A", "quantity": 1}],
    }
    r1 = await client.post("/api/plans", json=body)
    assert r1.status_code == 201
    r2 = await client.post("/api/plans", json=body)
    assert r2.status_code == 409
    assert r2.json()["error"] == "plan_name_taken"


@pytest.mark.asyncio
async def test_duplicate_line_identity_key_rejected(admin_client) -> None:
    client, _ = admin_client
    name = f"plan_{secrets.token_hex(3)}"
    r = await client.post(
        "/api/plans",
        json={
            "name": name,
            "lines": [
                {"line_identity_key": "K1", "part_number": "A", "quantity": 1},
                {"line_identity_key": "K1", "part_number": "B", "quantity": 1},
            ],
        },
    )
    assert r.status_code == 409
    assert r.json()["error"] == "duplicate_line_identity"
