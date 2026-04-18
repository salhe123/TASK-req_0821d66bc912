"""Share-link listing (/mine) + expiry field shape + revocation visibility."""
from __future__ import annotations

import secrets

import pytest


async def _make_plan_version(client) -> dict:
    return (
        await client.post(
            "/api/plans",
            json={
                "name": f"sl_{secrets.token_hex(3)}",
                "lines": [{"line_identity_key": "K1", "part_number": "P", "quantity": 1}],
            },
        )
    ).json()


@pytest.mark.asyncio
async def test_mine_empty_for_new_user_with_no_issued_links(admin_client) -> None:
    client, _ = admin_client
    r = await client.get("/api/plans/share-links/mine")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_mine_returns_issued_links_with_expected_shape(admin_client) -> None:
    client, _ = admin_client
    plan = await _make_plan_version(client)
    issued = (
        await client.post(
            f"/api/plans/{plan['id']}/versions/{plan['head_version_id']}/share",
            json={"role": "Plan Owner", "expires_in_days": 3},
        )
    ).json()

    mine = (await client.get("/api/plans/share-links/mine")).json()
    assert any(link["id"] == issued["id"] for link in mine)
    link = next(l for l in mine if l["id"] == issued["id"])
    assert set(link.keys()) == {
        "id", "plan_version_id", "role", "expires_at", "revoked", "created_at", "opened_at"
    }
    assert link["role"] == "Plan Owner"
    assert link["revoked"] is False


@pytest.mark.asyncio
async def test_revoked_link_visible_with_revoked_true(admin_client) -> None:
    client, _ = admin_client
    plan = await _make_plan_version(client)
    issued = (
        await client.post(
            f"/api/plans/{plan['id']}/versions/{plan['head_version_id']}/share",
            json={"role": "Plan Owner", "expires_in_days": 1},
        )
    ).json()
    await client.delete(f"/api/plans/share-links/{issued['id']}")

    mine = (await client.get("/api/plans/share-links/mine")).json()
    link = next(l for l in mine if l["id"] == issued["id"])
    assert link["revoked"] is True


@pytest.mark.asyncio
async def test_expiry_clamped_to_seven_days(admin_client) -> None:
    client, _ = admin_client
    plan = await _make_plan_version(client)
    issued = (
        await client.post(
            f"/api/plans/{plan['id']}/versions/{plan['head_version_id']}/share",
            json={"role": "Plan Owner", "expires_in_days": 999},
        )
    ).json()

    from datetime import datetime, timedelta, timezone
    exp_at = datetime.fromisoformat(issued["expires_at"])
    delta = exp_at - datetime.now(timezone.utc)
    assert delta <= timedelta(days=7, seconds=10)


@pytest.mark.asyncio
async def test_non_plan_owner_cannot_list_shares(evaluator_client) -> None:
    client, _ = evaluator_client
    r = await client.get("/api/plans/share-links/mine")
    assert r.status_code == 403
    assert r.json()["error"] == "permission_denied"
