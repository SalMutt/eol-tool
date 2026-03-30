"""Tests for the FastAPI application."""

import io

import pytest
from httpx import ASGITransport, AsyncClient

from eol_tool.api import app

_BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE) as c:
        yield c


class TestHealth:
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestLookup:
    async def test_known_model(self, client):
        resp = await client.get(
            "/api/lookup", params={"model": "EX4300-48T", "manufacturer": "Juniper"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] is not None
        assert data["manufacturer"] == "Juniper"
        assert data["status"] in ("eol", "eol_announced", "active", "unknown", "not_found")

    async def test_unknown_model(self, client):
        resp = await client.get(
            "/api/lookup",
            params={"model": "ZZZZZ-NONEXISTENT-99999", "manufacturer": "FakeMfr"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("unknown", "not_found")

    async def test_without_manufacturer(self, client):
        resp = await client.get("/api/lookup", params={"model": "EX4300-48T"})
        assert resp.status_code == 200
        data = resp.json()
        # Should have inferred Juniper from the EX prefix
        assert data["manufacturer"] == "Juniper"

    async def test_missing_model_param(self, client):
        resp = await client.get("/api/lookup")
        assert resp.status_code == 422


class TestSources:
    async def test_sources(self, client):
        resp = await client.get("/api/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) > 0
        first = data["sources"][0]
        assert "name" in first
        assert "type" in first


class TestCheckUpload:
    async def test_check_with_xlsx(self, client):
        """Upload a small test xlsx and verify the response structure."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Models"
        ws.append(["Model", "Manufacturer", "Category", "Condition", "Original_Item"])
        ws.append(["EX4300-48T", "Juniper", "switch", "USED", "EX4300-48T"])
        ws.append(["XEON E5-2680V4", "Intel", "cpu", "NEW", "Intel E5-2680 V4"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        resp = await client.post(
            "/api/check",
            files={"file": (
                "test.xlsx", buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] == 2
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 2
        assert "eol" in data
        assert "active" in data
        assert "unknown" in data
        assert "not_found" in data
        assert "dated" in data

    async def test_check_missing_file(self, client):
        resp = await client.post("/api/check")
        assert resp.status_code == 422
