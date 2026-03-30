"""Tests for the endoflife.date fallback checker."""

import json
from datetime import date
from pathlib import Path

import pytest

from eol_tool.checkers.endoflife_date import EndOfLifeDateChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory

FIXTURES = Path(__file__).parent.parent / "fixtures" / "endoflife_date"


def load_fixture(name: str) -> list:
    return json.loads((FIXTURES / name).read_text())


ALL_PRODUCTS = load_fixture("all_products.json")
INTEL_PROCESSORS = load_fixture("intel_processors.json")

BASE = "https://endoflife.date/api"


def _mock_all_products(httpx_mock, is_reusable=False):
    httpx_mock.add_response(url=f"{BASE}/all.json", json=ALL_PRODUCTS, is_reusable=is_reusable)


class TestIntelCpuMatch:
    """Intel CPUs should match intel-processors and get dates."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)
        httpx_mock.add_response(url=f"{BASE}/intel-processors.json", json=INTEL_PROCESSORS)

    @pytest.mark.asyncio
    async def test_xeon_e5_v4_is_eol(self, httpx_mock):
        model = HardwareModel(
            model="E5-2683 V4",
            manufacturer="Intel",
            category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2022, 6, 30)
        assert result.confidence == 70
        assert "intel-processors" in result.source_url
        assert result.source_name == "endoflife.date"
        assert result.eol_reason == EOLReason.COMMUNITY_DATA
        assert result.risk_category == RiskCategory.SUPPORT
        assert result.date_source == "community_database"

    @pytest.mark.asyncio
    async def test_xeon_e5_v3_is_eol(self, httpx_mock):
        model = HardwareModel(
            model="E5-2680 V3",
            manufacturer="Intel",
            category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.EOL
        assert result.eol_date == date(2021, 12, 31)
        assert result.confidence == 70
        assert result.eol_reason == EOLReason.COMMUNITY_DATA
        assert result.risk_category == RiskCategory.SUPPORT
        assert result.date_source == "community_database"


class TestIntelNicNoMatch:
    """Intel NICs must NOT match intel-processors."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)

    @pytest.mark.asyncio
    async def test_intel_nic_returns_not_found(self, httpx_mock):
        model = HardwareModel(
            model="X710-DA2",
            manufacturer="Intel",
            category="nic",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.NOT_FOUND
        assert result.confidence == 0
        assert result.eol_reason == EOLReason.COMMUNITY_DATA

    @pytest.mark.asyncio
    async def test_intel_ssd_returns_not_found(self, httpx_mock):
        model = HardwareModel(
            model="D3-S4510",
            manufacturer="Intel",
            category="ssd",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.NOT_FOUND
        assert result.confidence == 0


class TestUnknownProduct:
    """Unknown manufacturer/product should return NOT_FOUND."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)

    @pytest.mark.asyncio
    async def test_unknown_manufacturer(self, httpx_mock):
        model = HardwareModel(
            model="Widget-3000",
            manufacturer="AcmeCorp",
            category="widget",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.NOT_FOUND
        assert result.confidence == 0
        assert result.eol_reason == EOLReason.COMMUNITY_DATA
        assert result.risk_category == RiskCategory.INFORMATIONAL


class TestNoSlugMapping:
    """Categories explicitly mapped to None should return NOT_FOUND."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)

    @pytest.mark.asyncio
    async def test_juniper_switch_returns_not_found(self, httpx_mock):
        model = HardwareModel(
            model="EX4300-48T",
            manufacturer="Juniper",
            category="switch",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.NOT_FOUND
        assert result.confidence == 0
        assert result.eol_reason == EOLReason.COMMUNITY_DATA
        assert result.risk_category == RiskCategory.SECURITY

    @pytest.mark.asyncio
    async def test_amd_cpu_returns_not_found(self, httpx_mock):
        model = HardwareModel(
            model="EPYC 7543",
            manufacturer="AMD",
            category="cpu",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.NOT_FOUND
        assert result.confidence == 0


class TestDellPowerEdge:
    """Dell PowerEdge should return NOT_FOUND (dell-poweredge slug removed upstream)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, httpx_mock):
        _mock_all_products(httpx_mock)

    @pytest.mark.asyncio
    async def test_r740_returns_not_found(self, httpx_mock):
        model = HardwareModel(
            model="PowerEdge R740",
            manufacturer="Dell",
            category="server",
        )
        async with EndOfLifeDateChecker() as checker:
            result = await checker.check(model)

        assert result.status == EOLStatus.NOT_FOUND
        assert result.confidence == 0
        assert result.eol_reason == EOLReason.COMMUNITY_DATA
        assert result.risk_category == RiskCategory.SUPPORT


class TestStatusDetermination:
    """Test the _determine_status logic."""

    def test_eol_false_is_active(self):
        checker = EndOfLifeDateChecker()
        status, eol_date = checker._determine_status({"eol": False})
        assert status == EOLStatus.ACTIVE
        assert eol_date is None

    def test_eol_past_date_is_eol(self):
        checker = EndOfLifeDateChecker()
        status, eol_date = checker._determine_status({"eol": "2020-01-01"})
        assert status == EOLStatus.EOL
        assert eol_date == date(2020, 1, 1)

    def test_eol_future_date_is_announced(self):
        checker = EndOfLifeDateChecker()
        status, eol_date = checker._determine_status({"eol": "2099-12-31"})
        assert status == EOLStatus.EOL_ANNOUNCED
        assert eol_date == date(2099, 12, 31)

    def test_eol_true_is_eol(self):
        checker = EndOfLifeDateChecker()
        status, eol_date = checker._determine_status({"eol": True})
        assert status == EOLStatus.EOL
        assert eol_date is None


class TestRateLimiting:
    """Rate limiting should not exceed 10 concurrent requests."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        checker = EndOfLifeDateChecker()
        assert checker._semaphore._value == 10

    @pytest.mark.asyncio
    async def test_batch_respects_rate_limit(self, httpx_mock):
        _mock_all_products(httpx_mock, is_reusable=True)
        httpx_mock.add_response(
            url=f"{BASE}/intel-processors.json", json=INTEL_PROCESSORS, is_reusable=True
        )

        models = [
            HardwareModel(
                model=f"E5-26{80 + i} V4",
                manufacturer="Intel",
                category="cpu",
            )
            for i in range(15)
        ]

        async with EndOfLifeDateChecker() as checker:
            results = await checker.check_batch(models)

        assert len(results) == 15


class TestRiskCategoryMapping:
    """Test risk category assignment based on hardware category."""

    def test_switch_is_security(self):
        assert EndOfLifeDateChecker._risk_for_category("switch") == RiskCategory.SECURITY

    def test_firewall_is_security(self):
        assert EndOfLifeDateChecker._risk_for_category("firewall") == RiskCategory.SECURITY

    def test_network_device_is_security(self):
        assert EndOfLifeDateChecker._risk_for_category("network-device") == RiskCategory.SECURITY

    def test_cpu_is_support(self):
        assert EndOfLifeDateChecker._risk_for_category("cpu") == RiskCategory.SUPPORT

    def test_server_board_is_support(self):
        assert EndOfLifeDateChecker._risk_for_category("server-board") == RiskCategory.SUPPORT

    def test_server_is_support(self):
        assert EndOfLifeDateChecker._risk_for_category("server") == RiskCategory.SUPPORT

    def test_memory_is_procurement(self):
        assert EndOfLifeDateChecker._risk_for_category("memory") == RiskCategory.PROCUREMENT

    def test_ssd_is_procurement(self):
        assert EndOfLifeDateChecker._risk_for_category("ssd") == RiskCategory.PROCUREMENT

    def test_hdd_is_procurement(self):
        assert EndOfLifeDateChecker._risk_for_category("hdd") == RiskCategory.PROCUREMENT

    def test_drive_is_procurement(self):
        assert EndOfLifeDateChecker._risk_for_category("drive") == RiskCategory.PROCUREMENT

    def test_unknown_is_informational(self):
        assert EndOfLifeDateChecker._risk_for_category("widget") == RiskCategory.INFORMATIONAL

    def test_gpu_is_informational(self):
        assert EndOfLifeDateChecker._risk_for_category("gpu") == RiskCategory.INFORMATIONAL


class TestRegistration:
    """The checker should register with manufacturer_name '__fallback__'."""

    def test_manufacturer_name(self):
        assert EndOfLifeDateChecker.manufacturer_name == "__fallback__"

    def test_registered_in_registry(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "__fallback__" in checkers
        assert checkers["__fallback__"] is EndOfLifeDateChecker
