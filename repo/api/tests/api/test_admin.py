from __future__ import annotations

import secrets

import httpx
import psycopg
import pytest


@pytest.mark.asyncio
async def test_list_roles_and_permissions(admin_client) -> None:
    client, _ = admin_client

    roles = (await client.get("/api/admin/roles")).json()
    role_names = [r["name"] for r in roles["items"]]
    for name in ("Administrator", "ML Engineer", "Evaluator", "Reviewer", "Plan Owner"):
        assert name in role_names

    perms = (await client.get("/api/admin/permissions")).json()
    keys = {(p["resource"], p["action"]) for p in perms["items"]}
    assert ("user", "manage") in keys
    assert ("backup", "manage") in keys
    assert ("model", "promote") in keys


@pytest.mark.asyncio
async def test_audit_log_filters_by_action_and_resource(admin_client, db_dsn) -> None:
    client, info = admin_client

    # Generate some audit entries by creating a template + cycle
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"audit_tpl_{secrets.token_hex(3)}",
                "items": [
                    {"key": "q1", "label": "Q1", "weight": 1, "required": True,
                     "missing_strategy": "ZERO_FILL"}
                ],
            },
        )
    ).json()

    filtered = await client.get("/api/admin/audit/logs?action=TEMPLATE_CREATE")
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert any(row["action"] == "TEMPLATE_CREATE" for row in items)
    assert all(row["action"] == "TEMPLATE_CREATE" for row in items)

    by_resource = await client.get(f"/api/admin/audit/logs?resource_type=template")
    assert all(row["resource_type"] == "template" for row in by_resource.json()["items"])


@pytest.mark.asyncio
async def test_backup_create_stage_commit_flow(admin_client, db_dsn, api_base_url) -> None:
    client, info = admin_client

    created = (await client.post("/api/admin/backups")).json()
    assert "manifest_hash" in created
    assert len(created["manifest_hash"]) == 64
    assert len(created["kek_fingerprint"]) == 64
    aid = created["id"]

    # Stage → enters maintenance mode
    stage = await client.post(f"/api/admin/backups/{aid}/stage")
    assert stage.status_code == 200
    assert stage.json()["maintenance"]["active"] is True

    # Non-admin traffic should now receive 503 with error=maintenance
    # We bootstrap an evaluator
    from argon2 import PasswordHasher
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    eval_user = f"ev_{secrets.token_hex(3)}"
    pw = "Maint-test-pwd-1"
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, display_name, password_hash, is_active) "
            "VALUES (%s, %s, %s, TRUE) RETURNING id",
            (eval_user, eval_user, hasher.hash(pw)),
        )
        uid = str(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO user_roles (user_id, role_id) "
            "SELECT %s, id FROM roles WHERE name = 'Evaluator'",
            (uid,),
        )

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as ev:
        login = await ev.post(
            "/api/auth/login", json={"username": eval_user, "password": pw}
        )
        # login itself must still work (exempted)
        assert login.status_code == 200
        ev.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        ev.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        # Non-admin routes blocked with 503 maintenance
        r = await ev.get("/api/plans")
        assert r.status_code == 503
        body = r.json()
        assert body["error"] == "maintenance"

    # Admin commits → single BACKUP_RESTORE audit entry containing archive + admin id
    commit = await client.post(f"/api/admin/backups/{aid}/commit")
    assert commit.status_code == 200
    assert commit.json()["state"] == "committed"

    # Verify single audit entry with expected payload
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload, actor_user_id FROM audit_logs "
            "WHERE action = 'BACKUP_RESTORE' AND resource_id = %s",
            (aid,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        payload, actor = rows[0]
        assert payload["final_state"] == "committed"
        assert payload["administrator_id"] == info["user_id"]
        assert len(payload["kek_fingerprint"]) == 64
        assert str(actor) == info["user_id"]

    # Maintenance flag cleared → subsequent admin requests work
    r2 = await client.get("/api/admin/backups")
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_abort_leaves_state_untouched(admin_client, db_dsn) -> None:
    client, info = admin_client

    created = (await client.post("/api/admin/backups")).json()
    aid = created["id"]

    await client.post(f"/api/admin/backups/{aid}/stage")
    abort = await client.post(f"/api/admin/backups/{aid}/abort")
    assert abort.status_code == 200
    assert abort.json()["state"] == "aborted"

    # Audit row records aborted outcome; data tables untouched (the table counts
    # shouldn't change — spot-check audit_logs present and the restore event state).
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs "
            "WHERE action = 'BACKUP_RESTORE' AND resource_id = %s",
            (aid,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0]["final_state"] == "aborted"

        cur.execute(
            "SELECT state FROM restore_events WHERE archive_id = %s",
            (aid,),
        )
        states = [r[0] for r in cur.fetchall()]
        assert "aborted" in states


@pytest.mark.asyncio
async def test_stage_conflicts_when_another_is_staged(admin_client) -> None:
    client, _ = admin_client
    a1 = (await client.post("/api/admin/backups")).json()
    a2 = (await client.post("/api/admin/backups")).json()

    await client.post(f"/api/admin/backups/{a1['id']}/stage")
    conflict = await client.post(f"/api/admin/backups/{a2['id']}/stage")
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "restore_already_staged"

    # Clean up: abort the staged one
    await client.post(f"/api/admin/backups/{a1['id']}/abort")


@pytest.mark.asyncio
async def test_non_admin_forbidden_on_backup_endpoints(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.get("/api/admin/backups")
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"
