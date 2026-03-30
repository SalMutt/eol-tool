"""Tests for the OCZChecker."""

import pytest

from eol_tool.checkers.ocz import OCZChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel


@pytest.fixture
def checker():
    return OCZChecker()


def _hw(
    model: str, manufacturer: str = "OCZ", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestProducts:
    async def test_agility3_eol(self, checker):
        r = await checker.check(_hw("Agility 3 120GB"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED
        assert r.confidence == 90

    async def test_trion100_eol(self, checker):
        r = await checker.check(_hw("Trion 100 240GB"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED

    async def test_unknown_still_eol(self, checker):
        r = await checker.check(_hw("VERTEX-450"))
        assert r.status == EOLStatus.EOL


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "ocz" in checkers
        assert checkers["ocz"] is OCZChecker
