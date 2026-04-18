"""Shared helpers for the API-tier tests."""
from __future__ import annotations

import httpx


async def promote_with_eval_run(
    client: httpx.AsyncClient, model_id: str, version_id: str
) -> httpx.Response:
    """Start + complete an evaluation run, then promote. Required by the
    model promotion gate introduced after the delivery audit."""
    start = await client.post(
        f"/api/models/{model_id}/versions/{version_id}/runs",
        json={"kind": "EVALUATION", "dataset_ref": "holdout-v1"},
    )
    assert start.status_code == 201, start.text
    run_id = start.json()["id"]
    done = await client.post(
        f"/api/models/{model_id}/versions/{version_id}/runs/{run_id}/complete",
        json={"status": "SUCCEEDED", "metrics": {"auc": 0.92}},
    )
    assert done.status_code == 200, done.text
    return await client.post(f"/api/models/{model_id}/versions/{version_id}/promote")
