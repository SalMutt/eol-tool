"""Tests for the HPEChecker."""

import pytest

from eol_tool.checkers.hpe import HPEChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return HPEChecker()


def _hw(model: str, category: str = "server") -> HardwareModel:
    return HardwareModel(model=model, manufacturer="HPE", category=category)


class TestHPEGenerationEOL:
    async def test_gen7_eol(self, checker):
        r = await checker.check(_hw("DL360 G7"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION

    async def test_gen6_eol(self, checker):
        r = await checker.check(_hw("DL380 G6"))
        assert r.status == EOLStatus.EOL

    async def test_gen8_eol(self, checker):
        r = await checker.check(_hw("DL360p Gen8"))
        assert r.status == EOLStatus.EOL
        assert "Gen8" in r.notes

    async def test_gen9_eol(self, checker):
        r = await checker.check(_hw("DL380 Gen9"))
        assert r.status == EOLStatus.EOL
        assert "Gen9" in r.notes

    async def test_gen10_eol(self, checker):
        r = await checker.check(_hw("DL360 Gen10"))
        assert r.status == EOLStatus.EOL
        assert "Gen10" in r.notes
        assert r.risk_category == RiskCategory.SUPPORT


class TestHPEGenerationActive:
    async def test_gen10_plus_active(self, checker):
        r = await checker.check(_hw("DL360 Gen10 Plus"))
        assert r.status == EOLStatus.ACTIVE
        assert "Gen10 Plus" in r.notes

    async def test_gen10p_shorthand(self, checker):
        r = await checker.check(_hw("DL380 GEN10P"))
        assert r.status == EOLStatus.ACTIVE

    async def test_gen11_active(self, checker):
        r = await checker.check(_hw("DL380 Gen11"))
        assert r.status == EOLStatus.ACTIVE
        assert "Gen11" in r.notes

    async def test_gen11_dl380a(self, checker):
        r = await checker.check(_hw("DL380a Gen11"))
        assert r.status == EOLStatus.ACTIVE


class TestHPEFallbacks:
    async def test_proliant_no_gen_eol(self, checker):
        r = await checker.check(_hw("ProLiant DL360"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 40

    async def test_unknown_model(self, checker):
        r = await checker.check(_hw("StorageWorks X1600"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 30


class TestHPERegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "hpe" in checkers
        assert checkers["hpe"] is HPEChecker
