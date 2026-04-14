"""Tests for the MellanoxChecker."""

import pytest

from eol_tool.checkers.mellanox import MellanoxChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return MellanoxChecker()


def _hw(model: str, manufacturer: str = "Mellanox", category: str = "nic") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


class TestConnectX2:
    async def test_mhqh(self, checker):
        r = await checker.check(_hw("MHQH29C-XTR"))
        assert r.status == EOLStatus.EOL
        assert "ConnectX-2" in r.notes

    async def test_mnph(self, checker):
        r = await checker.check(_hw("MNPH29D-XTR"))
        assert r.status == EOLStatus.EOL


class TestConnectX3:
    async def test_mcx311(self, checker):
        r = await checker.check(_hw("MCX311A-XCAT"))
        assert r.status == EOLStatus.EOL
        assert "ConnectX-3" in r.notes

    async def test_mcx354(self, checker):
        r = await checker.check(_hw("MCX354A-FCBT"))
        assert r.status == EOLStatus.EOL


class TestConnectX4:
    async def test_mcx4121(self, checker):
        r = await checker.check(_hw("MCX4121A-ACAT"))
        assert r.status == EOLStatus.ACTIVE
        assert "ConnectX-4" in r.notes

    async def test_mcx416(self, checker):
        r = await checker.check(_hw("MCX416A-CCAT"))
        assert r.status == EOLStatus.ACTIVE


class TestConnectX5:
    async def test_mcx512(self, checker):
        r = await checker.check(_hw("MCX512A-ACAT"))
        assert r.status == EOLStatus.ACTIVE
        assert "ConnectX-5" in r.notes

    async def test_mcx556(self, checker):
        r = await checker.check(_hw("MCX556A-EDAT"))
        assert r.status == EOLStatus.ACTIVE


class TestConnectX6:
    async def test_mcx613(self, checker):
        r = await checker.check(_hw("MCX613106A-VDAT"))
        assert r.status == EOLStatus.ACTIVE
        assert "ConnectX-6" in r.notes

    async def test_mcx653(self, checker):
        r = await checker.check(_hw("MCX653106A-HDAT"))
        assert r.status == EOLStatus.ACTIVE


class TestConnectX7:
    async def test_mcx7(self, checker):
        r = await checker.check(_hw("MCX713106AS-VEAT"))
        assert r.status == EOLStatus.ACTIVE
        assert "ConnectX-7" in r.notes
        assert r.confidence == 90


class TestBlueField:
    async def test_bluefield2(self, checker):
        r = await checker.check(_hw("MBF2M332A-AEEOT"))
        assert r.status == EOLStatus.ACTIVE
        assert "BlueField-2" in r.notes

    async def test_bluefield3(self, checker):
        r = await checker.check(_hw("MBF3M332A-AEEOT"))
        assert r.status == EOLStatus.ACTIVE
        assert "BlueField-3" in r.notes


class TestRiskCategory:
    async def test_network_card_is_security(self, checker):
        r = await checker.check(_hw("MCX512A-ACAT"))
        assert r.risk_category == RiskCategory.SECURITY


class TestDefault:
    async def test_unrecognized_model_defaults_eol(self, checker):
        r = await checker.check(_hw("SomeOldCard-123"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 40
        assert "assumed EOL" in r.notes


class TestNormalization:
    def test_strip_mellanox_prefix(self):
        assert MellanoxChecker._normalize("Mellanox MCX512A") == "MCX512A"

    def test_strip_nvidia_prefix(self):
        assert MellanoxChecker._normalize("NVIDIA MCX713106AS") == "MCX713106AS"


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "mellanox" in checkers
        assert checkers["mellanox"] is MellanoxChecker
