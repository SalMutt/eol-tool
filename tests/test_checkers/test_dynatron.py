"""Tests for the DynatronChecker."""

import pytest

from eol_tool.checkers.dynatron import DynatronChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


def _hw(model: str) -> HardwareModel:
    return HardwareModel(model=model, manufacturer="Dynatron", category="cooling")


@pytest.fixture
def checker():
    return DynatronChecker()


class TestAMDSP3SP5Active:
    async def test_a42(self, checker):
        r = await checker.check(_hw("A42"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.confidence == 75
        assert "SP3/SP5" in r.notes

    async def test_a43(self, checker):
        r = await checker.check(_hw("A43"))
        assert r.status == EOLStatus.ACTIVE

    async def test_a45(self, checker):
        r = await checker.check(_hw("A45"))
        assert r.status == EOLStatus.ACTIVE

    async def test_a46(self, checker):
        r = await checker.check(_hw("A46"))
        assert r.status == EOLStatus.ACTIVE

    async def test_a47(self, checker):
        r = await checker.check(_hw("A47"))
        assert r.status == EOLStatus.ACTIVE

    async def test_a54_heatsink_suffix(self, checker):
        r = await checker.check(_hw("A54 HEATSINK"))
        assert r.status == EOLStatus.ACTIVE
        assert "SP3/SP5" in r.notes


class TestAMDAM4Active:
    async def test_a18_with_fan_prefix(self, checker):
        r = await checker.check(_hw("FAN A18 AMD"))
        assert r.status == EOLStatus.ACTIVE
        assert "AM4" in r.notes

    async def test_a24(self, checker):
        r = await checker.check(_hw("FAN A24 AMD"))
        assert r.status == EOLStatus.ACTIVE

    async def test_a37(self, checker):
        r = await checker.check(_hw("FAN A37"))
        assert r.status == EOLStatus.ACTIVE


class TestIntelActive:
    async def test_b12_lga4189(self, checker):
        r = await checker.check(_hw("B12"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "LGA4189" in r.notes

    async def test_s2_lga4677(self, checker):
        r = await checker.check(_hw("S2"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "LGA4677" in r.notes


class TestLegacyEOL:
    async def test_j2(self, checker):
        r = await checker.check(_hw("J2"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION
        assert "LGA2011" in r.notes

    async def test_j7_heatsink(self, checker):
        r = await checker.check(_hw("J7 HEATSINK"))
        assert r.status == EOLStatus.EOL

    async def test_j13(self, checker):
        r = await checker.check(_hw("J13"))
        assert r.status == EOLStatus.EOL

    async def test_k129_passive(self, checker):
        r = await checker.check(_hw("K129 PASSIVE"))
        assert r.status == EOLStatus.EOL
        assert "LGA1151" in r.notes

    async def test_k199_hsf(self, checker):
        r = await checker.check(_hw("K199 HSF"))
        assert r.status == EOLStatus.EOL

    async def test_q8(self, checker):
        r = await checker.check(_hw("Q8 HEATISNK"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT


class TestDynatronPrefixStripping:
    async def test_strip_dynatron_prefix(self, checker):
        r = await checker.check(_hw("DYNATRON A42"))
        assert r.status == EOLStatus.ACTIVE


class TestUnknown:
    async def test_unknown(self, checker):
        r = await checker.check(_hw("ZZZZZ-MYSTERY"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 40


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "dynatron" in checkers
        assert checkers["dynatron"] is DynatronChecker
