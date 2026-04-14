"""Tests for the ChenbroChecker."""

import pytest

from eol_tool.checkers.chenbro import ChenbroChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return ChenbroChecker()


def _hw(model: str, category: str = "chassis") -> HardwareModel:
    return HardwareModel(model=model, manufacturer="Chenbro", category=category)


class TestChenbroChassis:
    async def test_rb_chassis_active(self, checker):
        r = await checker.check(_hw("RB23812"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 70
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "passive hardware" in r.notes

    async def test_rm_chassis_active(self, checker):
        r = await checker.check(_hw("RM133"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_rm232_active(self, checker):
        r = await checker.check(_hw("RM232"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 70


class TestChenbroDefault:
    async def test_unknown_defaults_active(self, checker):
        r = await checker.check(_hw("SR107"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 60
        assert r.risk_category == RiskCategory.INFORMATIONAL


class TestChenbroRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "chenbro" in checkers
        assert checkers["chenbro"] is ChenbroChecker
