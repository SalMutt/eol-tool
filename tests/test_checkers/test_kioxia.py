"""Tests for the KIOXIAChecker."""

import pytest

from eol_tool.checkers.kioxia import KIOXIAChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return KIOXIAChecker()


def _hw(
    model: str, manufacturer: str = "KIOXIA", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestKIOXIAActive:
    async def test_cd6_active(self, checker):
        r = await checker.check(_hw("CD6-R 3.84TB"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_cd8_active(self, checker):
        r = await checker.check(_hw("CD8 7.68TB"))
        assert r.status == EOLStatus.ACTIVE


class TestExceria:
    async def test_exceria_active(self, checker):
        r = await checker.check(_hw("Exceria Plus G3 2TB"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75
        assert "EXCERIA" in r.notes

    async def test_exceria_lowercase(self, checker):
        r = await checker.check(_hw("KIOXIA EXCERIA 1TB"))
        assert r.status == EOLStatus.ACTIVE


class TestUnknown:
    async def test_unknown(self, checker):
        r = await checker.check(_hw("KIOXIA-MYSTERY"))
        assert r.status == EOLStatus.ACTIVE


class TestRegistration:
    def test_auto_registers_for_kioxia(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "kioxia" in checkers
        assert checkers["kioxia"] is KIOXIAChecker
