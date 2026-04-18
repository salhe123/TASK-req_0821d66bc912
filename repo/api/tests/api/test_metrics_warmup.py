from __future__ import annotations

import secrets

import pytest

from tests.api.helpers import promote_with_eval_run


def _feature(name: str) -> dict:
    return {"name": name, "dtype": "float", "transform": "identity", "source_query_hash": "q"}


@pytest.mark.asyncio
async def test_predict_updates_inference_p95_metric(admin_client) -> None:
    """After a predict call, `/api/metrics` reports a non-zero inferenceP95Ms
    value and bumps `requestsTotal`."""
    client, _ = admin_client
    before = (await client.get("/api/metrics")).json()

    # Set up an experiment + one predict
    model = (
        await client.post(
            "/api/models", json={"name": f"mw_{secrets.token_hex(3)}"}
        )
    ).json()
    v1 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a")],
                "artifact_params": {"bias": 0.0, "weights": {"a": 1.0}},
            },
        )
    ).json()
    await promote_with_eval_run(client, model["id"], v1["id"])
    exp = (
        await client.post(
            "/api/experiments",
            json={
                "name": f"ew_{secrets.token_hex(3)}",
                "model_a_version_id": v1["id"],
                "weight_a": 100,
            },
        )
    ).json()

    await client.post(
        "/api/inference/predict",
        json={"experiment_id": exp["id"], "subject_key": "m1", "features": {"a": 0.5}},
    )

    after = (await client.get("/api/metrics")).json()
    for key in (
        "requestsTotal",
        "errorsTotal",
        "inferenceP95Ms",
        "inferenceP95ViolationsTotal",
        "activeSessions",
        "feedbackEventsPerMinute",
        "p95BudgetMs",
    ):
        assert key in after
    assert after["requestsTotal"] >= before["requestsTotal"] + 1
    assert after["inferenceP95Ms"] > 0.0
    assert after["p95BudgetMs"] == 150.0
