"""Tests for the GET /api/status endpoint."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from eol_tool.api import app
from eol_tool.models import (
    EOLResult,
    EOLStatus,
    HardwareModel,
    RiskCategory,
)
from eol_tool.reader import write_results

_BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE) as c:
        yield c


def _make_results(count: int = 3) -> list[EOLResult]:
    """Create sample EOLResult objects for testing."""
    samples = [
        ("EX4300-48T", "Juniper", EOLStatus.EOL),
        ("EPYC-7413", "AMD", EOLStatus.ACTIVE),
        ("MYSTERY-X", "Unknown", EOLStatus.UNKNOWN),
        ("PM893", "Samsung", EOLStatus.EOL),
        ("E5-2680V4", "Intel", EOLStatus.ACTIVE),
    ]
    results = []
    for i in range(min(count, len(samples))):
        model_str, mfr, status = samples[i]
        results.append(
            EOLResult(
                model=HardwareModel(model=model_str, manufacturer=mfr, category="test"),
                status=status,
                eol_date=date(2024, 1, 1) if status == EOLStatus.EOL else None,
                source_name="test-source",
                checked_at=datetime(2025, 6, 1, 12, 0, 0),
                confidence=80,
                risk_category=RiskCategory.NONE,
            )
        )
    return results


def _write_results_file(results_dir: Path, timestamp: str = "2025-06-01T12-00-00") -> Path:
    """Write a results xlsx file with the standard naming convention."""
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"eol-results-{timestamp}.xlsx"
    results = _make_results(5)
    write_results(results, path)
    return path


class TestApiStatus:
    """Tests for GET /api/status."""

    async def test_returns_expected_fields(self, client, tmp_path):
        """Status response contains all required top-level keys."""
        with patch("eol_tool.api._get_results_dir", return_value=tmp_path / "empty"):
            resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        for key in (
            "last_check_time",
            "last_check_file",
            "total_models",
            "eol_count",
            "active_count",
            "unknown_count",
            "cache_stats",
            "next_scheduled_check",
        ):
            assert key in data, f"Missing key: {key}"

    async def test_correct_counts_from_results(self, client, tmp_path):
        """Counts match what is in the most recent results file."""
        results_dir = tmp_path / "results"
        _write_results_file(results_dir)

        with patch("eol_tool.api._get_results_dir", return_value=results_dir):
            resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_models"] == 5
        assert data["eol_count"] == 2  # EX4300-48T + PM893
        assert data["active_count"] == 2  # EPYC-7413 + E5-2680V4
        assert data["unknown_count"] == 1  # MYSTERY-X
        assert data["last_check_file"] == "eol-results-2025-06-01T12-00-00.xlsx"
        assert data["last_check_time"] == "2025-06-01T12:00:00"

    async def test_null_next_scheduled_check(self, client, tmp_path):
        """next_scheduled_check is null when no scheduler is running."""
        results_dir = tmp_path / "results"
        _write_results_file(results_dir)

        with (
            patch("eol_tool.api._get_results_dir", return_value=results_dir),
            patch("eol_tool.api._next_scheduled_check", None),
        ):
            resp = await client.get("/api/status")
        data = resp.json()
        assert data["next_scheduled_check"] is None

    async def test_missing_results_directory(self, client, tmp_path):
        """Gracefully handles a nonexistent results directory."""
        nonexistent = tmp_path / "does-not-exist"

        with patch("eol_tool.api._get_results_dir", return_value=nonexistent):
            resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_check_time"] is None
        assert data["last_check_file"] is None
        assert data["total_models"] == 0
        assert data["eol_count"] == 0
        assert data["active_count"] == 0
        assert data["unknown_count"] == 0

    async def test_picks_latest_file(self, client, tmp_path):
        """When multiple results files exist, uses the most recent one."""
        results_dir = tmp_path / "results"
        _write_results_file(results_dir, "2025-01-01T08-00-00")
        _write_results_file(results_dir, "2025-06-15T14-30-00")
        _write_results_file(results_dir, "2025-03-10T10-00-00")

        with patch("eol_tool.api._get_results_dir", return_value=results_dir):
            resp = await client.get("/api/status")
        data = resp.json()
        assert data["last_check_file"] == "eol-results-2025-06-15T14-30-00.xlsx"
        assert data["last_check_time"] == "2025-06-15T14:30:00"

    async def test_cache_stats_included(self, client, tmp_path):
        """cache_stats key is present (may be dict or null)."""
        with patch("eol_tool.api._get_results_dir", return_value=tmp_path / "empty"):
            resp = await client.get("/api/status")
        data = resp.json()
        # cache_stats should be a dict (from the cache) or null on error
        assert "cache_stats" in data

    async def test_empty_results_dir(self, client, tmp_path):
        """Handles an existing but empty results directory."""
        results_dir = tmp_path / "results"
        results_dir.mkdir(parents=True)

        with patch("eol_tool.api._get_results_dir", return_value=results_dir):
            resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_check_time"] is None
        assert data["last_check_file"] is None
        assert data["total_models"] == 0
