"""Tests for IntelARKChecker expansion to NICs, SSDs, and optics."""

from unittest.mock import AsyncMock, MagicMock, patch

from eol_tool.checkers.intel_ark import (
    IntelARKChecker,
    _normalize_key,
    _prepare_search_term,
    _to_result,
)
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


def _hw(model: str, category: str = "cpu", manufacturer: str = "Intel") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# NIC / SSD / optic categories pass the gate
# ===================================================================


class TestCategoryAccepted:
    async def test_nic_passes_category_gate(self):
        checker = IntelARKChecker()
        r = await checker.check(_hw("X520-DA2", category="nic"))
        assert "unsupported" not in r.notes

    async def test_ssd_passes_category_gate(self):
        checker = IntelARKChecker()
        r = await checker.check(_hw("INT S3500", category="ssd"))
        assert "unsupported" not in r.notes

    async def test_optic_passes_category_gate(self):
        checker = IntelARKChecker()
        r = await checker.check(_hw("SFP-10GSR", category="optic"))
        assert "unsupported" not in r.notes


# ===================================================================
# NIC model-to-query normalization
# ===================================================================


class TestNICNormalization:
    def test_strips_speed_port_suffix(self):
        key = _normalize_key("X520-DA2 10GB/S DUAL", "nic")
        assert key == "X520-DA2"

    def test_preserves_bare_adapter_family(self):
        key = _normalize_key("X520-DA2", "nic")
        assert key == "X520-DA2"

    def test_strips_intel_prefix(self):
        key = _normalize_key("INTEL X710-BM2", "nic")
        assert key == "X710-BM2"

    def test_i350_extraction(self):
        key = _normalize_key("I350-T4 1GB/S QUAD", "nic")
        assert key == "I350-T4"

    def test_search_term_is_adapter_family(self):
        key = _normalize_key("X520-DA2 10GB/S DUAL", "nic")
        term = _prepare_search_term(key, "nic")
        assert term == "Intel Ethernet X520-DA2"


# ===================================================================
# SSD model-to-query normalization
# ===================================================================


class TestSSDNormalization:
    def test_int_prefix_stripped_and_ssd_prepended(self):
        key = _normalize_key("INT S3500", "ssd")
        term = _prepare_search_term(key, "ssd")
        assert term == "Intel SSD S3500"

    def test_int_d3_model(self):
        key = _normalize_key("INT D3-S4510", "ssd")
        term = _prepare_search_term(key, "ssd")
        assert term == "Intel SSD D3-S4510"

    def test_bare_ssd_model(self):
        key = _normalize_key("660P", "ssd")
        term = _prepare_search_term(key, "ssd")
        assert term == "Intel SSD 660P"


# ===================================================================
# ARK result for NIC returns manufacturer_confirmed
# ===================================================================


class TestNICARKResult:
    def test_discontinued_nic_returns_manufacturer_confirmed(self):
        model = _hw("X520-DA2", category="nic")
        data = {
            "marketing_status": "Discontinued",
            "launch_date": "Q4'12",
            "eol_date": "July 1, 2021",
        }
        r = _to_result(model, data)
        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.confidence == 90
        assert r.risk_category == RiskCategory.SUPPORT

    def test_active_nic_returns_active(self):
        model = _hw("X550-T2", category="nic")
        data = {"marketing_status": "Launched", "launch_date": "Q3'15"}
        r = _to_result(model, data)
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Full check with mocked Playwright (never hits real ARK)
# ===================================================================


class TestMockedPlaywrightCheck:
    async def test_nic_check_with_mocked_playwright(self):
        checker = IntelARKChecker()
        checker._checker_disabled = False

        mock_data = {
            "marketing_status": "Discontinued",
            "launch_date": "Q4'12",
            "eol_date": "July 1, 2021",
        }

        with (
            patch.object(
                checker,
                "_playwright_lookup",
                new_callable=AsyncMock,
                return_value=mock_data,
            ),
            patch("eol_tool.checkers.intel_ark.PLAYWRIGHT_AVAILABLE", True),
            patch("eol_tool.checkers.intel_ark._init_cache_db") as mock_db,
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_db.return_value = mock_conn

            r = await checker.check(_hw("X520-DA2", category="nic"))

        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"
        assert r.source_name == "intel-ark"

    async def test_ssd_check_with_mocked_playwright(self):
        checker = IntelARKChecker()
        checker._checker_disabled = False

        mock_data = {
            "marketing_status": "Discontinued",
            "eol_date": "March 15, 2020",
        }

        with (
            patch.object(
                checker,
                "_playwright_lookup",
                new_callable=AsyncMock,
                return_value=mock_data,
            ),
            patch("eol_tool.checkers.intel_ark.PLAYWRIGHT_AVAILABLE", True),
            patch("eol_tool.checkers.intel_ark._init_cache_db") as mock_db,
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_db.return_value = mock_conn

            r = await checker.check(_hw("INT D3-S4510", category="ssd"))

        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"
        assert r.source_name == "intel-ark"
