"""Tests for the DellChecker."""

import pytest

from eol_tool.checkers.dell import DellChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return DellChecker()


def _hw(model: str, manufacturer: str = "Dell", category: str = "server") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Model normalization
# ===================================================================


class TestNormalization:
    def test_strip_dell_prefix(self):
        assert DellChecker._normalize("DELL POWEREDGE R730XD") == "POWEREDGE R730XD"

    def test_strip_dellemc_prefix(self):
        assert DellChecker._normalize("DELLEMC 480GB KCT7J") == "KCT7J"

    def test_strip_capacity_prefix(self):
        assert DellChecker._normalize("73GB DELL W345K 15K") == "W345K 15K"

    def test_strip_config_suffix(self):
        assert DellChecker._normalize("DELL R430 W/E5-2683V4-2") == "R430"

    def test_strip_ram_suffix(self):
        assert DellChecker._normalize("DELL R630 128GB RAM 4 X 960 SSD") == "R630"

    def test_strip_bay_suffix(self):
        assert DellChecker._normalize("DELL R640 8 BAY DUAL 6230 1TB") == "R640"

    def test_bare_part_number(self):
        assert DellChecker._normalize("2C2CP") == "2C2CP"

    def test_bare_raid_card(self):
        assert DellChecker._normalize("H700") == "H700"

    def test_strip_dual_suffix(self):
        assert DellChecker._normalize("DELL POWEREDGE R630 DUAL 2695V4") == "POWEREDGE R630"

    def test_ssd_m2(self):
        assert DellChecker._normalize("960GB DELL M.2") == "M.2"


# ===================================================================
# PowerEdge servers — static lookup (no HTTP client)
# ===================================================================


class TestEOLServers:
    async def test_r730xd(self, checker):
        r = await checker.check(_hw("DELL POWEREDGE R730XD", category="chassis"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.confidence == 85
        assert "R730xd" in r.notes
        assert r.date_source == "none"

    async def test_r630_full(self, checker):
        r = await checker.check(_hw("DELL POWEREDGE R630"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 85
        assert r.date_source == "none"

    async def test_r630_with_config(self, checker):
        r = await checker.check(_hw("DELL R630 W/2683V4"))
        assert r.status == EOLStatus.EOL

    async def test_r630_with_ram(self, checker):
        r = await checker.check(_hw("DELL R630 128GB RAM 4 X 960 SSD"))
        assert r.status == EOLStatus.EOL

    async def test_r430(self, checker):
        r = await checker.check(_hw("DELL R430 W/E5-2683V4-2"))
        assert r.status == EOLStatus.EOL

    async def test_r430_bare(self, checker):
        r = await checker.check(_hw("R430 W/E5-2695V4"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# PowerEdge servers — Active / EOL Announced (static)
# ===================================================================


class TestActiveServers:
    async def test_r750(self, checker):
        r = await checker.check(_hw("DELL POWEREDGE R750"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.confidence == 85

    async def test_r650(self, checker):
        r = await checker.check(_hw("DELL R650 W/ 4309Y"))
        assert r.status == EOLStatus.ACTIVE

    async def test_r640_eol_announced(self, checker):
        r = await checker.check(_hw("DELL R640 8 BAY DUAL 6230 768GB"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert r.risk_category == RiskCategory.SUPPORT


# ===================================================================
# NICs
# ===================================================================


class TestNICs:
    async def test_broadcom_57416(self, checker):
        r = await checker.check(_hw("57416 10GB BASE-T", category="nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 85

    async def test_99gtm_x540(self, checker):
        r = await checker.check(_hw("DELL 99GTM X540 QUAD PORT NDC", category="nic"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_intel_nic_deferred(self, checker):
        r = await checker.check(_hw("INTEL I350-T2 1GBE", category="nic"))
        assert r.status == EOLStatus.NOT_FOUND
        assert "intel" in r.notes.lower()


# ===================================================================
# RAID controllers — always static, no dates
# ===================================================================


class TestRAIDControllers:
    async def test_h330_no_date(self, checker):
        r = await checker.check(_hw("DELL 4Y5H1 PERC H330 CONT CARD", category="raid-controller"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_h330_skips_api(self, httpx_mock):
        """PERC H330 should not query endoflife.date — it's not a PowerEdge."""
        async with DellChecker() as c:
            r = await c.check(_hw("DELL 4Y5H1 PERC H330 CONT CARD", category="raid-controller"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "none"
        # No HTTP requests should have been made at all for a RAID controller
        assert len(httpx_mock.get_requests()) == 0

    async def test_h755(self, checker):
        r = await checker.check(_hw("DELL H755 RAID", category="raid-controller"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sas_6ir(self, checker):
        r = await checker.check(_hw("DELL HM030 SAS 6/IR", category="raid-controller"))
        assert r.status == EOLStatus.EOL

    async def test_h310_with_part_numbers(self, checker):
        r = await checker.check(_hw("H310 (K09CJ / 0K09CJ)", category="raid-controller"))
        assert r.status == EOLStatus.EOL

    async def test_h700(self, checker):
        r = await checker.check(_hw("H700", category="raid-controller"))
        assert r.status == EOLStatus.EOL

    async def test_h710(self, checker):
        r = await checker.check(_hw("H710", category="raid-controller"))
        assert r.status == EOLStatus.EOL

    async def test_h730(self, checker):
        r = await checker.check(_hw("H730", category="raid-controller"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# Drives and SSDs
# ===================================================================


class TestDrives:
    async def test_legacy_sas_w345k(self, checker):
        r = await checker.check(_hw("73GB DELL W345K 15K", category="hdd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert "73GB" in r.notes or "W345K" in r.notes

    async def test_ssd_kct7j(self, checker):
        r = await checker.check(_hw("480GB KCT7J", category="ssd"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_generic_m2_ssd(self, checker):
        r = await checker.check(_hw("960GB DELL M.2", category="ssd"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 30


# ===================================================================
# Optics
# ===================================================================


class TestOptics:
    async def test_sfp_25gsr(self, checker):
        r = await checker.check(_hw("DELL SFP-25GSR-85", category="optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.PROCUREMENT


# ===================================================================
# Server boards
# ===================================================================


class TestServerBoards:
    async def test_2c2cp(self, checker):
        r = await checker.check(_hw("2C2CP", category="server-board"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT


# ===================================================================
# Source name
# ===================================================================


class TestSourceName:
    async def test_known_product_source(self, checker):
        r = await checker.check(_hw("DELL POWEREDGE R730XD"))
        assert r.source_name == "dell-static-lookup"

    async def test_not_found_source(self, checker):
        r = await checker.check(_hw("DELL MYSTERY-9000"))
        assert r.source_name == "dell-static-lookup"


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_dell(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "dell" in checkers
        assert checkers["dell"] is DellChecker

    def test_priority_is_35(self):
        assert DellChecker.priority == 35
