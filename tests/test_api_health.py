"""Tests for the /api/health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from eol_tool.api import app
from eol_tool.health import get_checker_health

_BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_health():
    get_checker_health().reset()
    yield
    get_checker_health().reset()


@pytest.mark.anyio
async def test_health_returns_200_with_structure(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "checkers" in data
    assert "overall_status" in data
    assert "total_checks" in data
    assert "total_failures" in data
    assert "uptime_seconds" in data
    assert "recommendations" in data
    assert "version" in data


@pytest.mark.anyio
async def test_health_has_checkers_dict(client):
    h = get_checker_health()
    h.record_success("Intel ARK", "X520-DA2", 150.0)
    resp = await client.get("/api/health")
    data = resp.json()
    assert isinstance(data["checkers"], dict)
    assert "Intel ARK" in data["checkers"]
    assert data["checkers"]["Intel ARK"]["successes"] == 1


@pytest.mark.anyio
async def test_health_has_overall_status(client):
    resp = await client.get("/api/health")
    data = resp.json()
    assert data["overall_status"] in ("healthy", "degraded", "down", "idle")


@pytest.mark.anyio
async def test_health_recommendations_for_idle(client):
    resp = await client.get("/api/health")
    data = resp.json()
    assert any("No EOL checks recorded" in r for r in data["recommendations"])


@pytest.mark.anyio
async def test_health_recommendations_for_down_scraper(client):
    h = get_checker_health()
    for i in range(10):
        h.record_failure("Intel ARK", f"m-{i}", "Timeout", 5000.0)
    resp = await client.get("/api/health")
    data = resp.json()
    assert any("Intel ARK" in r and "failing" in r for r in data["recommendations"])
