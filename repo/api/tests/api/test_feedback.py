from __future__ import annotations

import secrets

import psycopg
import pytest

from tests.api.helpers import promote_with_eval_run


def _feature(name: str) -> dict:
    return {"name": name, "dtype": "float", "transform": "identity", "source_query_hash": "q"}


async def _setup_experiment(client) -> dict:
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
    return {"exp": exp, "v1": v1, "v2": v2}


@pytest.mark.asyncio
async def test_rate_limit_60_per_minute_per_subject(admin_client) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)
    subject = f"subj_{secrets.token_hex(3)}"

    for i in range(60):
        r = await client.post(
            "/api/feedback",
            json={
                "experiment_id": ctx["exp"]["id"],
                "subject_key": subject,
                "target_id": f"t-{i}",
                "kind": "LIKE",
                "arm": "A",
                "model_version_id": ctx["v1"]["id"],
            },
        )
        assert r.status_code == 201, (i, r.text)

    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": subject,
            "target_id": "t-61",
            "kind": "LIKE",
            "arm": "A",
            "model_version_id": ctx["v1"]["id"],
        },
    )
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"


@pytest.mark.asyncio
async def test_ingest_disabled_records_event_but_not_signal(admin_client, db_dsn) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)

    # Toggle ingest off
    await client.post(
        f"/api/experiments/{ctx['exp']['id']}/toggle",
        json={"ingest_enabled": False},
    )

    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": "sx",
            "target_id": "t1",
            "kind": "LIKE",
            "arm": "A",
            "model_version_id": ctx["v1"]["id"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["signal_updated"] is False

    # Event was recorded
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM feedback_events WHERE experiment_id = %s AND subject_key = %s",
            (ctx["exp"]["id"], "sx"),
        )
        assert cur.fetchone()[0] == 1
        # but no signal row
        cur.execute(
            "SELECT count(*) FROM feedback_signals WHERE experiment_id = %s",
            (ctx["exp"]["id"],),
        )
        assert cur.fetchone()[0] == 0


@pytest.mark.asyncio
async def test_block_persists_independently_of_toggle(admin_client, db_dsn) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)

    # Toggle ingest off; BLOCK should still persist in subject_blocks
    await client.post(
        f"/api/experiments/{ctx['exp']['id']}/toggle",
        json={"ingest_enabled": False},
    )
    subject = f"blk_{secrets.token_hex(3)}"
    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": subject,
            "target_id": "item-1",
            "kind": "BLOCK",
            "arm": "A",
            "model_version_id": ctx["v1"]["id"],
        },
    )
    assert r.status_code == 201

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM subject_blocks WHERE subject_key = %s AND target_id = %s",
            (subject, "item-1"),
        )
        assert cur.fetchone()[0] == 1

    resp = await client.get(f"/api/feedback/blocks/{subject}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject_key"] == subject
    assert body["items"][0]["target_id"] == "item-1"


@pytest.mark.asyncio
async def test_rollback_preserves_events_and_isolates_arms(admin_client, db_dsn) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)

    # Record LIKEs on both arms
    for (arm, mv) in [("A", ctx["v1"]["id"]), ("B", ctx["v2"]["id"])]:
        for i in range(3):
            await client.post(
                "/api/feedback",
                json={
                    "experiment_id": ctx["exp"]["id"],
                    "subject_key": f"s-{arm}-{i}",
                    "target_id": "target-X",
                    "kind": "LIKE",
                    "arm": arm,
                    "model_version_id": mv,
                },
            )

    signals_before = (
        await client.get(f"/api/feedback/signals/{ctx['exp']['id']}")
    ).json()
    by_arm_before = {s["arm"]: s["like_count"] for s in signals_before["items"] if s["target_id"] == "target-X"}
    assert by_arm_before == {"A": 3, "B": 3}

    # Rollback: flips weights (100,0), disables ingest + apply; events remain.
    rb = await client.post(
        f"/api/experiments/{ctx['exp']['id']}/rollback",
        json={"trigger": "manual", "reason": "isolating arms"},
    )
    assert rb.status_code == 200
    assert rb.json()["weight_a"] == 100
    assert rb.json()["ingest_enabled"] is False
    assert rb.json()["apply_enabled"] is False

    # Events count unchanged
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT arm, count(*) FROM feedback_events WHERE experiment_id = %s GROUP BY arm",
            (ctx["exp"]["id"],),
        )
        by_arm = {r[0]: r[1] for r in cur.fetchall()}
        assert by_arm == {"A": 3, "B": 3}

    # Signals untouched (rollback doesn't pollute the other arm)
    signals_after = (
        await client.get(f"/api/feedback/signals/{ctx['exp']['id']}")
    ).json()
    by_arm_after = {s["arm"]: s["like_count"] for s in signals_after["items"] if s["target_id"] == "target-X"}
    assert by_arm_after == by_arm_before


async def _setup_single_arm_experiment(client) -> dict:
    """Build an experiment with only an A arm (no model_b)."""
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
    return {"exp": exp, "v1": v1}


@pytest.mark.asyncio
async def test_arm_b_rejected_when_experiment_has_no_b_arm(admin_client) -> None:
    client, _ = admin_client
    ctx = await _setup_single_arm_experiment(client)

    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": "sbj",
            "target_id": "t1",
            "kind": "LIKE",
            "arm": "B",
            "model_version_id": ctx["v1"]["id"],
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "arm_not_routed"


@pytest.mark.asyncio
async def test_arm_model_mismatch_rejected(admin_client) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)

    # Claim arm A but submit the B model_version — this is exactly the stale-
    # client scenario we want to catch.
    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": "sbj",
            "target_id": "t1",
            "kind": "LIKE",
            "arm": "A",
            "model_version_id": ctx["v2"]["id"],
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "arm_model_mismatch"


@pytest.mark.asyncio
async def test_model_not_in_experiment_rejected(admin_client) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)

    # A model version that isn't routed by this experiment at all.
    other = (
        await client.post("/api/models", json={"name": f"o_{secrets.token_hex(3)}"})
    ).json()
    other_v = (
        await client.post(
            f"/api/models/{other['id']}/versions",
            json={
                "feature_schema": [_feature("a")],
                "artifact_params": {"bias": 5.0, "weights": {"a": 1.0}},
            },
        )
    ).json()
    await promote_with_eval_run(client, other["id"], other_v["id"])

    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": "sbj",
            "target_id": "t1",
            "kind": "LIKE",
            "arm": "A",
            "model_version_id": other_v["id"],
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "model_not_in_experiment"


@pytest.mark.asyncio
async def test_valid_arm_model_pair_accepted_and_attributes_to_routing(
    admin_client, db_dsn
) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)

    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": "sbj",
            "target_id": "tX",
            "kind": "LIKE",
            "arm": "B",
            "model_version_id": ctx["v2"]["id"],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["arm"] == "B"
    assert r.json()["signal_updated"] is True

    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT arm, model_version_id FROM feedback_events "
            "WHERE experiment_id = %s AND target_id = 'tX'",
            (ctx["exp"]["id"],),
        )
        row = cur.fetchone()
        assert row[0] == "B"
        assert str(row[1]) == ctx["v2"]["id"]


@pytest.mark.asyncio
async def test_invalid_kind_rejected(admin_client) -> None:
    client, _ = admin_client
    ctx = await _setup_experiment(client)
    r = await client.post(
        "/api/feedback",
        json={
            "experiment_id": ctx["exp"]["id"],
            "subject_key": "s",
            "target_id": "t",
            "kind": "MAYBE",
            "arm": "A",
            "model_version_id": ctx["v1"]["id"],
        },
    )
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"
