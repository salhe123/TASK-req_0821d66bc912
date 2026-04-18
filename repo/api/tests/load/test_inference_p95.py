"""Load gate: approved-route inference p95 must be ≤ 150 ms on production
hardware. The budget is overridable via `P95_BUDGET_MS` env so dev runs on
macOS-under-Colima (which adds VM + syscall overhead) don't fail this tier
spuriously. CI against production-grade runners should keep the default.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import statistics
import time

import httpx
import psycopg
import pytest
from argon2 import PasswordHasher


P95_BUDGET_MS = float(os.environ.get("P95_BUDGET_MS", "150"))
CONCURRENCY = int(os.environ.get("LOAD_CONCURRENCY", "16"))
TOTAL_REQUESTS = int(os.environ.get("LOAD_TOTAL_REQUESTS", "400"))


def _feature(name: str) -> dict:
    return {"name": name, "dtype": "float", "transform": "identity", "source_query_hash": "q"}


async def _setup_experiment(client: httpx.AsyncClient) -> dict:
    model = (
        await client.post(
            "/api/models", json={"name": f"loadm_{secrets.token_hex(3)}"}
        )
    ).json()
    v1 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a"), _feature("b")],
                "artifact_params": {"bias": 0.1, "weights": {"a": 0.3, "b": -0.2}},
            },
        )
    ).json()
    run = (
        await client.post(
            f"/api/models/{model['id']}/versions/{v1['id']}/runs",
            json={"kind": "EVALUATION", "dataset_ref": "load-holdout"},
        )
    ).json()
    await client.post(
        f"/api/models/{model['id']}/versions/{v1['id']}/runs/{run['id']}/complete",
        json={"status": "SUCCEEDED", "metrics": {"auc": 0.9}},
    )
    await client.post(f"/api/models/{model['id']}/versions/{v1['id']}/promote")
    exp = (
        await client.post(
            "/api/experiments",
            json={
                "name": f"loade_{secrets.token_hex(3)}",
                "model_a_version_id": v1["id"],
                "weight_a": 100,
            },
        )
    ).json()
    return exp


def _seed_admin(db_dsn: str) -> tuple[str, str]:
    hasher = PasswordHasher(time_cost=2, memory_cost=32 * 1024, parallelism=1)
    username = f"loadadmin_{secrets.token_hex(4)}"
    password = "Load-pass-pwd-9!"
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, display_name, password_hash, is_active) "
            "VALUES (%s, %s, %s, TRUE) RETURNING id",
            (username, username, hasher.hash(password)),
        )
        uid = str(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO user_roles (user_id, role_id) "
            "SELECT %s, id FROM roles WHERE name = 'Administrator'",
            (uid,),
        )
    return username, password


@pytest.mark.asyncio
async def test_predict_p95_under_budget(api_base_url: str, db_dsn: str) -> None:
    username, password = _seed_admin(db_dsn)
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        login = await client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

        exp = await _setup_experiment(client)

        # Warm up so the artifact cache + connection pool are hot.
        for i in range(20):
            await client.post(
                "/api/inference/predict",
                json={
                    "experiment_id": exp["id"],
                    "subject_key": f"warm-{i}",
                    "features": {"a": 0.1, "b": 0.2},
                },
            )

        sem = asyncio.Semaphore(CONCURRENCY)
        latencies_ms: list[float] = []
        errors = 0

        async def one(i: int) -> None:
            nonlocal errors
            async with sem:
                t0 = time.perf_counter()
                r = await client.post(
                    "/api/inference/predict",
                    json={
                        "experiment_id": exp["id"],
                        "subject_key": f"subject-{i}",
                        "features": {"a": 0.3, "b": 0.5},
                    },
                )
                elapsed = (time.perf_counter() - t0) * 1000
                latencies_ms.append(elapsed)
                if r.status_code != 200:
                    errors += 1

        await asyncio.gather(*(one(i) for i in range(TOTAL_REQUESTS)))

    assert errors == 0, f"{errors}/{TOTAL_REQUESTS} predict calls failed"

    latencies_ms.sort()
    p95 = latencies_ms[int(0.95 * (len(latencies_ms) - 1))]
    p50 = statistics.median(latencies_ms)
    p99 = latencies_ms[int(0.99 * (len(latencies_ms) - 1))]

    # Emit a machine-friendly summary so CI can pick it up
    print(
        f"[load] n={len(latencies_ms)} p50={p50:.1f}ms p95={p95:.1f}ms "
        f"p99={p99:.1f}ms errors={errors}"
    )

    assert p95 <= P95_BUDGET_MS, (
        f"p95 {p95:.1f}ms exceeds {P95_BUDGET_MS}ms budget "
        f"(p50={p50:.1f}, p99={p99:.1f})"
    )
