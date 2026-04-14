"""Tests for Hitachi, IBM, Adaptec, Zotac, and updated Arista/Dynatron checkers."""

import pytest

from eol_tool.checkers.adaptec import AdaptecChecker
from eol_tool.checkers.arista import AristaChecker
from eol_tool.checkers.dynatron import DynatronChecker
from eol_tool.checkers.hitachi import HitachiChecker
from eol_tool.checkers.ibm import IBMChecker
from eol_tool.checkers.zotac import ZotacChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


def _hw(
    model: str, manufacturer: str = "Test", category: str = "other",
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ── Hitachi ────────────────────────────────────────────────────────────


@pytest.fixture
def hitachi():
    return HitachiChecker()


class TestHitachi:
    async def test_ultrastar_sas_eol(self, hitachi):
        r = await hitachi.check(_hw("HUS726060ALS640", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL
        assert "Ultrastar SAS" in r.notes
        assert r.confidence == 85

    async def test_deskstar_eol(self, hitachi):
        r = await hitachi.check(_hw("HDS721010CLA332", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL
        assert "Deskstar" in r.notes

    async def test_helium_eol(self, hitachi):
        r = await hitachi.check(_hw("HUH728080ALE600", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL
        assert "Helium" in r.notes

    async def test_default_eol(self, hitachi):
        r = await hitachi.check(_hw("MYSTERY", "Hitachi"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 80

    async def test_hgst_prefix_stripped(self, hitachi):
        r = await hitachi.check(_hw("HGST HUS726060ALS640", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL

    def test_registration(self):
        from eol_tool.registry import list_checkers
        assert "hitachi" in list_checkers()

    def test_hgst_alias(self):
        from eol_tool.registry import get_checker
        assert get_checker("hgst") is not None


# ── IBM ────────────────────────────────────────────────────────────────


@pytest.fixture
def ibm():
    return IBMChecker()


class TestIBM:
    async def test_system_x_eol(self, ibm):
        r = await ibm.check(_hw("x3650 M4", "IBM", "server"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 85

    async def test_bladecenter_eol(self, ibm):
        r = await ibm.check(_hw("BladeCenter HS23", "IBM", "server"))
        assert r.status == EOLStatus.EOL

    async def test_power10_active(self, ibm):
        r = await ibm.check(_hw("Power10 S1024", "IBM", "server"))
        assert r.status == EOLStatus.ACTIVE

    async def test_power8_eol(self, ibm):
        r = await ibm.check(_hw("Power8 E850C", "IBM", "server"))
        assert r.status == EOLStatus.EOL

    async def test_switch_part_eol(self, ibm):
        r = await ibm.check(_hw("4273-E48", "IBM", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY

    async def test_default_eol(self, ibm):
        r = await ibm.check(_hw("IBM MYSTERY", "IBM"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 60


# ── Adaptec ────────────────────────────────────────────────────────────


@pytest.fixture
def adaptec():
    return AdaptecChecker()


class TestAdaptec:
    async def test_series_5_eol(self, adaptec):
        r = await adaptec.check(_hw("Adaptec 5805", "Adaptec", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 85

    async def test_series_7_eol(self, adaptec):
        r = await adaptec.check(_hw("Adaptec 71605", "Adaptec", "raid"))
        assert r.status == EOLStatus.EOL

    async def test_smartraid_active(self, adaptec):
        r = await adaptec.check(_hw("Adaptec SmartRAID 3154-8i", "Adaptec", "raid"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 80

    async def test_default_eol(self, adaptec):
        r = await adaptec.check(_hw("Adaptec MYSTERY", "Adaptec"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 60


# ── Zotac ──────────────────────────────────────────────────────────────


@pytest.fixture
def zotac():
    return ZotacChecker()


class TestZotac:
    async def test_gtx_1080_eol(self, zotac):
        r = await zotac.check(_hw("Zotac GTX 1080 Ti AMP", "Zotac", "gpu"))
        assert r.status == EOLStatus.EOL

    async def test_rtx_3060_active(self, zotac):
        r = await zotac.check(_hw("Zotac RTX 3060 Twin Edge", "Zotac", "gpu"))
        assert r.status == EOLStatus.ACTIVE

    async def test_rtx_4090_active(self, zotac):
        r = await zotac.check(_hw("Zotac RTX 4090 AMP Extreme", "Zotac", "gpu"))
        assert r.status == EOLStatus.ACTIVE

    async def test_rtx_2080_eol(self, zotac):
        r = await zotac.check(_hw("Zotac RTX 2080 Super", "Zotac", "gpu"))
        assert r.status == EOLStatus.EOL

    async def test_zbox_active(self, zotac):
        r = await zotac.check(_hw("ZBOX CI660 Nano", "Zotac", "mini_pc"))
        assert r.status == EOLStatus.ACTIVE

    async def test_default_active(self, zotac):
        r = await zotac.check(_hw("Zotac MYSTERY", "Zotac"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 40


# ── Arista (updated) ──────────────────────────────────────────────────


@pytest.fixture
def arista():
    return AristaChecker()


class TestAristaGeneration:
    async def test_7010_eol(self, arista):
        r = await arista.check(_hw("DCS-7010T-48", "Arista", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY

    async def test_7060_active(self, arista):
        r = await arista.check(_hw("DCS-7060CX2-32S", "Arista", "switch"))
        assert r.status == EOLStatus.ACTIVE

    async def test_7050cx3_active(self, arista):
        r = await arista.check(_hw("DCS-7050CX3-32S", "Arista", "switch"))
        assert r.status == EOLStatus.ACTIVE

    async def test_7050qx_eol(self, arista):
        r = await arista.check(_hw("DCS-7050QX-32S", "Arista", "switch"))
        assert r.status == EOLStatus.EOL

    async def test_7800_active(self, arista):
        r = await arista.check(_hw("DCS-7800R3-36P", "Arista", "switch"))
        assert r.status == EOLStatus.ACTIVE

    async def test_7300_active(self, arista):
        r = await arista.check(_hw("DCS-7300X3-32C", "Arista", "switch"))
        assert r.status == EOLStatus.ACTIVE


# ── Dynatron (updated) ────────────────────────────────────────────────


@pytest.fixture
def dynatron():
    return DynatronChecker()


class TestDynatronGeneration:
    async def test_lga4677_active(self, dynatron):
        r = await dynatron.check(_hw("Dynatron LGA 4677 2U", "Dynatron", "cooler"))
        assert r.status == EOLStatus.ACTIVE

    async def test_lga2011_eol(self, dynatron):
        r = await dynatron.check(_hw("Dynatron LGA 2011 1U", "Dynatron", "cooler"))
        assert r.status == EOLStatus.EOL

    async def test_sp5_active(self, dynatron):
        r = await dynatron.check(_hw("Dynatron SP5 cooler", "Dynatron", "cooler"))
        assert r.status == EOLStatus.ACTIVE

    async def test_default_active(self, dynatron):
        r = await dynatron.check(_hw("Dynatron MYSTERY", "Dynatron", "cooler"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 40
