"""Tests for the SeagateChecker."""

import pytest

from eol_tool.checkers.seagate import (
    SeagateChecker,
    _classify_by_product_line,
    _extract_capacity_tb,
)
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return SeagateChecker()


def _hw(
    model: str, manufacturer: str = "Seagate", category: str = "hdd"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Capacity extraction
# ===================================================================


class TestCapacityExtraction:
    def test_tb_integer(self):
        assert _extract_capacity_tb("10TB SEAGATE ENT - 0016") == 10.0

    def test_tb_decimal(self):
        assert _extract_capacity_tb("1.2TB SEAGATE ENT - M0009") == 1.2

    def test_gb(self):
        assert _extract_capacity_tb("300GB SEAGATE ENT") == 0.3

    def test_no_capacity(self):
        assert _extract_capacity_tb("SEAGATE ENT - MYSTERY") is None


# ===================================================================
# Small capacity drives — EOL
# ===================================================================


class TestSmallCapacityEOL:
    async def test_300gb_eol(self, checker):
        r = await checker.check(_hw("300GB SEAGATE ENT"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.confidence == 65

    async def test_900gb_eol(self, checker):
        r = await checker.check(_hw("900GB SEAGATE ENT - ST900MM0168"))
        assert r.status == EOLStatus.EOL

    async def test_1_2tb_eol(self, checker):
        r = await checker.check(_hw("1.2TB SEAGATE ENT - M0009"))
        assert r.status == EOLStatus.EOL

    async def test_4tb_eol(self, checker):
        r = await checker.check(_hw("4TB SEAGATE ENT"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# Mid capacity drives — EOL
# ===================================================================


class TestMidCapacityEOL:
    async def test_6tb_eol(self, checker):
        r = await checker.check(_hw("6TB SEAGATE ENT"))
        assert r.status == EOLStatus.EOL

    async def test_8tb_eol(self, checker):
        r = await checker.check(_hw("8TB SEAGATE ENT"))
        assert r.status == EOLStatus.EOL

    async def test_10tb_eol(self, checker):
        r = await checker.check(_hw("10TB SEAGATE ENT - 0016"))
        assert r.status == EOLStatus.EOL

    async def test_12tb_eol(self, checker):
        r = await checker.check(_hw("12TB SEAGATE ENT"))
        assert r.status == EOLStatus.EOL

    async def test_14tb_eol(self, checker):
        r = await checker.check(_hw("14TB SEAGATE ENT"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# Large capacity drives — ACTIVE
# ===================================================================


class TestLargeCapacityActive:
    async def test_16tb_active_informational(self, checker):
        r = await checker.check(_hw("16TB SEAGATE ENT"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_18tb_active(self, checker):
        r = await checker.check(_hw("18TB SEAGATE ENT"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_20tb_active(self, checker):
        r = await checker.check(_hw("20TB SEAGATE ENT"))
        assert r.status == EOLStatus.ACTIVE

    async def test_24tb_active(self, checker):
        r = await checker.check(_hw("24TB SEAGATE ENT"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Unrecognizable model
# ===================================================================


class TestUnknown:
    async def test_no_capacity_returns_unknown(self, checker):
        r = await checker.check(_hw("SEAGATE ENT - MYSTERY"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 50
        assert "not-classified" in r.notes


# ===================================================================
# Product-line classification
# ===================================================================


class TestConstellationEOL:
    async def test_constellation_nm_model(self, checker):
        r = await checker.check(_hw("ST2000NM0033"))
        assert r.status == EOLStatus.EOL
        assert "Constellation" in r.notes or "Enterprise Capacity" in r.notes

    async def test_constellation_nx_model(self, checker):
        r = await checker.check(_hw("ST1000NX0313"))
        assert r.status == EOLStatus.EOL
        assert "Constellation" in r.notes


class TestHGSTEOL:
    async def test_hgst_model_eol(self, checker):
        r = await checker.check(_hw("HGST HUS726T4TALA6L4"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED
        assert "HGST" in r.notes

    async def test_hgst_hus_prefix(self, checker):
        r = await checker.check(_hw("HUS726T6TALE6L4"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED

    async def test_hgst_source_name(self, checker):
        r = await checker.check(_hw("HGST HUS726T4TALA6L4"))
        assert r.source_name == "seagate-product-line-rules"


class TestExosClassification:
    async def test_exos_x16_active(self, checker):
        r = await checker.check(_hw("ST16000NM001G"))
        assert r.status == EOLStatus.ACTIVE
        assert "Exos current" in r.notes

    async def test_exos_x18_active(self, checker):
        r = await checker.check(_hw("ST18000NM000J"))
        assert r.status == EOLStatus.ACTIVE

    async def test_exos_x20_active(self, checker):
        r = await checker.check(_hw("ST20000NM007D"))
        assert r.status == EOLStatus.ACTIVE


class TestEnterprisePerfEOL:
    async def test_10k_sas_eol(self, checker):
        r = await checker.check(_hw("SEAGATE 10K SAS"))
        assert r.status == EOLStatus.EOL
        assert "10K/15K" in r.notes

    async def test_15k_sas_eol(self, checker):
        r = await checker.check(_hw("SEAGATE 15K ENT"))
        assert r.status == EOLStatus.EOL


class TestNytroClassification:
    async def test_nytro_old_gen_eol(self, checker):
        r = await checker.check(_hw("NYTRO 1351"))
        assert r.status == EOLStatus.EOL
        assert "Nytro previous" in r.notes

    async def test_nytro_current_gen_active(self, checker):
        r = await checker.check(_hw("NYTRO 3550"))
        assert r.status == EOLStatus.ACTIVE
        assert "Nytro current" in r.notes

    async def test_nytro_5000_active(self, checker):
        r = await checker.check(_hw("NYTRO 5050"))
        assert r.status == EOLStatus.ACTIVE


class TestProductLineFunction:
    def test_hgst_returns_eol(self):
        result = _classify_by_product_line("HGST HUS726T4TALA6L4")
        assert result is not None
        assert result[0] == EOLStatus.EOL

    def test_constellation_returns_eol(self):
        result = _classify_by_product_line("ST1000NX0313")
        assert result is not None
        assert result[0] == EOLStatus.EOL

    def test_unknown_returns_none(self):
        result = _classify_by_product_line("SEAGATE MYSTERY DRIVE")
        assert result is None

    def test_exos_current_returns_active(self):
        result = _classify_by_product_line("ST16000NM001G")
        assert result is not None
        assert result[0] == EOLStatus.ACTIVE


# ===================================================================
# Source name
# ===================================================================


class TestSourceName:
    async def test_source_name(self, checker):
        r = await checker.check(_hw("10TB SEAGATE ENT"))
        assert r.source_name == "seagate-capacity-rules"

    async def test_product_line_source_name(self, checker):
        r = await checker.check(_hw("HGST HUS726T4TALA6L4"))
        assert r.source_name == "seagate-product-line-rules"


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_seagate(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "seagate" in checkers
        assert checkers["seagate"] is SeagateChecker
