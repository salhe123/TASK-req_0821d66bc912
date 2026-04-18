from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_full_lifecycle_with_return_then_resubmit_then_archive(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    client, admin_info = admin_client

    # 1) Create template
    tpl_resp = await client.post(
        "/api/templates",
        json={
            "name": f"tpl_{secrets.token_hex(3)}",
            "description": "Q2 template",
            "items": [
                {"key": "q1", "label": "Q1", "weight": 1.0, "required": True,
                 "missing_strategy": "ZERO_FILL"},
                {"key": "q2", "label": "Q2", "weight": 2.0, "required": True,
                 "missing_strategy": "ZERO_FILL"},
            ],
        },
    )
    assert tpl_resp.status_code == 201, tpl_resp.text
    tpl = tpl_resp.json()

    # 2) Create cycle (deadline well in the future)
    deadline = datetime.now(timezone.utc) + timedelta(days=60)
    cycle_resp = await client.post(
        "/api/cycles",
        json={
            "name": "Q2 2026 lifecycle",
            "starts_on": str(date.today()),
            "ends_on": str(date.today() + timedelta(days=90)),
            "deadline_at": _iso(deadline),
            "timezone": "UTC",
            "makeup_enabled": False,
            "makeup_business_days": 5,
            "holidays": [],
            "template_version_id": tpl["latest_version_id"],
        },
    )
    assert cycle_resp.status_code == 201, cycle_resp.text
    cycle = cycle_resp.json()
    assert cycle["effective_deadline_at"] == cycle["deadline_at"]

    # 3) Seed evaluator + reviewer
    eval_user = f"lifeeval_{secrets.token_hex(3)}"
    rev_user = f"liferev_{secrets.token_hex(3)}"
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    eval_pw = "Evaluate-pass-99"
    rev_pw = "Review-pass-99"
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        for uname, pw, role in [(eval_user, eval_pw, "Evaluator"), (rev_user, rev_pw, "Reviewer")]:
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_active) "
                "VALUES (%s, %s, %s, TRUE) RETURNING id",
                (uname, uname, hasher.hash(pw)),
            )
            uid = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT %s, id FROM roles WHERE name = %s",
                (uid, role),
            )
        cur.execute("SELECT id FROM users WHERE username = %s", (eval_user,))
        eval_id = str(cur.fetchone()[0])
        cur.execute("SELECT id FROM users WHERE username = %s", (rev_user,))
        rev_id = str(cur.fetchone()[0])

    # 4) Admin assigns evaluator + reviewer
    add_resp = await client.post(
        f"/api/cycles/{cycle['id']}/assignments",
        json={"evaluator_user_id": eval_id, "reviewer_user_id": rev_id},
    )
    assert add_resp.status_code == 201, add_resp.text
    assignment = add_resp.json()
    assert assignment["state"] == "NOT_STARTED"
    assert assignment["late_flag"] is False

    # 5) Evaluator logs in
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e_client:
        login = await e_client.post(
            "/api/auth/login", json={"username": eval_user, "password": eval_pw}
        )
        e_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        # Save draft → IN_PROGRESS
        save = await e_client.post(
            f"/api/assignments/{assignment['id']}/save",
            json={"values": {"q1": 8, "q2": 9}},
        )
        assert save.status_code == 200
        assert save.json()["state"] == "IN_PROGRESS"

        # Submit → SUBMITTED
        submit = await e_client.post(
            f"/api/assignments/{assignment['id']}/submit",
            json={"values": {"q1": 8, "q2": 9}},
        )
        assert submit.status_code == 200
        body = submit.json()
        assert body["state"] == "SUBMITTED"
        assert body["submitted_at"] is not None
        assert body["late_flag"] is False

    # 6) Reviewer returns
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as r_client:
        login = await r_client.post(
            "/api/auth/login", json={"username": rev_user, "password": rev_pw}
        )
        r_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        r_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        ret = await r_client.post(
            f"/api/assignments/{assignment['id']}/return",
            json={"reason": "please reconsider q2"},
        )
        assert ret.status_code == 200
        assert ret.json()["state"] == "RETURNED_FOR_REVISION"
        assert ret.json()["returned_reason"] == "please reconsider q2"

    # 7) Evaluator saves + resubmits
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e_client:
        login = await e_client.post(
            "/api/auth/login", json={"username": eval_user, "password": eval_pw}
        )
        e_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        save = await e_client.post(
            f"/api/assignments/{assignment['id']}/save",
            json={"values": {"q1": 8, "q2": 7}},
        )
        assert save.status_code == 200
        assert save.json()["state"] == "IN_PROGRESS"
        re_submit = await e_client.post(
            f"/api/assignments/{assignment['id']}/submit",
            json={"values": {"q1": 8, "q2": 7}},
        )
        assert re_submit.status_code == 200
        assert re_submit.json()["state"] == "SUBMITTED"

    # 8) Reviewer approves → ARCHIVED
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as r_client:
        login = await r_client.post(
            "/api/auth/login", json={"username": rev_user, "password": rev_pw}
        )
        r_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        r_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        ok = await r_client.post(f"/api/assignments/{assignment['id']}/approve")
        assert ok.status_code == 200
        body = ok.json()
        assert body["state"] == "ARCHIVED"
        assert body["archived_at"] is not None

        # ARCHIVED is terminal — cannot return or re-approve
        bad_ret = await r_client.post(
            f"/api/assignments/{assignment['id']}/return",
            json={"reason": "nope"},
        )
        assert bad_ret.status_code == 409
        assert bad_ret.json()["error"] == "invalid_transition"


@pytest.mark.asyncio
async def test_submit_after_deadline_without_makeup_rejected(
    admin_client, db_dsn: str, api_base_url: str
) -> None:
    client, _ = admin_client
    # Template
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
    # Deadline in the past, makeup disabled
    past = datetime.now(timezone.utc) - timedelta(days=1)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "past cycle",
                "starts_on": str(date.today() - timedelta(days=30)),
                "ends_on": str(date.today()),
                "deadline_at": _iso(past),
                "timezone": "UTC",
                "makeup_enabled": False,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()

    eval_user = f"pastev_{secrets.token_hex(3)}"
    pw = "Evaluate-pass-99"
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
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

    (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": uid},
        )
    ).raise_for_status()

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e_client:
        login = await e_client.post(
            "/api/auth/login", json={"username": eval_user, "password": pw}
        )
        e_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        # Get my assignments
        mine = (await e_client.get("/api/assignments/mine/active")).json()
        assignment_id = mine[0]["id"]
        await e_client.post(
            f"/api/assignments/{assignment_id}/save",
            json={"values": {"a": 1}},
        )
        resp = await e_client.post(
            f"/api/assignments/{assignment_id}/submit",
            json={"values": {"a": 1}},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"] == "deadline_passed_no_makeup"


@pytest.mark.asyncio
async def test_submit_after_deadline_with_makeup_marks_late(
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
    past = datetime.now(timezone.utc) - timedelta(days=1)
    cycle = (
        await client.post(
            "/api/cycles",
            json={
                "name": "makeup cycle",
                "starts_on": str(date.today() - timedelta(days=30)),
                "ends_on": str(date.today() + timedelta(days=10)),
                "deadline_at": _iso(past),
                "timezone": "UTC",
                "makeup_enabled": True,
                "makeup_business_days": 5,
                "holidays": [],
                "template_version_id": tpl["latest_version_id"],
            },
        )
    ).json()

    eval_user = f"mkev_{secrets.token_hex(3)}"
    pw = "Evaluate-pass-99"
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
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

    (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": uid},
        )
    ).raise_for_status()

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as e_client:
        login = await e_client.post(
            "/api/auth/login", json={"username": eval_user, "password": pw}
        )
        e_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        e_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        mine = (await e_client.get("/api/assignments/mine/active")).json()
        aid = mine[0]["id"]
        await e_client.post(f"/api/assignments/{aid}/save", json={"values": {"a": 1}})
        resp = await e_client.post(f"/api/assignments/{aid}/submit", json={"values": {"a": 1}})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "SUBMITTED"
        assert body["late_flag"] is True


@pytest.mark.asyncio
async def test_evaluator_cannot_submit_others_assignment(
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
                "name": "ownership cycle",
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

    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    owner = f"owner_{secrets.token_hex(3)}"
    stranger = f"stranger_{secrets.token_hex(3)}"
    pw = "Evaluate-pass-99"
    owner_id = None
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        for uname in (owner, stranger):
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_active) "
                "VALUES (%s, %s, %s, TRUE) RETURNING id",
                (uname, uname, hasher.hash(pw)),
            )
            uid = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT %s, id FROM roles WHERE name = 'Evaluator'",
                (uid,),
            )
            if uname == owner:
                owner_id = str(uid)

    (
        await client.post(
            f"/api/cycles/{cycle['id']}/assignments",
            json={"evaluator_user_id": owner_id},
        )
    ).raise_for_status()

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as s_client:
        login = await s_client.post(
            "/api/auth/login", json={"username": stranger, "password": pw}
        )
        s_client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        s_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        mine = (await s_client.get("/api/assignments/mine/active")).json()
        assert mine == []

        # try to hit the owner's assignment via listing
        owner_assignment = (
            await client.get(f"/api/cycles/{cycle['id']}/assignments")
        ).json()["items"][0]
        resp = await s_client.post(
            f"/api/assignments/{owner_assignment['id']}/save",
            json={"values": {"a": 1}},
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "not_your_assignment"
