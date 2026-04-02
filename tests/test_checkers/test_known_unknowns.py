"""Tests for previously-unknown hardware models that should now be classified.

Every model listed here was returning UNKNOWN or NOT_FOUND before the
corresponding tech_generation rules were added. Each test verifies that the
model is now classified with the correct status, risk, and reason.
"""

import pytest

from eol_tool.checkers.tech_generation import TechGenerationChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return TechGenerationChecker()


def _hw(model: str, manufacturer: str = "", category: str = "") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# ASUS server barebones — platform generation classification
# ===================================================================


class TestASUSServerPlatforms:
    async def test_rs700_e9_eol(self, checker):
        r = await checker.check(_hw("RS700-E9-RS12", "ASUS", "server"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION

    async def test_rs700_e10_active(self, checker):
        r = await checker.check(_hw("RS700-E10-RS12", "ASUS", "server"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_rs520a_e12_active(self, checker):
        r = await checker.check(_hw("RS520A-E12-RS12", "ASUS", "server"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_rs300_e11_active(self, checker):
        r = await checker.check(_hw("RS300-E11-RS1", "ASUS", "server"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# IBM RAID controllers and switches
# ===================================================================


class TestIBMComponents:
    async def test_serveraid_m5014(self, checker):
        r = await checker.check(_hw("M5014", "IBM", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_serveraid_m5015(self, checker):
        r = await checker.check(_hw("M5015", "IBM", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_serveraid_m5210(self, checker):
        r = await checker.check(_hw("M5210", "IBM", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_serveraid_battery_46c9111(self, checker):
        r = await checker.check(_hw("46C9111", "IBM", "accessory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_rackswitch_4273_e48(self, checker):
        r = await checker.check(_hw("4273-E48", "IBM", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED


# ===================================================================
# NVIDIA professional GPUs (PNY Quadro part numbers)
# ===================================================================


class TestNVIDIAProfessionalGPU:
    async def test_vcqp1000_pascal(self, checker):
        r = await checker.check(_hw("VCQP1000-PB", "PNY", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION

    async def test_vcqrtx4000_turing(self, checker):
        r = await checker.check(_hw("VCQRTX4000-PB", "PNY", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION


# ===================================================================
# Zotac GPUs
# ===================================================================


class TestZotacGPU:
    async def test_zotac_gtx_1080_ti(self, checker):
        r = await checker.check(_hw("ZT-P10810B-10P", "Zotac", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION


# ===================================================================
# Hitachi HDDs (vendor acquired by WD)
# ===================================================================


class TestHitachiHDD:
    async def test_ultrastar_0f10381(self, checker):
        r = await checker.check(_hw("0F10381", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED
        assert "western-digital" in r.notes

    async def test_ultrastar_0f12470(self, checker):
        r = await checker.check(_hw("0F12470", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED


# ===================================================================
# Adaptec RAID controllers
# ===================================================================


class TestAdaptecRAID:
    async def test_asr_6405e(self, checker):
        r = await checker.check(_hw("ASR-6405E", "Adaptec", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_asr_71605(self, checker):
        r = await checker.check(_hw("ASR-71605", "Adaptec", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_asr_8805(self, checker):
        r = await checker.check(_hw("ASR-8805", "Adaptec", "raid"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED


# ===================================================================
# ASRock Rack motherboards
# ===================================================================


class TestASRockRack:
    async def test_s8016agm2nr_siena(self, checker):
        r = await checker.check(_hw("S8016AGM2NR", "ASRock", "motherboard"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# PNY GeForce GPUs
# ===================================================================


class TestPNYGeForce:
    async def test_vcg_gtx_1080_ti(self, checker):
        r = await checker.check(_hw("VCGGTX1080T11-CG2-BLK", "PNY", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION


# ===================================================================
# Corsair DDR5 memory
# ===================================================================


class TestCorsairDDR5:
    async def test_cmk_vengeance_ddr5(self, checker):
        r = await checker.check(_hw("CMK32GX5M2B5600C36", "Corsair", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_corsair_ddr5_keyword(self, checker):
        r = await checker.check(_hw("Corsair Vengeance DDR5-5600 32GB", "Corsair", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Kingston unusual parts
# ===================================================================


class TestKingstonParts:
    async def test_kth_ddr3_server_memory(self, checker):
        r = await checker.check(_hw("KTH-PL316/16G", "Kingston", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_kingston_sa400_ssd(self, checker):
        r = await checker.check(_hw("SA400S37/480G", "Kingston", "ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# HPE legacy components
# ===================================================================


class TestHPEComponents:
    async def test_hpe_sfp_optic_active(self, checker):
        r = await checker.check(_hw("HPE-SFP-10G-SR", "HPE", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_hpe_legacy_drive(self, checker):
        r = await checker.check(_hw("MB2000GCWD7", "HPE", "hdd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED


# ===================================================================
# Verify nothing returns UNKNOWN or NOT_FOUND
# ===================================================================


class TestNoUnknowns:
    """Every model in this file must resolve to EOL or ACTIVE — never UNKNOWN/NOT_FOUND."""

    _MODELS = [
        ("RS700-E9-RS12", "ASUS"),
        ("RS700-E10-RS12", "ASUS"),
        ("RS520A-E12-RS12", "ASUS"),
        ("RS300-E11-RS1", "ASUS"),
        ("M5014", "IBM"),
        ("M5015", "IBM"),
        ("M5210", "IBM"),
        ("46C9111", "IBM"),
        ("4273-E48", "IBM"),
        ("VCQP1000-PB", "PNY"),
        ("VCQRTX4000-PB", "PNY"),
        ("ZT-P10810B-10P", "Zotac"),
        ("0F10381", "Hitachi"),
        ("0F12470", "Hitachi"),
        ("ASR-6405E", "Adaptec"),
        ("ASR-71605", "Adaptec"),
        ("ASR-8805", "Adaptec"),
        ("S8016AGM2NR", "ASRock"),
        ("VCGGTX1080T11-CG2-BLK", "PNY"),
        ("CMK32GX5M2B5600C36", "Corsair"),
        ("KTH-PL316/16G", "Kingston"),
        ("SA400S37/480G", "Kingston"),
        ("HPE-SFP-10G-SR", "HPE"),
        ("MB2000GCWD7", "HPE"),
    ]

    @pytest.mark.parametrize("model,manufacturer", _MODELS)
    async def test_not_unknown_or_not_found(self, checker, model, manufacturer):
        r = await checker.check(_hw(model, manufacturer))
        assert r.status not in (EOLStatus.UNKNOWN, EOLStatus.NOT_FOUND), (
            f"{manufacturer} {model} returned {r.status.value}"
        )
