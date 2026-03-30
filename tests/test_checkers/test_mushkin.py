"""Tests for the MushkinChecker."""

import pytest

from eol_tool.checkers.mushkin import MushkinChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel


@pytest.fixture
def checker():
    return MushkinChecker()


def _hw(
    model: str, manufacturer: str = "Mushkin", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestProducts:
    async def test_chronos_eol(self, checker):
        r = await checker.check(_hw("Chronos 120GB"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.confidence == 70

    async def test_unknown(self, checker):
        r = await checker.check(_hw("MYSTERY"))
        assert r.status == EOLStatus.UNKNOWN


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "mushkin" in checkers
        assert checkers["mushkin"] is MushkinChecker
