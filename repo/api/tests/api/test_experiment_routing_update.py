"""Routing update path — weight changes persist, audit row recorded,
validation rejects out-of-range weights, permission enforced."""
from __future__ import annotations

import secrets

import psycopg
import pytest

from tests.api.helpers import promote_with_eval_run


def _feature(name: str) -> dict:
    return {"name": name, "dtype": "float", "transform": "identity", "source_query_hash": "q"}


async def _make_experiment(client) -> dict:
    model = (
        await client.post("/api/models", json={"name": f"m_{secrets.token_hex(3)}"})
    ).json()
    v1 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={"feature_schema": [_feature("a")], "artifact_params": {}},
        )
    ).json()
    await promote_with_eval_run(client, model["id"], v1["id"])
    return (
        await client.post(
            "/api/experiments",
            json={
                "name": f"rexp_{secrets.token_hex(3)}",
                "model_a_version_id": v1["id"],
                "weight_a": 90,
            },
        )
    ).json()


@pytest.mark.asyncio
async def test_routing_update_changes_weights_and_audits(admin_client, db_dsn) -> None:
    client, _ = admin_client
    exp = await _make_experiment(client)

    r = await client.post(
        f"/api/experiments/{exp['id']}/routing", json={"weight_a": 70}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["weight_a"] == 70
    assert body["weight_b"] == 30

    # Audit row captures before/after
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs WHERE action = 'ROUTING_CHANGE' "
            "AND resource_id = %s ORDER BY created_at DESC LIMIT 1",
            (exp["id"],),
        )
        payload = cur.fetchone()[0]
        assert payload["from"] == {"weight_a": 90, "weight_b": 10}
        assert payload["to"] == {"weight_a": 70, "weight_b": 30}


@pytest.mark.asyncio
async def test_routing_update_rejects_out_of_range_weight(admin_client) -> None:
    client, _ = admin_client
    exp = await _make_experiment(client)
    r = await client.post(
        f"/api/experiments/{exp['id']}/routing", json={"weight_a": 150}
    )
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


@pytest.mark.asyncio
async def test_routing_update_rejects_negative_weight(admin_client) -> None:
    client, _ = admin_client
    exp = await _make_experiment(client)
    r = await client.post(
        f"/api/experiments/{exp['id']}/routing", json={"weight_a": -5}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_routing_update_unknown_experiment_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.post(
        "/api/experiments/00000000-0000-0000-0000-000000000000/routing",
        json={"weight_a": 50},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_non_ml_engineer_cannot_change_routing(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.post(
        "/api/experiments/00000000-0000-0000-0000-000000000000/routing",
        json={"weight_a": 50},
    )
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"
