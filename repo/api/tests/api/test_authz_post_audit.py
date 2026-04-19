"""Authorization regression tests covering the fixes called out in the
static audit:

* Submission detail/trace object-level authorization
* Reviewer actions bound to the assigned reviewer
* Plan path integrity — mismatched plan_id / version_id must 404
* Subject block lookup authorization
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
    # Log in with a throwaway client, then return a fresh (unopened) client
    # so `async with await _login(...) as c:` works — httpx refuses to reopen
    # a client that has already issued a request.
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as bootstrap:
        resp = await bootstrap.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
    body = resp.json()
    return httpx.AsyncClient(
        base_url=base,
        timeout=10.0,
        headers={
            "Authorization": f"Bearer {body['session_token']}",
            "X-CSRF-Token": body["csrf_token"],
        },
    )


async def _seed_cycle_with_two_evaluators(
    admin_client, db_dsn: str, api_base_url: str
) -> dict:
    client, _ = admin_client
    tpl = (
        await client.post(
            "/api/templates",
            json={
                "name": f"tpl_{secrets.token_hex(3)}",
                "items": [
                    {"key": "a", "label": "A", "weight": 1.0, "required": True,
                     "missing_strategy": "ZERO_FILL"},
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
    owner = f"owner_{secrets.token_hex(3)}"
    stranger = f"stranger_{secrets.token_hex(3)}"
    reviewer = f"rev_{secrets.token_hex(3)}"
    other_reviewer = f"rev2_{secrets.token_hex(3)}"
    pw = "Evaluate-pass-99"
    owner_id = _make_user(db_dsn, owner, pw, "Evaluator")
    stranger_id = _make_user(db_dsn, stranger, pw, "Evaluator")
    reviewer_id = _make_user(db_dsn, reviewer, pw, "Reviewer")
    other_rev_id = _make_user(db_dsn, other_reviewer, pw, "Reviewer")
    assignment = (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={
                "evaluator_user_id": owner_id,
                "reviewer_user_id": reviewer_id,
            },
        )
    ).json()

    # Owner submits so a submission + trace exist for the authz tests.
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as owner_client:
        login = await owner_client.post(
            "/api/auth/login", json={"username": owner, "password": pw}
        )
        owner_client.headers["Authorization"] = (
            f"Bearer {login.json()['session_token']}"
        )
        owner_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        await owner_client.post(
            f"/api/assignments/{assignment['id']}/save",
            json={"values": {"a": 5}},
        )
        await owner_client.post(
            f"/api/assignments/{assignment['id']}/submit",
            json={"values": {"a": 5}},
        )

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM submissions WHERE assignment_id = %s", (assignment["id"],)
        )
        submission_id = str(cur.fetchone()[0])

    return {
        "assignment_id": assignment["id"],
        "submission_id": submission_id,
        "owner": owner,
        "owner_pw": pw,
        "stranger": stranger,
        "stranger_pw": pw,
        "reviewer": reviewer,
        "reviewer_pw": pw,
        "other_reviewer": other_reviewer,
        "other_reviewer_pw": pw,
    }


@pytest.mark.asyncio
async def test_submission_detail_denied_for_non_owner_non_reviewer(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    ctx = await _seed_cycle_with_two_evaluators(admin_client, db_dsn, api_base_url)
    async with await _login(api_base_url, ctx["stranger"], ctx["stranger_pw"]) as s_client:
        resp = await s_client.get(f"/api/submissions/{ctx['submission_id']}")
        assert resp.status_code == 403
        assert resp.json()["error"] == "not_your_submission"
        trace = await s_client.get(f"/api/submissions/{ctx['submission_id']}/trace")
        assert trace.status_code == 403


@pytest.mark.asyncio
async def test_submission_detail_allowed_for_owner_and_reviewer(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    ctx = await _seed_cycle_with_two_evaluators(admin_client, db_dsn, api_base_url)
    async with await _login(api_base_url, ctx["owner"], ctx["owner_pw"]) as o_client:
        resp = await o_client.get(f"/api/submissions/{ctx['submission_id']}")
        assert resp.status_code == 200
    async with await _login(api_base_url, ctx["reviewer"], ctx["reviewer_pw"]) as r_client:
        resp = await r_client.get(f"/api/submissions/{ctx['submission_id']}")
        assert resp.status_code == 200
        trace = await r_client.get(f"/api/submissions/{ctx['submission_id']}/trace")
        assert trace.status_code == 200


@pytest.mark.asyncio
async def test_reviewer_action_denied_when_not_assigned(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    ctx = await _seed_cycle_with_two_evaluators(admin_client, db_dsn, api_base_url)
    async with await _login(
        api_base_url, ctx["other_reviewer"], ctx["other_reviewer_pw"]
    ) as r_client:
        ret = await r_client.post(
            f"/api/assignments/{ctx['assignment_id']}/return",
            json={"reason": "intruder review"},
        )
        assert ret.status_code == 403
        assert ret.json()["error"] == "not_assigned_reviewer"
        approve = await r_client.post(
            f"/api/assignments/{ctx['assignment_id']}/approve"
        )
        assert approve.status_code == 403
        assert approve.json()["error"] == "not_assigned_reviewer"


@pytest.mark.asyncio
async def test_plan_version_detail_rejects_mismatched_plan_id(admin_client) -> None:
    client, _ = admin_client
    plan_a = (
        await client.post(
            "/api/plans",
            json={
                "name": f"plan_a_{secrets.token_hex(3)}",
                "description": "",
                "lines": [
                    {
                        "line_identity_key": "x",
                        "part_number": "PN-1",
                        "description": "line",
                        "quantity": "1",
                        "unit": "ea",
                        "notes": "",
                        "tags": [],
                    }
                ],
                "note": "init",
            },
        )
    ).json()
    plan_b = (
        await client.post(
            "/api/plans",
            json={
                "name": f"plan_b_{secrets.token_hex(3)}",
                "description": "",
                "lines": [
                    {
                        "line_identity_key": "x",
                        "part_number": "PN-2",
                        "description": "line",
                        "quantity": "1",
                        "unit": "ea",
                        "notes": "",
                        "tags": [],
                    }
                ],
                "note": "init",
            },
        )
    ).json()
    a_version_id = plan_a["head_version_id"]
    resp = await client.get(f"/api/plans/{plan_b['id']}/versions/{a_version_id}")
    assert resp.status_code == 404
    diff = await client.get(
        f"/api/plans/{plan_b['id']}/versions/{a_version_id}/diff"
    )
    assert diff.status_code == 404
    exp = await client.get(
        f"/api/plans/{plan_b['id']}/versions/{a_version_id}/export"
    )
    assert exp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_blocks_read_denied_for_other_subject(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    _make_user(db_dsn, f"fb_{secrets.token_hex(3)}", "Seed-pass-99", "Evaluator")
    user_a = f"fba_{secrets.token_hex(3)}"
    uid_a = _make_user(db_dsn, user_a, "Seed-pass-99", "Evaluator")
    user_b = f"fbb_{secrets.token_hex(3)}"
    _make_user(db_dsn, user_b, "Seed-pass-99", "Evaluator")

    async with await _login(api_base_url, user_b, "Seed-pass-99") as b_client:
        # Reading another subject's blocks is denied; only own-subject reads
        # (and privileged manage permission) succeed.
        resp = await b_client.get(f"/api/feedback/blocks/{uid_a}")
        assert resp.status_code == 403
        assert resp.json()["error"] == "subject_scope_denied"
