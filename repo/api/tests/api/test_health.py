import httpx
import pytest


@pytest.mark.asyncio
async def test_health_liveness(api_base_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok"}
    assert resp.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_health_ready_payload_shape(api_base_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.get("/api/health/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    if resp.status_code == 503:
        body = body["detail"]
    assert set(body.keys()) == {"status", "checks"}
    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["checks"], dict)
    assert "kek" in body["checks"]
    assert "db" in body["checks"]


@pytest.mark.asyncio
async def test_unknown_route_returns_envelope(api_base_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        resp = await client.get("/api/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == {"error", "message", "details"}
    assert body["error"] == "not_found"
