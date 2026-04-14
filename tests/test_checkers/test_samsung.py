"""Tests for the SamsungChecker."""

import pytest

from eol_tool.checkers.samsung import SamsungChecker
from eol_tool.models import EOLStatus, HardwareModel


@pytest.fixture
def checker():
    return SamsungChecker()


def _hw(
    model: str, manufacturer: str = "Samsung", category: str = "ssd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestSSDEOL:
    async def test_pm883_eol(self, checker):
        r = await checker.check(_hw("PM883 960GB"))
        assert r.status == EOLStatus.EOL

    async def test_pm863_eol(self, checker):
        r = await checker.check(_hw("PM863A 480GB"))
        assert r.status == EOLStatus.EOL


class TestSSDActive:
    async def test_pm9a3_active(self, checker):
        r = await checker.check(_hw("PM9A3 1.92TB"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75

    async def test_pm893_active(self, checker):
        r = await checker.check(_hw("PM893 960GB"))
        assert r.status == EOLStatus.ACTIVE


class TestDRAM:
    async def test_m393a_ddr4(self, checker):
        r = await checker.check(_hw("M393A4K40DB3", category="memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 70

    async def test_m321r_ddr5(self, checker):
        r = await checker.check(_hw("M321R8GA0BB0", category="memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_m393b_ddr3_eol(self, checker):
        r = await checker.check(_hw("M393B2G70QH0", category="memory"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# New SSD rules
# ===================================================================


class TestNewSSDRules:
    async def test_840_evo_eol(self, checker):
        r = await checker.check(_hw("SAM 840 EVO 250GB"))
        assert r.status == EOLStatus.EOL
        assert "840 EVO" in r.notes

    async def test_840_ssd_eol(self, checker):
        r = await checker.check(_hw("840 SSD 120GB"))
        assert r.status == EOLStatus.EOL

    async def test_850_evo_eol(self, checker):
        r = await checker.check(_hw("850 EVO 500GB"))
        assert r.status == EOLStatus.EOL

    async def test_870_qvo_active(self, checker):
        r = await checker.check(_hw("870 QVO 1TB"))
        assert r.status == EOLStatus.ACTIVE
        assert "QVO" in r.notes

    async def test_970_evo_eol(self, checker):
        r = await checker.check(_hw("970 EVO 500GB"))
        assert r.status == EOLStatus.EOL
        assert "discontinued" in r.notes.lower()

    async def test_970_evo_plus_active(self, checker):
        r = await checker.check(_hw("970 EVO PLUS 1TB"))
        assert r.status == EOLStatus.ACTIVE

    async def test_pm983_eol(self, checker):
        r = await checker.check(_hw("PM983 1.92TB"))
        assert r.status == EOLStatus.EOL
        assert "PM9A3" in r.notes

    async def test_pm963_eol(self, checker):
        r = await checker.check(_hw("PM963 960GB"))
        assert r.status == EOLStatus.EOL

    async def test_pm981_eol(self, checker):
        r = await checker.check(_hw("PM981 512GB"))
        assert r.status == EOLStatus.EOL

    async def test_pm1653_active(self, checker):
        r = await checker.check(_hw("PM1653 3.84TB"))
        assert r.status == EOLStatus.ACTIVE
        assert "SAS" in r.notes

    async def test_883_dct_eol(self, checker):
        r = await checker.check(_hw("883 DCT 960GB"))
        assert r.status == EOLStatus.EOL

    async def test_mz7l3_active(self, checker):
        r = await checker.check(_hw("MZ7L3960HCJR-00A07"))
        assert r.status == EOLStatus.ACTIVE
        assert "PM893" in r.notes or "PM897" in r.notes

    async def test_mzql2_active(self, checker):
        r = await checker.check(_hw("MZQL23T8HCLS-00A07"))
        assert r.status == EOLStatus.ACTIVE
        assert "PM9A3" in r.notes

    async def test_sam_prefix_stripped(self, checker):
        r = await checker.check(_hw("SAM PM9A3 3.84TB"))
        assert r.status == EOLStatus.ACTIVE


class TestUnknown:
    async def test_unknown(self, checker):
        r = await checker.check(_hw("MYSTERY-SAMSUNG"))
        assert r.status == EOLStatus.UNKNOWN


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "samsung" in checkers
        assert checkers["samsung"] is SamsungChecker
