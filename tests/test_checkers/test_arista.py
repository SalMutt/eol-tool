"""Tests for the Arista EOL checker."""

import pytest

from eol_tool.checkers.arista import AristaChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


def _hw(model: str) -> HardwareModel:
    return HardwareModel(model=model, manufacturer="Arista", category="switch")


@pytest.fixture
async def checker():
    c = AristaChecker()
    async with c:
        yield c


class TestAristaChecker:
    async def test_7050qx_32_eol(self, checker):
        r = await checker.check(_hw("7050QX-32"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert "7050QX-32" in r.notes
        assert r.confidence == 80

    async def test_7050s_64_eol(self, checker):
        r = await checker.check(_hw("7050S-64"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert "7050S-64" in r.notes

    async def test_qsfp_100g_sr4_active(self, checker):
        r = await checker.check(_hw("QSFP-100G-SR4"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "100G-SR4" in r.notes

    async def test_qsfp_40g_active(self, checker):
        r = await checker.check(_hw("QSFP-40G"))
        assert r.status == EOLStatus.ACTIVE
        assert "40G-optic" in r.notes

    async def test_40g_qsfp_plus_active(self, checker):
        r = await checker.check(_hw("40G QSFP+"))
        assert r.status == EOLStatus.ACTIVE
        assert "40G-optic" in r.notes

    async def test_sfp_10g_lr_active(self, checker):
        r = await checker.check(_hw("SFP-10GLR-31"))
        assert r.status == EOLStatus.ACTIVE
        assert "10G-LR" in r.notes

    async def test_sfp_25g_sr_active(self, checker):
        r = await checker.check(_hw("SFP-25GSR-85"))
        assert r.status == EOLStatus.ACTIVE
        assert "25G-SR" in r.notes

    async def test_unknown_model(self, checker):
        r = await checker.check(_hw("UNKNOWN-9999"))
        assert r.status == EOLStatus.UNKNOWN
        assert "arista-model-not-classified" in r.notes

    async def test_case_insensitive(self, checker):
        r = await checker.check(_hw("qsfp-100g-sr4"))
        assert r.status == EOLStatus.ACTIVE
