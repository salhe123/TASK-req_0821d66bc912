import secrets

import pytest

from tests.api.helpers import promote_with_eval_run


def _feature(name: str, dtype: str = "float") -> dict:
    return {"name": name, "dtype": dtype, "transform": "identity", "source_query_hash": "q1"}


@pytest.mark.asyncio
async def test_register_and_promote_first_version_pins_live_schema(admin_client) -> None:
    client, _ = admin_client
    model = (
        await client.post(
            "/api/models",
            json={"name": f"m_{secrets.token_hex(3)}", "description": "d"},
        )
    ).json()
    v1 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a"), _feature("b")],
                "artifact_uri": "file:///tmp/m.bin",
                "artifact_params": {"bias": 0.1, "weights": {"a": 0.5, "b": -0.3}},
            },
        )
    ).json()
    assert v1["status"] == "DRAFT"
    assert len(v1["feature_schema_hash"]) == 64

    promo = await promote_with_eval_run(client, model["id"], v1["id"])
    assert promo.status_code == 200
    body = promo.json()
    assert body["status"] == "APPROVED"
    assert body["approved_at"] is not None

    # Live schema hash is now pinned
    listing = (await client.get("/api/models")).json()
    item = next(m for m in listing["items"] if m["id"] == model["id"])
    assert item["live_schema_hash"] == v1["feature_schema_hash"]


@pytest.mark.asyncio
async def test_promote_blocked_on_schema_mismatch(admin_client) -> None:
    client, _ = admin_client
    model = (
        await client.post(
            "/api/models", json={"name": f"m_{secrets.token_hex(3)}"}
        )
    ).json()
    v1 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a")],
                "artifact_uri": "",
                "artifact_params": {},
            },
        )
    ).json()
    await promote_with_eval_run(client, model["id"], v1["id"])

    v2 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a"), _feature("c")],
                "artifact_params": {},
            },
        )
    ).json()

    resp = await promote_with_eval_run(client, model["id"], v2["id"])
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "feature_schema_mismatch"
    assert body["details"]["expected_hash"] == v1["feature_schema_hash"]
    assert body["details"]["got_hash"] == v2["feature_schema_hash"]
    assert "c" in body["details"]["extra_in_got"]

    # Fix v2 to match schema → promotion succeeds
    v2_fixed = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a")],
                "artifact_params": {},
            },
        )
    ).json()
    ok = await promote_with_eval_run(client, model["id"], v2_fixed["id"])
    assert ok.status_code == 200
    assert ok.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_experiment_routing_predict_and_rollback(admin_client, db_dsn) -> None:
    client, _ = admin_client
    model = (
        await client.post(
            "/api/models", json={"name": f"m_{secrets.token_hex(3)}"}
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
    v2 = (
        await client.post(
            f"/api/models/{model['id']}/versions",
            json={
                "feature_schema": [_feature("a")],
                "artifact_params": {"bias": 1.0, "weights": {"a": 1.0}},
            },
        )
    ).json()
    await promote_with_eval_run(client, model["id"], v2["id"])

    exp = (
        await client.post(
            "/api/experiments",
            json={
                "name": f"e_{secrets.token_hex(3)}",
                "model_a_version_id": v1["id"],
                "model_b_version_id": v2["id"],
                "weight_a": 50,
            },
        )
    ).json()
    assert exp["weight_a"] == 50
    assert exp["weight_b"] == 50

    # Predict: deterministic given subject. Call twice, same arm + same score.
    r1 = await client.post(
        "/api/inference/predict",
        json={
            "experiment_id": exp["id"],
            "subject_key": "subject-123",
            "features": {"a": 0.5},
        },
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["arm"] in ("A", "B")
    assert body1["subject_key"] == "subject-123"
    assert body1["latency_ms"] >= 0

    r2 = await client.post(
        "/api/inference/predict",
        json={
            "experiment_id": exp["id"],
            "subject_key": "subject-123",
            "features": {"a": 0.5},
        },
    )
    body2 = r2.json()
    assert body2["arm"] == body1["arm"]
    assert body2["model_version_id"] == body1["model_version_id"]
    assert body2["score"] == body1["score"]

    # Rollback flips to 100/0, records a manual trigger, and disables
    # ingest+apply toggles (per Phase 6 isolation guarantee).
    rb = await client.post(
        f"/api/experiments/{exp['id']}/rollback",
        json={"trigger": "manual", "reason": "stopping experiment"},
    )
    assert rb.status_code == 200
    body = rb.json()
    assert body["weight_a"] == 100
    assert body["weight_b"] == 0
    assert body["ingest_enabled"] is False
    assert body["apply_enabled"] is False

    # Re-enable apply to verify the routing flip propagates to predict. After
    # a real incident an operator would do this through the admin console.
    await client.post(
        f"/api/experiments/{exp['id']}/toggle",
        json={"apply_enabled": True},
    )
    for key in ("s1", "s2", "s3"):
        resp = await client.post(
            "/api/inference/predict",
            json={
                "experiment_id": exp["id"],
                "subject_key": key,
                "features": {"a": 0.1},
            },
        )
        assert resp.json()["arm"] == "A"

    # Rollback event persisted with trigger
    import psycopg

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT trigger, reason FROM rollback_events WHERE experiment_id = %s",
            (exp["id"],),
        )
        row = cur.fetchone()
        assert row == ("manual", "stopping experiment")


@pytest.mark.asyncio
async def test_predict_blocked_when_apply_disabled(admin_client) -> None:
    client, _ = admin_client
    model = (
        await client.post(
            "/api/models", json={"name": f"m_{secrets.token_hex(3)}"}
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
                "name": f"e_{secrets.token_hex(3)}",
                "model_a_version_id": v1["id"],
                "weight_a": 100,
            },
        )
    ).json()
    await client.post(
        f"/api/experiments/{exp['id']}/toggle",
        json={"apply_enabled": False},
    )
    r = await client.post(
        "/api/inference/predict",
        json={"experiment_id": exp["id"], "subject_key": "x", "features": {"a": 0.1}},
    )
    assert r.status_code == 409
    assert r.json()["error"] == "experiment_apply_disabled"


@pytest.mark.asyncio
async def test_metrics_endpoint_shape(admin_client) -> None:
    client, _ = admin_client
    r = await client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "requestsTotal",
        "errorsTotal",
        "inferenceP95Ms",
        "inferenceP95ViolationsTotal",
        "activeSessions",
        "feedbackEventsPerMinute",
    ):
        assert key in body
