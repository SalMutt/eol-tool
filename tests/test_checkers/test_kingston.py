"""Tests for the KingstonChecker."""

import pytest

from eol_tool.checkers.kingston import KingstonChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return KingstonChecker()


def _hw(
    model: str, manufacturer: str = "Kingston", category: str = "memory"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# DDR3 memory — EOL
# ===================================================================


class TestDDR3EOL:
    async def test_kvr13_eol(self, checker):
        r = await checker.check(_hw("KVR13R9D4/16"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 70

    async def test_kvr16_eol(self, checker):
        r = await checker.check(_hw("KVR16R11D4/16"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# DDR4 server memory — ACTIVE
# ===================================================================


class TestDDR4Active:
    async def test_ksm26_active(self, checker):
        r = await checker.check(_hw("KSM26RD4/32MEI"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_ksm32_active(self, checker):
        r = await checker.check(_hw("KSM32RD4/32MEI"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ksm24_informational(self, checker):
        r = await checker.check(_hw("KSM24RS4/16MEI"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_kvr24_informational(self, checker):
        r = await checker.check(_hw("KVR24E17D8/16"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL


# ===================================================================
# DDR5 memory — ACTIVE
# ===================================================================


class TestDDR5Active:
    async def test_ksm48_active(self, checker):
        r = await checker.check(_hw("KSM48R40BD8-32"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_kvr48_active(self, checker):
        r = await checker.check(_hw("KVR48U40BS8-16"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Enterprise SSDs
# ===================================================================


class TestSSDs:
    async def test_dc600m_active(self, checker):
        r = await checker.check(_hw("DC600M 960GB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "DC600M" in r.notes

    async def test_dc500r_active(self, checker):
        r = await checker.check(_hw("DC500R 480GB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE

    async def test_skc2500_eol(self, checker):
        r = await checker.check(_hw("SKC2500M8/500G", category="ssd"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_skc3000_active(self, checker):
        r = await checker.check(_hw("SKC3000S/1024G", category="ssd"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Dell-specific KTD series
# ===================================================================


class TestKTD:
    async def test_ktd_pe424_active(self, checker):
        r = await checker.check(_hw("KTD-PE424E/16G"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL


# ===================================================================
# Unknown model
# ===================================================================


class TestUnknown:
    async def test_unknown_returns_unknown(self, checker):
        r = await checker.check(_hw("MYSTERY-MODULE-XYZ"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 50
        assert "not-classified" in r.notes


# ===================================================================
# Normalization
# ===================================================================


class TestNormalization:
    def test_strip_kingston_prefix(self):
        assert KingstonChecker._normalize("KINGSTON KSM26RD4/32MEI") == "KSM26RD4/32MEI"

    def test_strip_kng_prefix(self):
        assert KingstonChecker._normalize("KNG DC600M") == "DC600M"


# ===================================================================
# Auto-registration
# ===================================================================


# ===================================================================
# New SSD rules
# ===================================================================


class TestNewSSDs:
    async def test_a400_active(self, checker):
        r = await checker.check(_hw("KNG A400 480GB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "A400" in r.notes

    async def test_dc400_eol(self, checker):
        r = await checker.check(_hw("KNG DC400 480GB", category="ssd"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_dc450r_eol(self, checker):
        r = await checker.check(_hw("DC450R 960GB", category="ssd"))
        assert r.status == EOLStatus.EOL
        assert "DC450R" in r.notes

    async def test_dc2000b_active(self, checker):
        r = await checker.check(_hw("DC2000B 1.92TB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "DC2000B" in r.notes

    async def test_kc600_active(self, checker):
        r = await checker.check(_hw("KNG KC600 512GB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "KC600" in r.notes

    async def test_kc400_eol(self, checker):
        r = await checker.check(_hw("KC400 256GB", category="ssd"))
        assert r.status == EOLStatus.EOL

    async def test_kc3000_without_skc_prefix(self, checker):
        r = await checker.check(_hw("KNG KC3000 1TB", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "KC3000" in r.notes

    async def test_sa2000_eol(self, checker):
        r = await checker.check(_hw("SA2000M8/500G", category="ssd"))
        assert r.status == EOLStatus.EOL

    async def test_snv2s_active(self, checker):
        r = await checker.check(_hw("SNV2S/1000G", category="ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert "NV2" in r.notes

    async def test_ssdnow_v300_eol(self, checker):
        r = await checker.check(_hw("SSDNow V300 120GB", category="ssd"))
        assert r.status == EOLStatus.EOL

    async def test_v300_eol(self, checker):
        r = await checker.check(_hw("KNG V300 240GB", category="ssd"))
        assert r.status == EOLStatus.EOL


class TestRegistration:
    def test_auto_registers_for_kingston(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "kingston" in checkers
        assert checkers["kingston"] is KingstonChecker
