"""Tests for the SolidigmChecker."""

import pytest

from eol_tool.checkers.solidigm import SolidigmChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return SolidigmChecker()


def _hw(
    model: str, manufacturer: str = "Solidigm", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestProducts:
    async def test_p4320_eol(self, checker):
        r = await checker.check(_hw("D5-P4320 7.68TB"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 80

    async def test_p5316_active(self, checker):
        r = await checker.check(_hw("D5-P5316 15.36TB"))
        assert r.status == EOLStatus.ACTIVE

    async def test_p5430_active(self, checker):
        r = await checker.check(_hw("D5-P5430 3.84TB"))
        assert r.status == EOLStatus.ACTIVE


class TestUnknown:
    async def test_unknown(self, checker):
        r = await checker.check(_hw("MYSTERY"))
        assert r.status == EOLStatus.ACTIVE


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "solidigm" in checkers
        assert checkers["solidigm"] is SolidigmChecker
