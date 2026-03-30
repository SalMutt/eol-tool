"""Tests for the MicronChecker."""

import pytest

from eol_tool.checkers.micron import MicronChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return MicronChecker()


def _hw(
    model: str, manufacturer: str = "Micron", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# SSD product lines — EOL
# ===================================================================


class TestSSDEOL:
    async def test_5100_eol(self, checker):
        r = await checker.check(_hw("MICRON 5100 PRO 480GB"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.confidence == 75
        assert "5100" in r.notes

    async def test_5200_eol(self, checker):
        r = await checker.check(_hw("5200 ECO 960GB"))
        assert r.status == EOLStatus.EOL

    async def test_9300_eol(self, checker):
        r = await checker.check(_hw("9300 PRO 3.84TB"))
        assert r.status == EOLStatus.EOL

    async def test_7300_eol(self, checker):
        r = await checker.check(_hw("7300 PRO 1.92TB"))
        assert r.status == EOLStatus.EOL

    async def test_m510dc_eol(self, checker):
        r = await checker.check(_hw("M510DC 480GB"))
        assert r.status == EOLStatus.EOL

    async def test_2300_eol(self, checker):
        r = await checker.check(_hw("2300 NVMe 256GB"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# SSD product lines — ACTIVE
# ===================================================================


class TestSSDActive:
    async def test_5400_active(self, checker):
        r = await checker.check(_hw("5400 PRO 960GB"))
        assert r.status == EOLStatus.ACTIVE
        assert "5400" in r.notes

    async def test_7450_active(self, checker):
        r = await checker.check(_hw("7450 PRO 1.92TB"))
        assert r.status == EOLStatus.ACTIVE

    async def test_9400_active(self, checker):
        r = await checker.check(_hw("9400 PRO 3.84TB"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# DRAM — DDR3 EOL
# ===================================================================


class TestDRAMEOL:
    async def test_ddr3_mt36ksf(self, checker):
        r = await checker.check(_hw("MT36KSF2G72PZ-1G6E1", category="memory"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.confidence == 65

    async def test_ddr3_mt18ksf(self, checker):
        r = await checker.check(_hw("MT18KSF1G72PZ-1G6E1", category="memory"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# DRAM — DDR4/DDR5 ACTIVE
# ===================================================================


class TestDRAMActive:
    async def test_ddr4_mta36asf(self, checker):
        r = await checker.check(_hw("MTA36ASF4G72PZ-2G6E1", category="memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_mem_dr516(self, checker):
        r = await checker.check(_hw("MEM-DR516L-CL01", category="memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_mem_dr416(self, checker):
        r = await checker.check(_hw("MEM-DR416L-CL06", category="memory"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Crucial-branded
# ===================================================================


class TestCrucial:
    async def test_crucial_ddr4_rfd4(self, checker):
        r = await checker.check(_hw("CT32G4RFD4266", category="memory"))
        assert r.status == EOLStatus.ACTIVE
        assert "DDR4" in r.notes

    async def test_crucial_p1_ssd_eol(self, checker):
        r = await checker.check(_hw("CT500P1SSD8"))
        assert r.status == EOLStatus.EOL
        assert "P1" in r.notes


# ===================================================================
# Unknown model
# ===================================================================


# ===================================================================
# New DRAM prefix rules
# ===================================================================


class TestNewDRAM:
    async def test_mta18asf_active(self, checker):
        r = await checker.check(_hw("MTA18ASF2G72AZ-2G6E1", category="memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_mta72ass_active(self, checker):
        r = await checker.check(_hw("MTA72ASS8G72LZ-2G6D2", category="memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_mta8atf_active(self, checker):
        r = await checker.check(_hw("MTA8ATF1G64HZ-2G3B1", category="memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_mta9asf_active(self, checker):
        r = await checker.check(_hw("MTA9ASF1G72PZ-2G3B1", category="memory"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Crucial SSD by name (CRU prefix)
# ===================================================================


class TestCrucialSSDs:
    async def test_cru_mx200_eol(self, checker):
        r = await checker.check(_hw("CRU MX200 500GB"))
        assert r.status == EOLStatus.EOL
        assert "MX200" in r.notes

    async def test_cru_mx300_eol(self, checker):
        r = await checker.check(_hw("CRU MX300 750GB"))
        assert r.status == EOLStatus.EOL
        assert "MX300" in r.notes

    async def test_cru_mx500_active(self, checker):
        r = await checker.check(_hw("CRU MX500 1TB"))
        assert r.status == EOLStatus.ACTIVE
        assert "MX500" in r.notes

    async def test_cru_bx500_active(self, checker):
        r = await checker.check(_hw("CRU BX500 240GB"))
        assert r.status == EOLStatus.ACTIVE
        assert "BX500" in r.notes

    async def test_crucial_t705_active(self, checker):
        r = await checker.check(_hw("CT2000T705SSD3"))
        assert r.status == EOLStatus.ACTIVE
        assert "T705" in r.notes

    async def test_crucial_p1_eol_via_name(self, checker):
        r = await checker.check(_hw("CRU P1 500GB"))
        assert r.status == EOLStatus.EOL
        assert "P1" in r.notes


# ===================================================================
# Unknown model
# ===================================================================


class TestUnknown:
    async def test_unknown_returns_unknown(self, checker):
        r = await checker.check(_hw("MYSTERY-MICRON-XYZ"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 50


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_micron(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "micron" in checkers
        assert checkers["micron"] is MicronChecker
