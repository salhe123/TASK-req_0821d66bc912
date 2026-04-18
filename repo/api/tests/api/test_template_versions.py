"""Template publishing: first creation + publishing subsequent versions
bumping version_no, duplicate-keys rejected, not-found, permission."""
from __future__ import annotations

import secrets

import psycopg
import pytest


def _item(key: str, weight: float = 1.0) -> dict:
    return {
        "key": key, "label": key.upper(), "weight": weight, "required": True,
        "missing_strategy": "ZERO_FILL",
    }


@pytest.mark.asyncio
async def test_list_templates_returns_latest_only_info(admin_client) -> None:
    client, _ = admin_client
    name = f"tlist_{secrets.token_hex(3)}"
    (
        await client.post(
            "/api/templates", json={"name": name, "items": [_item("q1"), _item("q2")]}
        )
    ).raise_for_status()
    listing = (await client.get("/api/templates")).json()
    entry = next(t for t in listing if t["name"] == name)
    assert entry["latest_version_no"] == 1
    assert {i["key"] for i in entry["items"]} == {"q1", "q2"}


@pytest.mark.asyncio
async def test_publish_new_version_bumps_number(admin_client, db_dsn: str) -> None:
    client, _ = admin_client
    name = f"tbump_{secrets.token_hex(3)}"
    tpl = (
        await client.post(
            "/api/templates", json={"name": name, "items": [_item("a")]}
        )
    ).json()
    assert tpl["latest_version_no"] == 1
    v1_id = tpl["latest_version_id"]

    v2_resp = await client.post(
        f"/api/templates/{tpl['id']}/versions",
        json={"name": name, "items": [_item("a"), _item("b", weight=2.0)]},
    )
    assert v2_resp.status_code == 201
    v2 = v2_resp.json()
    assert v2["latest_version_no"] == 2
    assert v2["latest_version_id"] != v1_id

    # Listing reflects the latest
    again = (await client.get("/api/templates")).json()
    entry = next(t for t in again if t["id"] == tpl["id"])
    assert entry["latest_version_no"] == 2

    # Audit row for publish
    with psycopg.connect(db_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT payload FROM audit_logs WHERE action = 'TEMPLATE_VERSION_PUBLISH' "
            "AND resource_id = %s ORDER BY created_at DESC LIMIT 1",
            (tpl["id"],),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0]["version_no"] == 2


@pytest.mark.asyncio
async def test_publish_duplicate_item_keys_rejected(admin_client) -> None:
    client, _ = admin_client
    name = f"tdup_{secrets.token_hex(3)}"
    tpl = (
        await client.post(
            "/api/templates", json={"name": name, "items": [_item("a")]}
        )
    ).json()
    r = await client.post(
        f"/api/templates/{tpl['id']}/versions",
        json={"name": name, "items": [_item("a"), _item("a")]},
    )
    assert r.status_code == 409
    assert r.json()["error"] == "duplicate_item_keys"


@pytest.mark.asyncio
async def test_publish_unknown_template_404(admin_client) -> None:
    client, _ = admin_client
    r = await client.post(
        "/api/templates/00000000-0000-0000-0000-000000000000/versions",
        json={"name": "nope", "items": [_item("a")]},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_template_name_conflict(admin_client) -> None:
    client, _ = admin_client
    name = f"tname_{secrets.token_hex(3)}"
    (
        await client.post(
            "/api/templates", json={"name": name, "items": [_item("a")]}
        )
    ).raise_for_status()
    r = await client.post(
        "/api/templates", json={"name": name, "items": [_item("a")]}
    )
    assert r.status_code == 409
    assert r.json()["error"] == "template_name_taken"


@pytest.mark.asyncio
async def test_create_template_invalid_missing_strategy_rejected(admin_client) -> None:
    client, _ = admin_client
    r = await client.post(
        "/api/templates",
        json={
            "name": f"bad_{secrets.token_hex(3)}",
            "items": [{
                "key": "a", "label": "A", "weight": 1, "required": True,
                "missing_strategy": "NOT_A_STRATEGY",
            }],
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_non_admin_cannot_publish_template(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.post(
        "/api/templates", json={"name": "x", "items": [_item("a")]}
    )
    assert r.status_code == 403
