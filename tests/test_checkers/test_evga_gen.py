"""Tests for the EVGAChecker."""

import pytest

from eol_tool.checkers.evga import EVGAChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return EVGAChecker()


def _hw(model: str, manufacturer: str = "EVGA", category: str = "gpu") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestGPUs:
    async def test_gtx_1080_eol(self, checker):
        r = await checker.check(_hw("EVGA GeForce GTX 1080 Ti SC2"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 90

    async def test_rtx_3090_eol(self, checker):
        r = await checker.check(_hw("EVGA GeForce RTX 3090 FTW3"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT


class TestPSU:
    async def test_supernova_active(self, checker):
        r = await checker.check(_hw("EVGA SuperNOVA 1600 G+", category="psu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL


class TestPeripherals:
    async def test_mouse_active(self, checker):
        r = await checker.check(_hw("EVGA TORQ X10", category="peripheral"))
        assert r.status == EOLStatus.ACTIVE


class TestDefault:
    async def test_unknown_defaults_eol(self, checker):
        r = await checker.check(_hw("EVGA MYSTERY-PRODUCT"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 60


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "evga" in checkers
        assert checkers["evga"] is EVGAChecker
