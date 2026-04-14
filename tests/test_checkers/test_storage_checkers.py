"""Tests for SanDisk, OCZ, Transcend, KIOXIA, and Solidigm checkers."""

import pytest

from eol_tool.checkers.ocz import OCZChecker
from eol_tool.checkers.sandisk import SanDiskChecker
from eol_tool.checkers.transcend import TranscendChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


def _hw(model: str, manufacturer: str = "Test", category: str = "ssd") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ── SanDisk ────────────────────────────────────────────────────────────


@pytest.fixture
def sandisk():
    return SanDiskChecker()


class TestSanDisk:
    async def test_cloudspeed_eol(self, sandisk):
        r = await sandisk.check(_hw("SDLF1DAR-480G", "SanDisk"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 85

    async def test_lightning_eol(self, sandisk):
        r = await sandisk.check(_hw("SDLB6HM-400G", "SanDisk"))
        assert r.status == EOLStatus.EOL

    async def test_x400_eol(self, sandisk):
        r = await sandisk.check(_hw("SanDisk X400 256GB", "SanDisk"))
        assert r.status == EOLStatus.EOL

    async def test_ultra_ii_eol(self, sandisk):
        r = await sandisk.check(_hw("SanDisk Ultra II 480GB", "SanDisk"))
        assert r.status == EOLStatus.EOL

    async def test_half_slim_eol(self, sandisk):
        r = await sandisk.check(_hw("SDSA5DK-064G Half-Slim", "SanDisk"))
        assert r.status == EOLStatus.EOL

    async def test_default_eol(self, sandisk):
        r = await sandisk.check(_hw("SanDisk MYSTERY-ENTERPRISE", "SanDisk"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 60

    def test_registration(self):
        from eol_tool.registry import list_checkers
        assert "sandisk" in list_checkers()


# ── OCZ ────────────────────────────────────────────────────────────────


@pytest.fixture
def ocz():
    return OCZChecker()


class TestOCZ:
    async def test_agility_eol(self, ocz):
        r = await ocz.check(_hw("OCZ Agility 3 120GB", "OCZ"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 90
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_trion_eol(self, ocz):
        r = await ocz.check(_hw("OCZ Trion 100 240GB", "OCZ"))
        assert r.status == EOLStatus.EOL

    async def test_any_model_eol(self, ocz):
        r = await ocz.check(_hw("OCZ ANYTHING-AT-ALL", "OCZ"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 90


# ── Transcend ──────────────────────────────────────────────────────────


@pytest.fixture
def transcend():
    return TranscendChecker()


class TestTranscend:
    async def test_ssd370_eol(self, transcend):
        r = await transcend.check(_hw("Transcend SSD370S 256GB", "Transcend"))
        assert r.status == EOLStatus.EOL

    async def test_msa370_eol(self, transcend):
        r = await transcend.check(_hw("Transcend MSA370S 128GB mSATA", "Transcend"))
        assert r.status == EOLStatus.EOL

    async def test_ssd230s_active(self, transcend):
        r = await transcend.check(_hw("Transcend SSD230S 512GB", "Transcend"))
        assert r.status == EOLStatus.ACTIVE

    async def test_mte220s_active(self, transcend):
        r = await transcend.check(_hw("Transcend MTE220S 1TB NVMe", "Transcend"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ddr3_eol(self, transcend):
        r = await transcend.check(_hw("Transcend DDR3 8GB", "Transcend", "memory"))
        assert r.status == EOLStatus.EOL

    async def test_ddr4_active(self, transcend):
        r = await transcend.check(_hw("Transcend DDR4 16GB", "Transcend", "memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_default_active(self, transcend):
        r = await transcend.check(_hw("Transcend MYSTERY", "Transcend"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 50
