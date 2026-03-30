"""Tests for the PNYChecker."""

import pytest

from eol_tool.checkers.pny import PNYChecker
from eol_tool.models import EOLStatus, HardwareModel


@pytest.fixture
def checker():
    return PNYChecker()


def _hw(
    model: str, manufacturer: str = "PNY", category: str = "gpu"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestGPUs:
    async def test_p2200_eol(self, checker):
        r = await checker.check(_hw("P2200 VIDEO CARD"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 70

    async def test_rtx4000_active(self, checker):
        r = await checker.check(_hw("VCQRTX4000-PB"))
        assert r.status == EOLStatus.ACTIVE

    async def test_k1200_eol(self, checker):
        r = await checker.check(_hw("VCQK1200-T"))
        assert r.status == EOLStatus.EOL


class TestSSDs:
    async def test_cs900_active(self, checker):
        r = await checker.check(_hw("CS900 240GB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_cs1311_eol(self, checker):
        r = await checker.check(_hw("CS1311 120GB", category="ssd"))
        assert r.status == EOLStatus.EOL


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "pny" in checkers
        assert checkers["pny"] is PNYChecker
