"""Tests for expanded endoflife.date cycle matching and date supplementation."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from eol_tool.checkers.endoflife_date import (
    EndOfLifeDateChecker,
    supplement_missing_dates,
)
from eol_tool.models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

FIXTURES = Path(__file__).parent / "fixtures" / "endoflife_date"


def load_fixture(name: str) -> list:
    return json.loads((FIXTURES / name).read_text())


ALL_PRODUCTS = load_fixture("all_products.json")
INTEL_PROCESSORS = load_fixture("intel_processors.json")
NVIDIA_GPU = load_fixture("nvidia_gpu.json")

BASE = "https://endoflife.date/api"


def _mock_all_products(httpx_mock, is_reusable=False):
    httpx_mock.add_response(url=f"{BASE}/all.json", json=ALL_PRODUCTS, is_reusable=is_reusable)


# ---------------------------------------------------------------------------
# Xeon Scalable matching (Strategy 1c)
# ---------------------------------------------------------------------------


class TestXeonScalableMatching:
    """Xeon Scalable processors should match generation-specific cycles."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)
        httpx_mock.add_response(
            url=f"{BASE}/intel-processors.json", json=INTEL_PROCESSORS,
        )

    @pytest.mark.asyncio
    async def test_silver_4110_matches_skylake_xeon(self, httpx_mock):
        model = HardwareModel(
            model="Xeon Silver 4110", manufacturer="Intel", category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2024, 3, 1)
        assert result.confidence == 70
        assert "skylake-xeon" in result.notes
        assert result.date_source == "community_database"

    @pytest.mark.asyncio
    async def test_silver_4210_matches_cascade_lake(self, httpx_mock):
        model = HardwareModel(
            model="Xeon Silver 4210", manufacturer="Intel", category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2025, 12, 31)
        assert result.confidence == 70
        assert "cascade-lake-xeon" in result.notes

    @pytest.mark.asyncio
    async def test_gold_6248_matches_cascade_lake(self, httpx_mock):
        model = HardwareModel(
            model="Xeon Gold 6248", manufacturer="Intel", category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2025, 12, 31)
        assert "cascade-lake-xeon" in result.notes

    @pytest.mark.asyncio
    async def test_silver_4310_matches_ice_lake(self, httpx_mock):
        model = HardwareModel(
            model="Xeon Silver 4310", manufacturer="Intel", category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.ACTIVE
        assert result.eol_date is None
        assert "ice-lake-xeon" in result.notes


# ---------------------------------------------------------------------------
# NVIDIA VCQ extraction (Strategy 1d)
# ---------------------------------------------------------------------------


class TestNvidiaVcqExtraction:
    """NVIDIA VCQ part numbers should extract GPU family for matching."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)
        httpx_mock.add_response(
            url=f"{BASE}/nvidia-gpu.json", json=NVIDIA_GPU,
        )

    @pytest.mark.asyncio
    async def test_vcqp1000_matches_pascal(self, httpx_mock):
        model = HardwareModel(
            model="VCQP1000-PB", manufacturer="NVIDIA", category="gpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2024, 6, 30)
        assert result.confidence == 70
        assert "pascal" in result.notes

    @pytest.mark.asyncio
    async def test_vcqrtx4000_matches_turing(self, httpx_mock):
        model = HardwareModel(
            model="VCQRTX4000-PB", manufacturer="NVIDIA", category="gpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2025, 12, 31)
        assert "turing" in result.notes

    @pytest.mark.asyncio
    async def test_vcqk1200_matches_maxwell(self, httpx_mock):
        model = HardwareModel(
            model="VCQK1200-T", manufacturer="NVIDIA", category="gpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2023, 3, 31)
        assert "maxwell" in result.notes


# ---------------------------------------------------------------------------
# supplement_missing_dates
# ---------------------------------------------------------------------------


class TestSupplementMissingDates:
    """Post-processing should add dates to dateless EOL results."""

    @pytest.mark.asyncio
    async def test_adds_date_to_dateless_eol(self, httpx_mock):
        _mock_all_products(httpx_mock)
        httpx_mock.add_response(
            url=f"{BASE}/intel-processors.json", json=INTEL_PROCESSORS,
        )
        result = EOLResult(
            model=HardwareModel(
                model="Xeon Silver 4110", manufacturer="Intel", category="cpu",
            ),
            status=EOLStatus.EOL,
            eol_date=None,
            checked_at=datetime.now(),
            source_name="tech-generation",
            confidence=60,
            notes="old Xeon",
            date_source="none",
        )

        updated = await supplement_missing_dates([result])

        assert updated[0].eol_date == date(2024, 3, 1)
        assert updated[0].date_source == "community_database"
        assert "eol-date-supplemented-from-endoflife.date" in updated[0].notes

    @pytest.mark.asyncio
    async def test_preserves_status_and_source(self, httpx_mock):
        _mock_all_products(httpx_mock)
        httpx_mock.add_response(
            url=f"{BASE}/intel-processors.json", json=INTEL_PROCESSORS,
        )
        result = EOLResult(
            model=HardwareModel(
                model="Xeon Silver 4110", manufacturer="Intel", category="cpu",
            ),
            status=EOLStatus.EOL,
            eol_date=None,
            checked_at=datetime.now(),
            source_name="tech-generation",
            confidence=60,
            eol_reason=EOLReason.TECHNOLOGY_GENERATION,
            risk_category=RiskCategory.SUPPORT,
        )

        updated = await supplement_missing_dates([result])

        assert updated[0].status == EOLStatus.EOL
        assert updated[0].source_name == "tech-generation"
        assert updated[0].confidence == 60
        assert updated[0].eol_reason == EOLReason.TECHNOLOGY_GENERATION

    @pytest.mark.asyncio
    async def test_skips_active_models(self, httpx_mock):
        result = EOLResult(
            model=HardwareModel(
                model="Xeon Silver 4310", manufacturer="Intel", category="cpu",
            ),
            status=EOLStatus.ACTIVE,
            eol_date=None,
            checked_at=datetime.now(),
            source_name="vendor",
        )

        updated = await supplement_missing_dates([result])

        assert updated[0].eol_date is None
        assert updated[0].date_source == "none"

    @pytest.mark.asyncio
    async def test_skips_models_with_existing_date(self, httpx_mock):
        existing_date = date(2023, 1, 1)
        result = EOLResult(
            model=HardwareModel(
                model="Xeon Silver 4110", manufacturer="Intel", category="cpu",
            ),
            status=EOLStatus.EOL,
            eol_date=existing_date,
            checked_at=datetime.now(),
            source_name="vendor",
            date_source="manufacturer_confirmed",
        )

        updated = await supplement_missing_dates([result])

        assert updated[0].eol_date == existing_date
        assert updated[0].date_source == "manufacturer_confirmed"
