"""Tests for the ASRockChecker."""

import pytest

from eol_tool.checkers.asrock import ASRockChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return ASRockChecker()


def _hw(
    model: str, manufacturer: str = "ASRock", category: str = "motherboard"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestActive:
    async def test_b650d4u(self, checker):
        r = await checker.check(_hw("B650D4U"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 70

    async def test_b650d4u_2l2t(self, checker):
        r = await checker.check(_hw("B650D4U-2L2T/BCM"))
        assert r.status == EOLStatus.ACTIVE

    async def test_x570d4u_informational(self, checker):
        r = await checker.check(_hw("X570D4U"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_wrx90e(self, checker):
        r = await checker.check(_hw("WRX90E-SAGE SE"))
        assert r.status == EOLStatus.ACTIVE


class TestUnknown:
    async def test_unknown(self, checker):
        r = await checker.check(_hw("MYSTERY-BOARD"))
        assert r.status == EOLStatus.UNKNOWN


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "asrock" in checkers
        assert checkers["asrock"] is ASRockChecker
