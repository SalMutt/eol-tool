"""Tests for the IntelChecker."""

import pytest

from eol_tool.checkers.intel import IntelChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return IntelChecker()


def _hw(
    model: str,
    manufacturer: str = "Intel",
    category: str = "nic",
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# NIC lookups
# ===================================================================


class TestNICs:
    async def test_x520_da2_eol(self, checker):
        r = await checker.check(_hw("X520-DA2"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 80
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_x540_t2_eol(self, checker):
        r = await checker.check(_hw("X540-T2"))
        assert r.status == EOLStatus.EOL

    async def test_i350_t4_active(self, checker):
        r = await checker.check(_hw("I350-T4"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_x550_t2_active(self, checker):
        r = await checker.check(_hw("X550-T2"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_x710_bm2_active(self, checker):
        r = await checker.check(_hw("X710-BM2"))
        assert r.status == EOLStatus.ACTIVE

    async def test_x710_t4l_active(self, checker):
        r = await checker.check(_hw("X710-T4L"))
        assert r.status == EOLStatus.ACTIVE

    async def test_x722_da4_active(self, checker):
        r = await checker.check(_hw("X722-DA4"))
        assert r.status == EOLStatus.ACTIVE

    async def test_intel_prefix_stripped(self, checker):
        r = await checker.check(_hw("INTEL X520-DA2"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# SSD lookups
# ===================================================================


class TestSSDs:
    async def test_ssd_540_eol(self, checker):
        r = await checker.check(_hw("540", category="ssd"))
        assert r.status == EOLStatus.EOL
        assert "540s" in r.notes

    async def test_ssd_520_eol(self, checker):
        r = await checker.check(_hw("520", category="ssd"))
        assert r.status == EOLStatus.EOL

    async def test_ssd_660p_eol(self, checker):
        r = await checker.check(_hw("660P", category="ssd"))
        assert r.status == EOLStatus.EOL

    async def test_ssd_760p_eol(self, checker):
        r = await checker.check(_hw("760P", category="ssd"))
        assert r.status == EOLStatus.EOL

    async def test_ssd_dc_p4511_eol(self, checker):
        r = await checker.check(_hw("DC P4511", category="ssd"))
        assert r.status == EOLStatus.EOL
        assert "Solidigm" in r.notes

    async def test_ssd_520_not_matched_as_nic(self, checker):
        """520 SSD should not match X520 NIC."""
        r = await checker.check(_hw("520", category="ssd"))
        assert "SSD 520" in r.notes


# ===================================================================
# CPU models — should be deferred to tech_generation
# ===================================================================


class TestCPUs:
    async def test_cpu_returns_not_found(self, checker):
        r = await checker.check(_hw("E5-2680V4", category="cpu"))
        assert r.status == EOLStatus.NOT_FOUND
        assert "cpu" in r.notes.lower()

    async def test_xeon_cpu_not_found(self, checker):
        r = await checker.check(_hw("XEON E5-2690V3", category="cpu"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# RAID models
# ===================================================================


class TestRAID:
    async def test_res2sv240_eol(self, checker):
        r = await checker.check(_hw("RES2SV240", category="raid-controller"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert "SAS expander" in r.notes


# ===================================================================
# Unknown model
# ===================================================================


class TestUnknown:
    async def test_unknown_returns_not_found(self, checker):
        r = await checker.check(_hw("MYSTERY-WIDGET-3000"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.source_name == "intel-static-lookup"


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_intel(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "intel" in checkers
        assert checkers["intel"] is IntelChecker


# ===================================================================
# NOT_FOUND fallback chain — vendor → techgen
# ===================================================================


class TestNotFoundFallback:
    """Verify that NOT_FOUND from IntelChecker causes fallback to techgen."""

    async def test_cpu_falls_through_to_techgen(self):
        """Intel static checker returns NOT_FOUND for CPUs; techgen should
        pick them up and classify by generation."""
        from eol_tool.registry import get_checker

        cpu = _hw("XEON E5-2680V4", category="cpu")

        # Intel static checker returns NOT_FOUND for CPUs
        intel_checker = IntelChecker()
        r1 = await intel_checker.check(cpu)
        assert r1.status == EOLStatus.NOT_FOUND

        # Tech generation checker should classify this CPU
        techgen_cls = get_checker("__techgen__")
        if techgen_cls:
            tg = techgen_cls()
            async with tg:
                r2 = await tg.check(cpu)
            # E5-2680V4 is Broadwell-EP, should be EOL
            assert r2.status in (EOLStatus.EOL, EOLStatus.EOL_ANNOUNCED)
            assert r2.status != EOLStatus.NOT_FOUND
