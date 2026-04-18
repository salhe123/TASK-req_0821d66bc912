from __future__ import annotations

import secrets

import httpx
import pytest


@pytest.mark.asyncio
async def test_every_mutating_endpoint_requires_csrf(admin_client) -> None:
    """Spot-check a cross-section of mutating endpoints — each must 403 csrf_missing
    when the X-CSRF-Token header is stripped but auth is present."""
    client, _ = admin_client
    no_csrf = {"X-CSRF-Token": "", "Authorization": client.headers["Authorization"]}

    probes = [
        ("POST", "/api/admin/users", {"username": "x", "display_name": "", "password": "x" * 12, "roles": []}),
        ("POST", "/api/templates", {"name": "x", "items": [{"key": "a", "label": "A", "weight": 1, "required": True, "missing_strategy": "ZERO_FILL"}]}),
        ("POST", "/api/plans", {"name": "x", "lines": [{"line_identity_key": "K", "part_number": "P", "quantity": 1}]}),
        ("POST", "/api/models", {"name": "x"}),
        ("POST", "/api/experiments", {"name": "x", "model_a_version_id": "00000000-0000-0000-0000-000000000000", "weight_a": 100}),
        ("POST", "/api/feedback", {"experiment_id": "00000000-0000-0000-0000-000000000000", "subject_key": "s", "target_id": "t", "kind": "LIKE"}),
        ("POST", "/api/admin/backups", None),
    ]
    for method, path, body in probes:
        r = await client.request(method, path, json=body, headers=no_csrf)
        assert r.status_code == 403, (path, r.status_code, r.text)
        assert r.json()["error"] == "csrf_missing", path


@pytest.mark.asyncio
async def test_safe_methods_do_not_require_csrf(admin_client) -> None:
    client, _ = admin_client
    no_csrf = {"X-CSRF-Token": "", "Authorization": client.headers["Authorization"]}
    r = await client.get("/api/admin/users", headers=no_csrf)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_response_carries_request_id(admin_client) -> None:
    client, _ = admin_client
    r = await client.get("/api/health")
    assert "x-request-id" in r.headers
    assert len(r.headers["x-request-id"]) >= 8


@pytest.mark.asyncio
async def test_masking_hides_sensitive_fields_for_unauthorized_caller(evaluator_client) -> None:
    """The `/me` endpoint exposes the caller's own allowlist; an Evaluator role
    does not carry a wildcard, so the allowlist contains only the fields the
    role explicitly grants (evaluator_notes)."""
    client, _ = evaluator_client
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert "*" not in body["field_view_allowlist"]
    assert "evaluator_notes" in body["field_view_allowlist"]


@pytest.mark.asyncio
async def test_failing_login_returns_full_envelope_shape(api_base_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        r = await client.post("/api/auth/login", json={"username": "nope", "password": "nope"})
    assert r.status_code == 401
    body = r.json()
    assert set(body.keys()) == {"error", "message", "details"}
    assert body["error"] == "invalid_credentials"
    assert body["details"] == {}
