"""Tests for the WDChecker."""

import pytest

from eol_tool.checkers.wd import WDChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return WDChecker()


def _hw(
    model: str, manufacturer: str = "WD", category: str = "hdd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Active product lines
# ===================================================================


class TestActive:
    async def test_gold_kfbx(self, checker):
        r = await checker.check(_hw("WD102KFBX"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert r.confidence == 70
        assert "Gold" in r.notes

    async def test_red_efzx(self, checker):
        r = await checker.check(_hw("WD20EFZX"))
        assert r.status == EOLStatus.ACTIVE
        assert "Red" in r.notes

    async def test_red_efrx(self, checker):
        r = await checker.check(_hw("WD40EFRX"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ezaz_active_informational(self, checker):
        r = await checker.check(_hw("WD30EZAZ"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL


# ===================================================================
# EOL product lines
# ===================================================================


class TestEOL:
    async def test_caviar_fals(self, checker):
        r = await checker.check(_hw("WD1001FALS"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_re_fyyz(self, checker):
        r = await checker.check(_hw("WD2000FYYZ"))
        assert r.status == EOLStatus.EOL
        assert "RE" in r.notes

    async def test_black_fzex(self, checker):
        r = await checker.check(_hw("WD2003FZEX"))
        assert r.status == EOLStatus.EOL
        assert "Black" in r.notes

    async def test_blue_ezex(self, checker):
        r = await checker.check(_hw("WD10EZEX"))
        assert r.status == EOLStatus.EOL

    async def test_green_aads(self, checker):
        r = await checker.check(_hw("WD5000AADS"))
        assert r.status == EOLStatus.EOL

    async def test_re_fbyx(self, checker):
        r = await checker.check(_hw("WD2003FBYX"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# Normalization
# ===================================================================


class TestNormalization:
    def test_strip_capacity_prefix(self):
        assert WDChecker._normalize("10TB WD102KFBX") == "WD102KFBX"

    def test_strip_wd_prefix(self):
        assert WDChecker._normalize("WD/ WD102KFBX") == "WD102KFBX"

    async def test_capacity_prefix_lookup(self, checker):
        r = await checker.check(_hw("10TB WD102KFBX"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Unknown model
# ===================================================================


# ===================================================================
# New suffix rules
# ===================================================================


class TestNewSuffixes:
    async def test_kryz_eol(self, checker):
        r = await checker.check(_hw("WD4000KRYZ"))
        assert r.status == EOLStatus.EOL
        assert "Gold" in r.notes

    async def test_fbyz_active(self, checker):
        r = await checker.check(_hw("WD102FBYZ"))
        assert r.status == EOLStatus.ACTIVE
        assert "Gold" in r.notes

    async def test_fyyg_eol(self, checker):
        r = await checker.check(_hw("WD2000FYYG"))
        assert r.status == EOLStatus.EOL
        assert "RE" in r.notes

    async def test_fryz_eol(self, checker):
        r = await checker.check(_hw("WD4003FRYZ"))
        assert r.status == EOLStatus.EOL
        assert "Gold" in r.notes

    async def test_azex_eol(self, checker):
        r = await checker.check(_hw("WD10AZEX"))
        assert r.status == EOLStatus.EOL
        assert "Blue" in r.notes


# ===================================================================
# WD SSD rules
# ===================================================================


class TestWDSSDs:
    async def test_wds200t2g0a_active(self, checker):
        r = await checker.check(_hw("WDS200T2G0A", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "Green" in r.notes

    async def test_wd_green_keyword(self, checker):
        r = await checker.check(_hw("WD GREEN 240GB SSD", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "Green" in r.notes


# ===================================================================
# Unknown model
# ===================================================================


class TestUnknown:
    async def test_unknown_suffix(self, checker):
        r = await checker.check(_hw("WD5000XYZQ"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 50


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_wd(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "wd" in checkers
        assert checkers["wd"] is WDChecker
