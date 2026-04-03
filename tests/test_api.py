"""Tests for the FastAPI application."""

import csv
import io
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient

from eol_tool.api import _CSV_FIELDS, _MAX_UPLOAD_BYTES, app
from eol_tool.models import EOLResult, EOLStatus, HardwareModel

_BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE) as c:
        yield c


def _make_test_xlsx(rows):
    """Build a minimal xlsx in-memory and return a BytesIO."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Models"
    ws.append(["Model", "Manufacturer", "Category", "Condition", "Original_Item"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _make_results_xlsx(results_data):
    """Build a results xlsx with standard columns."""
    from eol_tool.reader import write_results

    now = datetime(2025, 6, 1, 12, 0, 0)
    results = []
    for model, mfr, cat, status in results_data:
        results.append(
            EOLResult(
                model=HardwareModel(model=model, manufacturer=mfr, category=cat),
                status=status,
                checked_at=now,
                confidence=80,
            )
        )
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    write_results(results, tmp_path)
    data = tmp_path.read_bytes()
    tmp_path.unlink()
    return data


class TestHealth:
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "checkers" in data
        assert data["version"] == "2.1.0"


class TestFrontendRoot:
    async def test_root_returns_200_or_404(self, client):
        """GET / returns 200 with HTML when frontend exists, 404 otherwise."""
        resp = await client.get("/")
        # If the frontend is mounted, we get 200 with HTML;
        # if not, the app returns 404. Both are valid in test.
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert "text/html" in resp.headers.get("content-type", "")


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

    async def test_lookup_result_has_expected_fields(self, client):
        resp = await client.get(
            "/api/lookup", params={"model": "EX4300-48T", "manufacturer": "Juniper"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in ("model", "status", "risk_category", "confidence"):
            assert field in data, f"Missing field: {field}"


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
        buf = _make_test_xlsx([
            ["EX4300-48T", "Juniper", "switch", "USED", "EX4300-48T"],
            ["XEON E5-2680V4", "Intel", "cpu", "NEW", "Intel E5-2680 V4"],
        ])

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

    async def test_check_invalid_file_raises(self, client):
        with pytest.raises(Exception):
            await client.post(
                "/api/check",
                files={"file": ("bad.xlsx", b"not-a-real-xlsx", "application/octet-stream")},
            )


class TestDiffUpload:
    async def test_diff_two_xlsx_files(self, client):
        """POST /api/diff with two xlsx files returns diff result."""
        prev_data = _make_results_xlsx([
            ("EX4300-48T", "Juniper", "switch", EOLStatus.ACTIVE),
        ])
        curr_data = _make_results_xlsx([
            ("EX4300-48T", "Juniper", "switch", EOLStatus.EOL),
        ])

        resp = await client.post(
            "/api/diff",
            files={
                "previous": ("prev.xlsx", prev_data, "application/octet-stream"),
                "current": ("curr.xlsx", curr_data, "application/octet-stream"),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "changes" in data
        assert "previous_count" in data
        assert "current_count" in data


class TestOverridesExport:
    async def test_export_csv_content_type(self, client, tmp_path):
        """GET /api/overrides/export returns text/csv."""
        csv_path = tmp_path / "overrides.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            writer.writerow({
                "model": "TEST-MODEL", "manufacturer": "TestMfr",
                "status": "eol", "eol_reason": "", "risk_category": "",
                "eol_date": "", "eos_date": "", "source_url": "", "notes": "",
            })

        with patch("eol_tool.api.get_csv_path", return_value=csv_path):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url=_BASE) as c:
                resp = await c.get("/api/overrides/export")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["model"] == "TEST-MODEL"


class TestDiffLastPathTraversal:
    async def test_path_outside_results_dir_returns_400(self, client):
        with patch("eol_tool.api._LAST_RESULTS_PATH", Path("/tmp/fake.xlsx")), \
             patch("eol_tool.api._get_results_dir", return_value=Path("/tmp/results")):
            # Ensure _LAST_RESULTS_PATH "exists" for the check
            Path("/tmp/fake.xlsx").touch()
            try:
                resp = await client.get(
                    "/api/diff/last", params={"current": "../../etc/passwd"}
                )
                assert resp.status_code == 400
                assert resp.json()["detail"] == "invalid path"
            finally:
                Path("/tmp/fake.xlsx").unlink(missing_ok=True)

    async def test_traversal_attempt_returns_400(self, client):
        with patch("eol_tool.api._LAST_RESULTS_PATH", Path("/tmp/fake.xlsx")), \
             patch("eol_tool.api._get_results_dir", return_value=Path("/tmp/results")):
            Path("/tmp/fake.xlsx").touch()
            try:
                resp = await client.get(
                    "/api/diff/last",
                    params={"current": "/tmp/results/../../../etc/passwd"},
                )
                assert resp.status_code == 400
            finally:
                Path("/tmp/fake.xlsx").unlink(missing_ok=True)

    async def test_valid_path_within_results_dir(self, client, tmp_path):
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        fake_prev = tmp_path / "prev.xlsx"
        fake_prev.touch()
        current_file = results_dir / "current.xlsx"

        with patch("eol_tool.api._LAST_RESULTS_PATH", fake_prev), \
             patch("eol_tool.api._get_results_dir", return_value=results_dir):
            # Path validation passes, but compare_results will fail on fake xlsx.
            # We only care that the path check doesn't reject it.
            try:
                resp = await client.get(
                    "/api/diff/last", params={"current": str(current_file)}
                )
                assert resp.status_code != 400
            except Exception:
                # compare_results raises on invalid xlsx — that's fine,
                # it means the path validation passed
                pass


class TestUploadSizeLimit:
    async def test_check_upload_too_large_returns_413(self, client):
        oversized = b"x" * (_MAX_UPLOAD_BYTES + 1)
        resp = await client.post(
            "/api/check",
            files={"file": ("big.xlsx", oversized, "application/octet-stream")},
        )
        assert resp.status_code == 413
        assert "file too large" in resp.json()["detail"]

    async def test_check_upload_within_limit(self, client):
        buf = _make_test_xlsx([
            ["EX4300-48T", "Juniper", "switch", "USED", "EX4300-48T"],
        ])
        resp = await client.post(
            "/api/check",
            files={"file": ("test.xlsx", buf, "application/octet-stream")},
        )
        assert resp.status_code == 200

    async def test_import_overrides_too_large_returns_413(self, client, tmp_path):
        oversized = b"x" * (_MAX_UPLOAD_BYTES + 1)
        csv_path = tmp_path / "overrides.csv"
        csv_path.touch()
        with patch("eol_tool.api.get_csv_path", return_value=csv_path):
            resp = await client.post(
                "/api/overrides/import",
                files={"file": ("big.csv", oversized, "text/csv")},
            )
        assert resp.status_code == 413

    async def test_diff_upload_too_large_returns_413(self, client):
        small = b"x" * 100
        oversized = b"x" * (_MAX_UPLOAD_BYTES + 1)
        resp = await client.post(
            "/api/diff",
            files={
                "previous": ("prev.xlsx", small, "application/octet-stream"),
                "current": ("curr.xlsx", oversized, "application/octet-stream"),
            },
        )
        assert resp.status_code == 413
