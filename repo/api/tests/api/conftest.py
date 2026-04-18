from __future__ import annotations

import os
import secrets
import time

import httpx
import psycopg
import pytest
import pytest_asyncio

from argon2 import PasswordHasher


def _reset_identity_tables(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE sessions, failed_logins, user_roles, users "
                "RESTART IDENTITY CASCADE"
            )


def _create_admin(dsn: str, username: str, password: str) -> str:
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    pwd_hash = hasher.hash(password)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_active) "
                "VALUES (%s, %s, %s, TRUE) RETURNING id",
                (username, username, pwd_hash),
            )
            row = cur.fetchone()
            assert row is not None
            uid = str(row[0])
            cur.execute(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT %s, id FROM roles WHERE name = 'Administrator'",
                (uid,),
            )
    return uid


def _create_evaluator(dsn: str, username: str, password: str) -> str:
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    pwd_hash = hasher.hash(password)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, is_active) "
                "VALUES (%s, %s, %s, TRUE) RETURNING id",
                (username, username, pwd_hash),
            )
            row = cur.fetchone()
            assert row is not None
            uid = str(row[0])
            cur.execute(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT %s, id FROM roles WHERE name = 'Evaluator'",
                (uid,),
            )
    return uid


@pytest_asyncio.fixture(scope="function")
async def admin_client(api_base_url: str, db_dsn: str):
    _reset_identity_tables(db_dsn)
    username = f"admin_{secrets.token_hex(4)}"
    password = "Abcd1234Efgh!"
    uid = _create_admin(db_dsn, username, password)

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        client.headers["Authorization"] = f"Bearer {body['session_token']}"
        client.headers["X-CSRF-Token"] = body["csrf_token"]
        try:
            yield client, {"user_id": uid, "username": username, "password": password, **body}
        finally:
            # Safety net: if a test leaves a staged restore behind, abort it so
            # the next test is not stuck in maintenance mode.
            try:
                with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
                    cur.execute(
                        "SELECT archive_id FROM restore_events WHERE state = 'staged'"
                    )
                    staged = [str(r[0]) for r in cur.fetchall()]
                for aid in staged:
                    await client.post(f"/api/admin/backups/{aid}/abort")
            except Exception:
                pass


@pytest_asyncio.fixture(scope="function")
async def evaluator_client(api_base_url: str, db_dsn: str):
    username = f"eval_{secrets.token_hex(4)}"
    password = "Evaluate-pass-99"
    uid = _create_evaluator(db_dsn, username, password)

    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        client.headers["Authorization"] = f"Bearer {body['session_token']}"
        client.headers["X-CSRF-Token"] = body["csrf_token"]
        yield client, {"user_id": uid, "username": username, "password": password, **body}
