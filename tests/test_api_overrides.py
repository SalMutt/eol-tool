"""Tests for the manual overrides API endpoints."""

import csv
import io
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from eol_tool.api import _CSV_FIELDS, app

_BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def csv_path(tmp_path):
    """Create a temporary CSV file for testing."""
    path = tmp_path / "overrides.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
    return path


@pytest.fixture
def csv_with_data(tmp_path):
    """Create a temporary CSV file pre-populated with test data."""
    path = tmp_path / "overrides.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerow({
            "model": "EX4300-48T",
            "manufacturer": "Juniper",
            "status": "eol",
            "eol_reason": "manufacturer_declared",
            "risk_category": "security",
            "eol_date": "2023-03-31",
            "eos_date": "2026-03-31",
            "source_url": "https://example.com",
            "notes": "Test entry",
        })
        writer.writerow({
            "model": "PM893",
            "manufacturer": "Samsung",
            "status": "eol",
            "eol_reason": "product_discontinued",
            "risk_category": "procurement",
            "eol_date": "",
            "eos_date": "",
            "source_url": "",
            "notes": "Replaced by PM897",
        })
    return path


@pytest.fixture
async def client(csv_path):
    with patch("eol_tool.api.get_csv_path", return_value=csv_path):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=_BASE) as c:
            yield c


@pytest.fixture
async def client_with_data(csv_with_data):
    with patch("eol_tool.api.get_csv_path", return_value=csv_with_data):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=_BASE) as c:
            yield c


class TestGetOverrides:
    async def test_get_empty(self, client):
        resp = await client.get("/api/overrides")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_with_data(self, client_with_data):
        resp = await client_with_data.get("/api/overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["model"] == "EX4300-48T"
        assert data[0]["manufacturer"] == "Juniper"
        assert data[0]["status"] == "eol"
        assert data[1]["model"] == "PM893"


class TestCreateOverride:
    async def test_create_success(self, client):
        resp = await client.post("/api/overrides", json={
            "model": "MX204",
            "manufacturer": "Juniper",
            "status": "active",
            "risk_category": "none",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["model"] == "MX204"
        assert data["manufacturer"] == "Juniper"
        assert data["status"] == "active"

        # Verify it appears in GET
        resp2 = await client.get("/api/overrides")
        assert len(resp2.json()) == 1

    async def test_create_duplicate(self, client_with_data):
        resp = await client_with_data.post("/api/overrides", json={
            "model": "EX4300-48T",
            "manufacturer": "Juniper",
            "status": "active",
        })
        assert resp.status_code == 409

    async def test_create_invalid_status(self, client):
        resp = await client.post("/api/overrides", json={
            "model": "TestModel",
            "status": "invalid_status",
        })
        assert resp.status_code == 422

    async def test_create_empty_model(self, client):
        resp = await client.post("/api/overrides", json={
            "model": "",
            "status": "eol",
        })
        assert resp.status_code == 422

    async def test_create_invalid_date(self, client):
        resp = await client.post("/api/overrides", json={
            "model": "TestModel",
            "status": "eol",
            "eol_date": "not-a-date",
        })
        assert resp.status_code == 422


class TestUpdateOverride:
    async def test_update_success(self, client_with_data):
        resp = await client_with_data.put("/api/overrides", json={
            "model": "EX4300-48T",
            "manufacturer": "Juniper",
            "status": "active",
            "risk_category": "none",
            "notes": "Updated entry",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["notes"] == "Updated entry"

    async def test_update_not_found(self, client_with_data):
        resp = await client_with_data.put("/api/overrides", json={
            "model": "NONEXISTENT",
            "manufacturer": "",
            "status": "eol",
        })
        assert resp.status_code == 404


class TestDeleteOverride:
    async def test_delete_success(self, client_with_data):
        resp = await client_with_data.delete(
            "/api/overrides",
            params={"model": "EX4300-48T", "manufacturer": "Juniper"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify it's gone
        resp2 = await client_with_data.get("/api/overrides")
        models = [r["model"] for r in resp2.json()]
        assert "EX4300-48T" not in models

    async def test_delete_not_found(self, client_with_data):
        resp = await client_with_data.delete(
            "/api/overrides",
            params={"model": "NONEXISTENT", "manufacturer": ""},
        )
        assert resp.status_code == 404


class TestExportOverrides:
    async def test_export_csv(self, client_with_data):
        resp = await client_with_data.get("/api/overrides/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in resp.headers.get("content-disposition", "")

        # Parse the CSV content
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["model"] == "EX4300-48T"


class TestImportOverrides:
    async def test_import_merge(self, client_with_data):
        csv_content = (
            "model,manufacturer,status,eol_reason,risk_category,eol_date,eos_date,source_url,notes\n"
            "EX4300-48T,Juniper,active,manufacturer_declared,none,,,, Updated via import\n"
            "MX204,Juniper,active,none,none,,,,New model\n"
            "PM893,Samsung,eol,product_discontinued,procurement,,,,Replaced by PM897\n"
        )
        resp = await client_with_data.post(
            "/api/overrides/import",
            files={"file": ("overrides.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] == 1      # MX204
        assert data["updated"] == 1    # EX4300-48T changed status
        assert data["unchanged"] == 1  # PM893 same

        # Verify final state
        resp2 = await client_with_data.get("/api/overrides")
        all_overrides = resp2.json()
        assert len(all_overrides) == 3


class TestOverrideCaseSensitivity:
    async def test_duplicate_case_insensitive(self, client_with_data):
        """Creating with different case should be detected as duplicate."""
        resp = await client_with_data.post("/api/overrides", json={
            "model": "ex4300-48t",
            "manufacturer": "juniper",
            "status": "active",
        })
        assert resp.status_code == 409
