"""Tests for the SolidigmChecker."""

import pytest

from eol_tool.checkers.solidigm import SolidigmChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return SolidigmChecker()


def _hw(model: str, manufacturer: str = "Solidigm", category: str = "ssd") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestEOLProducts:
    async def test_d5_p4320(self, checker):
        r = await checker.check(_hw("D5-P4320"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION
        assert "P4320" in r.notes

    async def test_d5_p4320_no_dash(self, checker):
        r = await checker.check(_hw("D5P4320"))
        assert r.status == EOLStatus.EOL


class TestActiveProducts:
    async def test_d7_p5510(self, checker):
        r = await checker.check(_hw("D7-P5510"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert "D7" in r.notes

    async def test_d7_p5620(self, checker):
        r = await checker.check(_hw("D7-P5620"))
        assert r.status == EOLStatus.ACTIVE

    async def test_d5_p5316(self, checker):
        r = await checker.check(_hw("D5-P5316"))
        assert r.status == EOLStatus.ACTIVE
        assert "D5-P5" in r.notes

    async def test_d5_p5430(self, checker):
        r = await checker.check(_hw("D5-P5430"))
        assert r.status == EOLStatus.ACTIVE

    async def test_synergy(self, checker):
        r = await checker.check(_hw("D7-PS1010 Synergy"))
        assert r.status == EOLStatus.ACTIVE

    async def test_p41_plus(self, checker):
        r = await checker.check(_hw("P41 Plus"))
        assert r.status == EOLStatus.ACTIVE
        assert "P41" in r.notes

    async def test_p44_pro(self, checker):
        r = await checker.check(_hw("P44 Pro"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ssdpf(self, checker):
        r = await checker.check(_hw("SSDPF2KX038TZ"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 70


class TestRiskCategory:
    async def test_ssd_is_procurement(self, checker):
        r = await checker.check(_hw("D7-P5510"))
        assert r.risk_category == RiskCategory.PROCUREMENT


class TestDefault:
    async def test_unrecognized_defaults_active(self, checker):
        r = await checker.check(_hw("SOLIDIGM-UNKNOWN"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 50


class TestNormalization:
    def test_strip_solidigm_prefix(self):
        assert SolidigmChecker._normalize("Solidigm D7-P5510") == "D7-P5510"

    def test_strip_intel_prefix(self):
        assert SolidigmChecker._normalize("Intel D5-P5316") == "D5-P5316"


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "solidigm" in checkers
        assert checkers["solidigm"] is SolidigmChecker
