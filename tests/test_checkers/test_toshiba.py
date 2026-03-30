"""Tests for the ToshibaChecker."""

import pytest

from eol_tool.checkers.toshiba import ToshibaChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return ToshibaChecker()


def _hw(
    model: str, manufacturer: str = "Toshiba", category: str = "hdd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestMGEOL:
    async def test_mg04_eol(self, checker):
        r = await checker.check(_hw("TOS MG04ACA400E"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 70

    async def test_mg06_eol(self, checker):
        r = await checker.check(_hw("TOS MG06ACA10TE"))
        assert r.status == EOLStatus.EOL

    async def test_mg07_eol(self, checker):
        r = await checker.check(_hw("TOS MG07ACA12TE"))
        assert r.status == EOLStatus.EOL


class TestMGActive:
    async def test_mg08_informational(self, checker):
        r = await checker.check(_hw("TOS MG08ACA16TE"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_mg09_active(self, checker):
        r = await checker.check(_hw("MG09ACA18TE"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_mg10_active(self, checker):
        r = await checker.check(_hw("MG10ADA20TE"))
        assert r.status == EOLStatus.ACTIVE


class TestOtherModels:
    async def test_md06_eol(self, checker):
        r = await checker.check(_hw("MD06ACA800"))
        assert r.status == EOLStatus.EOL

    async def test_thnsnh_ssd_eol(self, checker):
        r = await checker.check(_hw("THNSNH128GBST", category="ssd"))
        assert r.status == EOLStatus.EOL


class TestUnknown:
    async def test_unknown(self, checker):
        r = await checker.check(_hw("TOSHIBA-MYSTERY"))
        assert r.status == EOLStatus.UNKNOWN


class TestRegistration:
    def test_auto_registers_for_toshiba(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "toshiba" in checkers
        assert checkers["toshiba"] is ToshibaChecker
