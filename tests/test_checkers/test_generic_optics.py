"""Tests for the GenericOpticsChecker."""

import pytest

from eol_tool.checkers.generic_optics import GenericOpticsChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return GenericOpticsChecker()


def _hw(model: str, manufacturer: str = "", category: str = "optics") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# All 28 required models — must classify as ACTIVE
# ===================================================================


class TestRequiredModelsActive:
    async def test_qsfp_sr4_40g(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_40g_univ(self, checker):
        r = await checker.check(_hw("QSFP-40G-UNIV"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_lr4_40g(self, checker):
        r = await checker.check(_hw("QSFP-LR4-40G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sfp_10g_t(self, checker):
        r = await checker.check(_hw("SFP-10G-T"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sfp_1ge_lx(self, checker):
        r = await checker.check(_hw("SFP-1GE-LX"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sfp_ge_t_l(self, checker):
        r = await checker.check(_hw("SFP-GE-T-L"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_100g_sr4(self, checker):
        r = await checker.check(_hw("QSFP-100G-SR4"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sfp_10gzr_55(self, checker):
        r = await checker.check(_hw("SFP-10GZR-55"))
        assert r.status == EOLStatus.ACTIVE

    async def test_cvr_qsfp_sfp10g(self, checker):
        r = await checker.check(_hw("CVR-QSFP-SFP10G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_40g_lr4_enc(self, checker):
        r = await checker.check(_hw("QSFP-40G-LR4-ENC"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_plr4_40g(self, checker):
        r = await checker.check(_hw("QSFP-PLR4-40G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_lr4_100g(self, checker):
        r = await checker.check(_hw("QSFP-LR4-100G"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfpp_40gbase_sr4(self, checker):
        r = await checker.check(_hw("QSFPP-40GBASE-SR4"))
        assert r.status == EOLStatus.ACTIVE

    async def test_100gbase_sr4_qsfp28(self, checker):
        r = await checker.check(_hw("100GBASE-SR4 QSFP28"))
        assert r.status == EOLStatus.ACTIVE

    async def test_10g_sfp_plus_lr(self, checker):
        r = await checker.check(_hw("10G SFP+ LR"))
        assert r.status == EOLStatus.ACTIVE

    async def test_10g_sfp_plus_sr_br(self, checker):
        r = await checker.check(_hw("10G SFP+ SR BR"))
        assert r.status == EOLStatus.ACTIVE

    async def test_10g_xfp_lr(self, checker):
        r = await checker.check(_hw("10G XFP LR"))
        assert r.status == EOLStatus.ACTIVE

    async def test_10g_xfp_sr_85(self, checker):
        r = await checker.check(_hw("10G XFP SR-85"))
        assert r.status == EOLStatus.ACTIVE

    async def test_10gbase_sr_sfp_plus_850nm(self, checker):
        r = await checker.check(_hw("10GBASE- SR SFP+ 850NM"))
        assert r.status == EOLStatus.ACTIVE

    async def test_10gbase_t_sfp_plus_copper_rj45(self, checker):
        r = await checker.check(_hw("10GBASE-T SFP+ COPPER RJ-45"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sfp_gb_ge_t(self, checker):
        r = await checker.check(_hw("SFP-GB-GE-T"))
        assert r.status == EOLStatus.ACTIVE

    async def test_sfp1g_lx_31(self, checker):
        r = await checker.check(_hw("SFP1G-LX-31"))
        assert r.status == EOLStatus.ACTIVE

    async def test_cfp_gen2_100gbase_lr4(self, checker):
        r = await checker.check(_hw("CFP-GEN2-100GBASE-LR4"))
        assert r.status == EOLStatus.ACTIVE

    async def test_c30_sfpp_10g_dw30(self, checker):
        r = await checker.check(_hw("C30 SFPP-10G-DW30"))
        assert r.status == EOLStatus.ACTIVE

    async def test_c31_sfpp_10g_dw31(self, checker):
        r = await checker.check(_hw("C31 SFPP-10G-DW31"))
        assert r.status == EOLStatus.ACTIVE

    async def test_c32_sfpp_10g_dw32(self, checker):
        r = await checker.check(_hw("C32 SFPP-10G-DW32"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_sr4_40g_ai(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G-AI"))
        assert r.status == EOLStatus.ACTIVE

    async def test_qsfp_sr4_50g_ai(self, checker):
        r = await checker.check(_hw("QSFP-SR4-50G-AI"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# NOT_FOUND — known manufacturer (vendor-specific checker handles it)
# ===================================================================


class TestKnownManufacturerReturnsNotFound:
    async def test_juniper_optic(self, checker):
        r = await checker.check(_hw("JNP-QSFP-4X10GE-SR", manufacturer="Juniper"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.notes == "has-known-manufacturer"

    async def test_hpe_branded_optic(self, checker):
        r = await checker.check(_hw("SFP-10G-SR", manufacturer="HPE"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_cisco_branded_optic(self, checker):
        r = await checker.check(_hw("QSFP-100G-LR4", manufacturer="Cisco"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# NOT_FOUND — non-optic models
# ===================================================================


class TestNonOpticReturnsNotFound:
    async def test_cpu_model(self, checker):
        r = await checker.check(_hw("XEON E5-2683V4", category="cpu"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.notes == "not-an-optic"

    async def test_memory_model(self, checker):
        r = await checker.check(_hw("HMA84GR7CJR4N", category="memory"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_switch_model(self, checker):
        r = await checker.check(_hw("EX4300-48T", category="switch"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_generic_server(self, checker):
        r = await checker.check(_hw("POWEREDGE R640", category="server"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# DWDM channel optics — notes should be "dwdm-optic-commodity"
# ===================================================================


class TestDWDMOptics:
    async def test_dw30_notes(self, checker):
        r = await checker.check(_hw("C30 SFPP-10G-DW30"))
        assert r.notes == "dwdm-optic-commodity"

    async def test_dw31_notes(self, checker):
        r = await checker.check(_hw("C31 SFPP-10G-DW31"))
        assert r.notes == "dwdm-optic-commodity"

    async def test_dw32_notes(self, checker):
        r = await checker.check(_hw("C32 SFPP-10G-DW32"))
        assert r.notes == "dwdm-optic-commodity"

    async def test_dwdm_risk_none(self, checker):
        r = await checker.check(_hw("C30 SFPP-10G-DW30"))
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Converter modules
# ===================================================================


class TestConverterModules:
    async def test_cvr_active(self, checker):
        r = await checker.check(_hw("CVR-QSFP-SFP10G"))
        assert r.status == EOLStatus.ACTIVE
        assert r.notes == "commodity-transceiver-always-available"

    async def test_cvr_is_not_dwdm(self, checker):
        r = await checker.check(_hw("CVR-QSFP-SFP10G"))
        assert r.notes != "dwdm-optic-commodity"


# ===================================================================
# Result field assertions
# ===================================================================


class TestResultFields:
    async def test_confidence_is_80(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G"))
        assert r.confidence == 80

    async def test_source_name(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G"))
        assert r.source_name == "generic-optics-classifier"

    async def test_eol_reason_none(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G"))
        assert r.eol_reason == EOLReason.NONE

    async def test_risk_category_none(self, checker):
        r = await checker.check(_hw("SFP-10G-T"))
        assert r.risk_category == RiskCategory.NONE

    async def test_standard_optic_notes(self, checker):
        r = await checker.check(_hw("SFP-10G-T"))
        assert r.notes == "commodity-transceiver-always-available"

    async def test_not_found_confidence_zero(self, checker):
        r = await checker.check(_hw("XEON E5-2683V4"))
        assert r.confidence == 0

    async def test_not_found_source_name(self, checker):
        r = await checker.check(_hw("XEON E5-2683V4"))
        assert r.source_name == "generic-optics-classifier"


# ===================================================================
# Edge cases — manufacturer variations
# ===================================================================


class TestManufacturerVariations:
    async def test_unknown_manufacturer_treated_as_generic(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G", manufacturer="unknown"))
        assert r.status == EOLStatus.ACTIVE

    async def test_generic_manufacturer_treated_as_generic(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G", manufacturer="generic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_whitespace_manufacturer_treated_as_generic(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G", manufacturer="  "))
        assert r.status == EOLStatus.ACTIVE
