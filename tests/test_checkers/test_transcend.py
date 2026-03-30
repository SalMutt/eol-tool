"""Tests for the TranscendChecker."""

import pytest

from eol_tool.checkers.transcend import TranscendChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return TranscendChecker()


def _hw(
    model: str, manufacturer: str = "Transcend", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestProducts:
    async def test_ts16g_hsd_eol(self, checker):
        r = await checker.check(_hw("TS16GHSD630"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_ts32g_hsd_eol(self, checker):
        r = await checker.check(_hw("TS32GHSD372M"))
        assert r.status == EOLStatus.EOL

    async def test_ts64g_hsd452t_active(self, checker):
        r = await checker.check(_hw("TS64GHSD452T-I"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ts64g_mts400s_eol(self, checker):
        r = await checker.check(_hw("TS64GMTS400S"))
        assert r.status == EOLStatus.EOL


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "transcend" in checkers
        assert checkers["transcend"] is TranscendChecker
