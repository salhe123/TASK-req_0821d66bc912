"""Model training / evaluation run workflow (phase 8).

Covers the lifecycle endpoints added to close the audit gap:
  * start → complete run transitions
  * promotion gate requires a SUCCEEDED EVALUATION run on the target version
"""
from __future__ import annotations

import secrets

import pytest


def _feature(name: str) -> dict:
    return {"name": name, "dtype": "float", "transform": "identity", "source_query_hash": "q"}


async def _register_version(client) -> tuple[dict, dict]:
    model = (
        await client.post(
            "/api/models",
            json={"name": f"run_m_{secrets.token_hex(3)}", "description": "runs"},
        )
    ).json()
    version = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a")],
                "artifact_params": {"bias": 0.0, "weights": {"a": 1.0}},
            },
        )
    ).json()
    return model, version


@pytest.mark.asyncio
async def test_promote_rejected_without_successful_evaluation_run(admin_client) -> None:
    client, _ = admin_client
    model, version = await _register_version(client)
    resp = await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/promote"
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "evaluation_run_required"


@pytest.mark.asyncio
async def test_run_lifecycle_start_then_complete(admin_client) -> None:
    client, _ = admin_client
    model, version = await _register_version(client)
    start = await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/runs",
        json={"kind": "EVALUATION", "dataset_ref": "holdout"},
    )
    assert start.status_code == 201
    run = start.json()
    assert run["status"] == "RUNNING"
    assert run["kind"] == "EVALUATION"

    complete = await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/runs/{run['id']}/complete",
        json={"status": "SUCCEEDED", "metrics": {"auc": 0.9}},
    )
    assert complete.status_code == 200
    done = complete.json()
    assert done["status"] == "SUCCEEDED"
    assert done["metrics"]["auc"] == 0.9
    assert done["completed_at"] is not None

    listing = await client.get(
        f"/api/models/{model['id']}/versions/{version['id']}/runs"
    )
    assert listing.status_code == 200
    rows = listing.json()["items"]
    assert len(rows) == 1
    assert rows[0]["id"] == run["id"]


@pytest.mark.asyncio
async def test_run_already_completed_conflict(admin_client) -> None:
    client, _ = admin_client
    model, version = await _register_version(client)
    run = (
        await client.post(
            f"/api/models/{model['id']}/versions/{version['id']}/runs",
            json={"kind": "TRAINING"},
        )
    ).json()
    ok = await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/runs/{run['id']}/complete",
        json={"status": "SUCCEEDED", "metrics": {}},
    )
    assert ok.status_code == 200
    again = await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/runs/{run['id']}/complete",
        json={"status": "FAILED", "metrics": {}},
    )
    assert again.status_code == 409
    assert again.json()["error"] == "run_already_completed"


@pytest.mark.asyncio
async def test_failed_evaluation_does_not_unlock_promotion(admin_client) -> None:
    client, _ = admin_client
    model, version = await _register_version(client)
    run = (
        await client.post(
            f"/api/models/{model['id']}/versions/{version['id']}/runs",
            json={"kind": "EVALUATION"},
        )
    ).json()
    await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/runs/{run['id']}/complete",
        json={"status": "FAILED", "metrics": {"auc": 0.1}},
    )
    resp = await client.post(
        f"/api/models/{model['id']}/versions/{version['id']}/promote"
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "evaluation_run_required"
