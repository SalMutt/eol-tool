"""Tests for Corsair, Mushkin, ADATA, A-Tech, and Axiom checkers."""

import pytest

from eol_tool.checkers.adata import ADATAChecker
from eol_tool.checkers.atech import ATechChecker
from eol_tool.checkers.axiom import AxiomChecker
from eol_tool.checkers.corsair import CorsairChecker
from eol_tool.checkers.mushkin import MushkinChecker
from eol_tool.models import EOLStatus, HardwareModel


def _hw(model: str, manufacturer: str = "Test", category: str = "memory") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ── Corsair ────────────────────────────────────────────────────────────


@pytest.fixture
def corsair():
    return CorsairChecker()


class TestCorsair:
    async def test_ddr3_eol(self, corsair):
        r = await corsair.check(_hw("Corsair Vengeance DDR3 16GB", "Corsair"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 85

    async def test_ddr5_active(self, corsair):
        r = await corsair.check(_hw("Corsair Vengeance DDR5 32GB", "Corsair"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 90

    async def test_mp600_active(self, corsair):
        r = await corsair.check(_hw("Corsair MP600 PRO LPX 2TB", "Corsair", "ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_mp510_eol(self, corsair):
        r = await corsair.check(_hw("Corsair MP510 480GB", "Corsair", "ssd"))
        assert r.status == EOLStatus.EOL

    async def test_force_ssd_eol(self, corsair):
        r = await corsair.check(_hw("CSSD-F240GBGS", "Corsair", "ssd"))
        assert r.status == EOLStatus.EOL

    async def test_default_active(self, corsair):
        r = await corsair.check(_hw("Corsair K70 RGB", "Corsair", "peripheral"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 50

    def test_registration(self):
        from eol_tool.registry import list_checkers
        assert "corsair" in list_checkers()


# ── Mushkin ────────────────────────────────────────────────────────────


@pytest.fixture
def mushkin():
    return MushkinChecker()


class TestMushkin:
    async def test_reactor_eol(self, mushkin):
        r = await mushkin.check(_hw("Mushkin Reactor 1TB", "Mushkin", "ssd"))
        assert r.status == EOLStatus.EOL

    async def test_pilot_eol(self, mushkin):
        r = await mushkin.check(_hw("Mushkin Pilot 500GB NVMe", "Mushkin", "ssd"))
        assert r.status == EOLStatus.EOL

    async def test_pilot_e_active(self, mushkin):
        r = await mushkin.check(_hw("Mushkin Pilot-E 1TB NVMe", "Mushkin", "ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_source_active(self, mushkin):
        r = await mushkin.check(_hw("Mushkin Source 500GB", "Mushkin", "ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ddr3_eol(self, mushkin):
        r = await mushkin.check(_hw("Mushkin DDR3 8GB", "Mushkin"))
        assert r.status == EOLStatus.EOL

    async def test_default_eol(self, mushkin):
        r = await mushkin.check(_hw("Mushkin MYSTERY", "Mushkin"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 40


# ── ADATA ──────────────────────────────────────────────────────────────


@pytest.fixture
def adata():
    return ADATAChecker()


class TestADATA:
    async def test_su800_eol(self, adata):
        r = await adata.check(_hw("ADATA SU800 512GB", "ADATA", "ssd"))
        assert r.status == EOLStatus.EOL

    async def test_su650_active(self, adata):
        r = await adata.check(_hw("ADATA SU650 480GB", "ADATA", "ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sx8200_eol(self, adata):
        r = await adata.check(_hw("ADATA XPG SX8200 Pro 1TB", "ADATA", "ssd"))
        assert r.status == EOLStatus.EOL

    async def test_gammix_s70_active(self, adata):
        r = await adata.check(_hw("ADATA XPG GAMMIX S70 Blade 2TB", "ADATA", "ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ddr5_active(self, adata):
        r = await adata.check(_hw("ADATA DDR5 4800 32GB", "ADATA"))
        assert r.status == EOLStatus.ACTIVE

    async def test_default_active(self, adata):
        r = await adata.check(_hw("ADATA MYSTERY", "ADATA"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 50


# ── A-Tech ─────────────────────────────────────────────────────────────


@pytest.fixture
def atech():
    return ATechChecker()


class TestATech:
    async def test_ddr3_eol(self, atech):
        r = await atech.check(_hw("A-Tech 8GB DDR3 1600MHz", "A-Tech"))
        assert r.status == EOLStatus.EOL

    async def test_ddr4_active(self, atech):
        r = await atech.check(_hw("A-Tech 16GB DDR4 3200MHz", "A-Tech"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ddr5_active(self, atech):
        r = await atech.check(_hw("A-Tech 32GB DDR5 4800MHz", "A-Tech"))
        assert r.status == EOLStatus.ACTIVE

    async def test_default_active(self, atech):
        r = await atech.check(_hw("A-Tech 16GB ECC", "A-Tech"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 40


# ── Axiom ──────────────────────────────────────────────────────────────


@pytest.fixture
def axiom():
    return AxiomChecker()


class TestAxiom:
    async def test_ddr3_eol(self, axiom):
        r = await axiom.check(_hw("Axiom 16GB DDR3 PC3-12800", "Axiom"))
        assert r.status == EOLStatus.EOL

    async def test_ddr4_active(self, axiom):
        r = await axiom.check(_hw("Axiom 32GB DDR4 PC4-25600", "Axiom"))
        assert r.status == EOLStatus.ACTIVE

    async def test_1g_optic_eol(self, axiom):
        r = await axiom.check(_hw("Axiom 1G SFP LX", "Axiom", "optic"))
        assert r.status == EOLStatus.EOL

    async def test_10g_optic_active(self, axiom):
        r = await axiom.check(_hw("Axiom SFP+ 10G SR", "Axiom", "optic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_default_active(self, axiom):
        r = await axiom.check(_hw("Axiom AX-MYSTERY", "Axiom"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 40
