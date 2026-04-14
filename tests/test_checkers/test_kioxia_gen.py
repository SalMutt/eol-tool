"""Tests for the KIOXIAChecker."""

import pytest

from eol_tool.checkers.kioxia import KIOXIAChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return KIOXIAChecker()


def _hw(model: str, manufacturer: str = "KIOXIA", category: str = "ssd") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestEOLProducts:
    async def test_cd5(self, checker):
        r = await checker.check(_hw("KCD51LUG960G"))
        assert r.status == EOLStatus.EOL
        assert "CD5" in r.notes
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION

    async def test_cm5(self, checker):
        r = await checker.check(_hw("KCM51VUG1T60"))
        assert r.status == EOLStatus.EOL
        assert "CM5" in r.notes

    async def test_pm5(self, checker):
        r = await checker.check(_hw("KPM51RUG960G"))
        assert r.status == EOLStatus.EOL
        assert "PM5" in r.notes

    async def test_xd5(self, checker):
        r = await checker.check(_hw("KXD51LN11T92"))
        assert r.status == EOLStatus.EOL
        assert "XD5" in r.notes

    async def test_xg6(self, checker):
        r = await checker.check(_hw("KXG60ZNV512G"))
        assert r.status == EOLStatus.EOL
        assert "XG6" in r.notes

    async def test_bg4(self, checker):
        r = await checker.check(_hw("KBG40ZNS256G"))
        assert r.status == EOLStatus.EOL
        assert "BG4" in r.notes


class TestActiveProducts:
    async def test_cd6(self, checker):
        r = await checker.check(_hw("KCD61LUL3T84"))
        assert r.status == EOLStatus.ACTIVE
        assert "CD6" in r.notes

    async def test_cd7(self, checker):
        r = await checker.check(_hw("KCD71LUG7T68"))
        assert r.status == EOLStatus.ACTIVE

    async def test_cm6(self, checker):
        r = await checker.check(_hw("KCM61RUL3T84"))
        assert r.status == EOLStatus.ACTIVE

    async def test_cm7(self, checker):
        r = await checker.check(_hw("KCM71RUL3T84"))
        assert r.status == EOLStatus.ACTIVE

    async def test_pm6(self, checker):
        r = await checker.check(_hw("KPM61RUG3T84"))
        assert r.status == EOLStatus.ACTIVE
        assert "PM6" in r.notes

    async def test_pm7(self, checker):
        r = await checker.check(_hw("KPM71RUG3T84"))
        assert r.status == EOLStatus.ACTIVE

    async def test_xg8(self, checker):
        r = await checker.check(_hw("KXG80ZNV512G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_bg5(self, checker):
        r = await checker.check(_hw("KBG50ZNS512G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_hk6(self, checker):
        r = await checker.check(_hw("KHK61RSE960G"))
        assert r.status == EOLStatus.ACTIVE
        assert "HK6" in r.notes

    async def test_exceria(self, checker):
        r = await checker.check(_hw("EXCERIA PLUS G3"))
        assert r.status == EOLStatus.ACTIVE
        assert "EXCERIA" in r.notes


class TestRiskCategory:
    async def test_ssd_is_procurement(self, checker):
        r = await checker.check(_hw("KCD61LUL3T84"))
        assert r.risk_category == RiskCategory.PROCUREMENT


class TestDefault:
    async def test_unrecognized_defaults_active(self, checker):
        r = await checker.check(_hw("KIOXIA-UNKNOWN-MODEL"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 40


class TestNormalization:
    def test_strip_kioxia_prefix(self):
        assert KIOXIAChecker._normalize("KIOXIA KCD61LUL") == "KCD61LUL"

    def test_strip_toshiba_prefix(self):
        assert KIOXIAChecker._normalize("Toshiba KXG60ZNV") == "KXG60ZNV"


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "kioxia" in checkers
        assert checkers["kioxia"] is KIOXIAChecker
