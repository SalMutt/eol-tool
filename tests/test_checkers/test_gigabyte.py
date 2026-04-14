"""Tests for the GigabyteChecker."""

import pytest

from eol_tool.checkers.gigabyte import GigabyteChecker
from eol_tool.models import EOLStatus, HardwareModel


@pytest.fixture
def checker():
    return GigabyteChecker()


def _hw(
    model: str, manufacturer: str = "Gigabyte", category: str = "motherboard"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestProducts:
    async def test_mc12_le0_active(self, checker):
        r = await checker.check(_hw("MC12-LE0"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 65

    async def test_mc13_le0_active(self, checker):
        r = await checker.check(_hw("MC13-LE0"))
        assert r.status == EOLStatus.ACTIVE

    async def test_generic_ssd_active(self, checker):
        r = await checker.check(_hw("240GB GIGABYTE", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 30


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "gigabyte" in checkers
        assert checkers["gigabyte"] is GigabyteChecker
