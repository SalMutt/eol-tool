"""Tests for the BroadcomChecker."""

import pytest

from eol_tool.checkers.broadcom import BroadcomChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return BroadcomChecker()


def _hw(
    model: str, manufacturer: str = "Broadcom", category: str = "raid-controller"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# SAS2 RAID controllers — all EOL
# ===================================================================


class TestSAS2EOL:
    async def test_9240_8i(self, checker):
        r = await checker.check(_hw("9240-8I"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.confidence == 85

    async def test_9260_4i(self, checker):
        r = await checker.check(_hw("9260-4I"))
        assert r.status == EOLStatus.EOL

    async def test_9260_8i(self, checker):
        r = await checker.check(_hw("9260-8I"))
        assert r.status == EOLStatus.EOL

    async def test_9261_8i(self, checker):
        r = await checker.check(_hw("9261-8I"))
        assert r.status == EOLStatus.EOL

    async def test_9271_4i(self, checker):
        r = await checker.check(_hw("9271-4I"))
        assert r.status == EOLStatus.EOL

    async def test_9271_8i(self, checker):
        r = await checker.check(_hw("9271-8I"))
        assert r.status == EOLStatus.EOL

    async def test_9220_8i(self, checker):
        r = await checker.check(_hw("9220-8I"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# SAS3 controllers
# ===================================================================


class TestSAS3:
    async def test_9300_8i_eol(self, checker):
        r = await checker.check(_hw("9300-8I"))
        assert r.status == EOLStatus.EOL

    async def test_9305_16i_active(self, checker):
        r = await checker.check(_hw("9305-16I"))
        assert r.status == EOLStatus.ACTIVE

    async def test_9361_8i_eol(self, checker):
        r = await checker.check(_hw("9361-8I"))
        assert r.status == EOLStatus.EOL

    async def test_9361_16i_eol(self, checker):
        r = await checker.check(_hw("9361-16I"))
        assert r.status == EOLStatus.EOL

    async def test_9362_8i_active(self, checker):
        r = await checker.check(_hw("9362-8I"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# SAS4 / NVMe tri-mode — active
# ===================================================================


class TestSAS4:
    async def test_9500_8i_active(self, checker):
        r = await checker.check(_hw("9500-8I"))
        assert r.status == EOLStatus.ACTIVE

    async def test_9660_16i_active(self, checker):
        r = await checker.check(_hw("9660-16I"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Intel RAID Expander — should return NOT_FOUND
# ===================================================================


class TestIntelExpander:
    async def test_res2sv240_not_found(self, checker):
        r = await checker.check(_hw("RES2SV240"))
        assert r.status == EOLStatus.NOT_FOUND
        assert "intel" in r.notes.lower()


# ===================================================================
# Normalization
# ===================================================================


class TestNormalization:
    def test_strip_megaraid_sas_prefix(self):
        assert BroadcomChecker._normalize("MegaRAID SAS 9361-8I") == "9361-8I"

    def test_strip_lsi_prefix(self):
        assert BroadcomChecker._normalize("LSI 9300-8I") == "9300-8I"

    def test_uppercase(self):
        assert BroadcomChecker._normalize("9271-8i") == "9271-8I"

    def test_strip_whitespace(self):
        assert BroadcomChecker._normalize("  9500-8I  ") == "9500-8I"

    async def test_megaraid_prefix_lookup(self, checker):
        r = await checker.check(_hw("MegaRAID SAS 9361-8I"))
        assert r.status == EOLStatus.EOL

    async def test_lsi_prefix_lookup(self, checker):
        r = await checker.check(_hw("LSI 9300-8I"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# Source name
# ===================================================================


class TestSourceName:
    async def test_known_product_source(self, checker):
        r = await checker.check(_hw("9361-8I"))
        assert r.source_name == "broadcom-static-lookup"

    async def test_not_found_source(self, checker):
        r = await checker.check(_hw("UNKNOWN-MODEL"))
        assert r.source_name == "broadcom-static-lookup"


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_broadcom(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "broadcom" in checkers
        assert checkers["broadcom"] is BroadcomChecker
