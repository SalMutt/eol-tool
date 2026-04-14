"""Tests for the MSIChecker."""

import pytest

from eol_tool.checkers.msi import MSIChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return MSIChecker()


def _hw(model: str, category: str = "server-board") -> HardwareModel:
    return HardwareModel(model=model, manufacturer="MSI", category=category)


class TestMSI:
    async def test_server_board_active(self, checker):
        r = await checker.check(_hw("MS-S1311"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 50
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_ws_board_active(self, checker):
        r = await checker.check(_hw("WS X299 PRO"))
        assert r.status == EOLStatus.ACTIVE

    async def test_any_model_active(self, checker):
        r = await checker.check(_hw("MEG X670E ACE"))
        assert r.status == EOLStatus.ACTIVE


class TestMSIRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "msi" in checkers
        assert checkers["msi"] is MSIChecker
