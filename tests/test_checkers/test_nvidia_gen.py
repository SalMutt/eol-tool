"""Tests for the NVIDIAChecker."""

import pytest

from eol_tool.checkers.nvidia import NVIDIAChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return NVIDIAChecker()


def _hw(model: str, manufacturer: str = "NVIDIA", category: str = "gpu") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestKepler:
    async def test_tesla_k40(self, checker):
        r = await checker.check(_hw("Tesla K40"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION
        assert "Kepler" in r.notes

    async def test_tesla_k80(self, checker):
        r = await checker.check(_hw("Tesla K80"))
        assert r.status == EOLStatus.EOL
        assert "Kepler" in r.notes


class TestMaxwell:
    async def test_tesla_m40(self, checker):
        r = await checker.check(_hw("Tesla M40"))
        assert r.status == EOLStatus.EOL
        assert "Maxwell" in r.notes

    async def test_tesla_m60(self, checker):
        r = await checker.check(_hw("Tesla M60"))
        assert r.status == EOLStatus.EOL


class TestPascal:
    async def test_tesla_p100(self, checker):
        r = await checker.check(_hw("Tesla P100"))
        assert r.status == EOLStatus.EOL
        assert "Pascal" in r.notes

    async def test_tesla_p40(self, checker):
        r = await checker.check(_hw("Tesla P40"))
        assert r.status == EOLStatus.EOL

    async def test_quadro_p6000(self, checker):
        r = await checker.check(_hw("Quadro P6000"))
        assert r.status == EOLStatus.EOL
        assert "Pascal" in r.notes

    async def test_gtx_1080(self, checker):
        r = await checker.check(_hw("GeForce GTX 1080"))
        assert r.status == EOLStatus.EOL
        assert "Pascal" in r.notes


class TestVolta:
    async def test_v100(self, checker):
        r = await checker.check(_hw("Tesla V100"))
        assert r.status == EOLStatus.EOL
        assert "Volta" in r.notes

    async def test_v100_sxm2(self, checker):
        r = await checker.check(_hw("NVIDIA V100-SXM2-32GB"))
        assert r.status == EOLStatus.EOL


class TestTuring:
    async def test_t4(self, checker):
        r = await checker.check(_hw("Tesla T4"))
        assert r.status == EOLStatus.ACTIVE
        assert "Turing" in r.notes

    async def test_quadro_rtx_8000(self, checker):
        r = await checker.check(_hw("Quadro RTX 8000"))
        assert r.status == EOLStatus.EOL
        assert "Quadro RTX Turing" in r.notes

    async def test_rtx_2080(self, checker):
        r = await checker.check(_hw("GeForce RTX 2080"))
        assert r.status == EOLStatus.EOL
        assert "Turing" in r.notes


class TestAmpere:
    async def test_a100(self, checker):
        r = await checker.check(_hw("A100"))
        assert r.status == EOLStatus.ACTIVE
        assert "Ampere" in r.notes

    async def test_a40(self, checker):
        r = await checker.check(_hw("NVIDIA A40"))
        assert r.status == EOLStatus.ACTIVE

    async def test_rtx_a6000(self, checker):
        r = await checker.check(_hw("RTX A6000"))
        assert r.status == EOLStatus.ACTIVE
        assert "Ampere" in r.notes


class TestHopper:
    async def test_h100(self, checker):
        r = await checker.check(_hw("H100"))
        assert r.status == EOLStatus.ACTIVE
        assert "Hopper" in r.notes
        assert r.confidence == 90

    async def test_h200(self, checker):
        r = await checker.check(_hw("NVIDIA H200"))
        assert r.status == EOLStatus.ACTIVE


class TestAdaLovelace:
    async def test_l40(self, checker):
        r = await checker.check(_hw("L40"))
        assert r.status == EOLStatus.ACTIVE
        assert "Ada Lovelace" in r.notes

    async def test_l4(self, checker):
        r = await checker.check(_hw("L4"))
        assert r.status == EOLStatus.ACTIVE

    async def test_rtx_4000_ada(self, checker):
        r = await checker.check(_hw("RTX 4000 ADA"))
        assert r.status == EOLStatus.ACTIVE
        assert "Ada Lovelace" in r.notes


class TestBlackwell:
    async def test_b200(self, checker):
        r = await checker.check(_hw("B200"))
        assert r.status == EOLStatus.ACTIVE
        assert "Blackwell" in r.notes

    async def test_gb200(self, checker):
        r = await checker.check(_hw("GB200"))
        assert r.status == EOLStatus.ACTIVE


class TestGeForce:
    async def test_gt_710(self, checker):
        r = await checker.check(_hw("GeForce GT 710"))
        assert r.status == EOLStatus.EOL

    async def test_rtx_3090(self, checker):
        r = await checker.check(_hw("GeForce RTX 3090"))
        assert r.status == EOLStatus.ACTIVE

    async def test_rtx_4090(self, checker):
        r = await checker.check(_hw("GeForce RTX 4090"))
        assert r.status == EOLStatus.ACTIVE


class TestRiskCategory:
    async def test_gpu_is_informational(self, checker):
        r = await checker.check(_hw("A100"))
        assert r.risk_category == RiskCategory.INFORMATIONAL


class TestNotFound:
    async def test_unknown_model(self, checker):
        r = await checker.check(_hw("ACME-Widget-9000"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.confidence == 0


class TestNormalization:
    def test_strip_nvidia_prefix(self):
        assert NVIDIAChecker._normalize("NVIDIA A100") == "A100"

    def test_uppercase(self):
        assert NVIDIAChecker._normalize("  tesla v100  ") == "TESLA V100"


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "nvidia" in checkers
        assert checkers["nvidia"] is NVIDIAChecker
