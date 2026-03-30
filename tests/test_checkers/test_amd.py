"""Tests for the AMDChecker."""

import pytest

from eol_tool.checkers.amd import AMDChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return AMDChecker()


def _hw(model: str, manufacturer: str = "AMD", category: str = "cpu") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Model normalization
# ===================================================================


class TestNormalization:
    def test_strip_amd_prefix(self):
        assert AMDChecker._normalize("AMD EPYC 7282") == "EPYC 7282"

    def test_strip_cpu_suffix(self):
        assert AMDChecker._normalize("AMD 9174F CPU") == "9174F"

    def test_strip_both(self):
        assert AMDChecker._normalize("AMD EPYC 9124 CPU") == "EPYC 9124"

    def test_uppercase_and_trim(self):
        assert AMDChecker._normalize("  epyc 7742  ") == "EPYC 7742"

    def test_no_prefix_no_suffix(self):
        assert AMDChecker._normalize("EPYC 7351") == "EPYC 7351"


# ===================================================================
# Naples — EPYC 7001 series (EOL)
# ===================================================================


class TestNaples:
    async def test_epyc_7281(self, checker):
        r = await checker.check(_hw("EPYC 7281"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.confidence == 85
        assert "Naples" in r.notes

    async def test_epyc_7351(self, checker):
        r = await checker.check(_hw("EPYC 7351"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_epyc_7351p(self, checker):
        r = await checker.check(_hw("EPYC 7351P"))
        assert r.status == EOLStatus.EOL

    async def test_epyc_7401p(self, checker):
        r = await checker.check(_hw("EPYC 7401P"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED

    async def test_epyc_7551p(self, checker):
        r = await checker.check(_hw("EPYC 7551P"))
        assert r.status == EOLStatus.EOL

    async def test_epyc_7601(self, checker):
        r = await checker.check(_hw("EPYC 7601"))
        assert r.status == EOLStatus.EOL

    async def test_amd_prefixed_7251p(self, checker):
        r = await checker.check(_hw("AMD EPYC 7251P"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT


# ===================================================================
# Rome — EPYC 7002 series (EOL)
# ===================================================================


class TestRome:
    async def test_epyc_7282(self, checker):
        r = await checker.check(_hw("AMD EPYC 7282"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.confidence == 85
        assert "Rome" in r.notes

    async def test_epyc_7232p(self, checker):
        r = await checker.check(_hw("EPYC 7232P"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_epyc_7252(self, checker):
        r = await checker.check(_hw("EPYC 7252"))
        assert r.status == EOLStatus.EOL

    async def test_epyc_7302p(self, checker):
        r = await checker.check(_hw("AMD EPYC 7302P"))
        assert r.status == EOLStatus.EOL

    async def test_epyc_7402p(self, checker):
        r = await checker.check(_hw("AMD EPYC 7402P"))
        assert r.status == EOLStatus.EOL

    async def test_epyc_7452(self, checker):
        r = await checker.check(_hw("EPYC 7452"))
        assert r.status == EOLStatus.EOL

    async def test_epyc_7742(self, checker):
        r = await checker.check(_hw("EPYC 7742"))
        assert r.status == EOLStatus.EOL
        assert "Rome" in r.notes

    async def test_bare_7302p(self, checker):
        r = await checker.check(_hw("7302P"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL


# ===================================================================
# Milan — EPYC 7003 series (ACTIVE)
# ===================================================================


class TestMilan:
    async def test_epyc_7443p(self, checker):
        r = await checker.check(_hw("AMD EPYC 7443P"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.confidence == 85
        assert "Milan" in r.notes

    async def test_epyc_7713(self, checker):
        r = await checker.check(_hw("AMD EPYC 7713"))
        assert r.status == EOLStatus.ACTIVE

    async def test_epyc_7763(self, checker):
        r = await checker.check(_hw("EPYC 7763"))
        assert r.status == EOLStatus.ACTIVE

    async def test_epyc_7413(self, checker):
        r = await checker.check(_hw("EPYC 7413"))
        assert r.status == EOLStatus.ACTIVE

    async def test_epyc_7643(self, checker):
        r = await checker.check(_hw("EPYC 7643"))
        assert r.status == EOLStatus.ACTIVE

    async def test_epyc_7f53(self, checker):
        r = await checker.check(_hw("AMD EPYC 7F53"))
        assert r.status == EOLStatus.ACTIVE
        assert "Milan" in r.notes

    async def test_epyc_73f3(self, checker):
        r = await checker.check(_hw("EPYC 73F3"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Genoa — EPYC 9004 series (ACTIVE)
# ===================================================================


class TestGenoa:
    async def test_epyc_9124(self, checker):
        r = await checker.check(_hw("AMD EPYC 9124"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.NONE
        assert r.confidence == 90
        assert "Genoa" in r.notes

    async def test_epyc_9174f(self, checker):
        r = await checker.check(_hw("EPYC 9174F"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_epyc_9334(self, checker):
        r = await checker.check(_hw("AMD EPYC 9334"))
        assert r.status == EOLStatus.ACTIVE

    async def test_amd_9174f_cpu(self, checker):
        """'AMD 9174F CPU' from dataset normalizes and matches Genoa."""
        r = await checker.check(_hw("AMD 9174F CPU"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "Genoa" in r.notes

    async def test_epyc_9654(self, checker):
        r = await checker.check(_hw("EPYC 9654"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Siena — EPYC 4004 series (ACTIVE)
# ===================================================================


class TestSiena:
    async def test_epyc_4564p(self, checker):
        r = await checker.check(_hw("AMD EPYC 4564P"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.NONE
        assert r.confidence == 90
        assert "Siena" in r.notes

    async def test_epyc_4584px(self, checker):
        r = await checker.check(_hw("AMD EPYC 4584PX"))
        assert r.status == EOLStatus.ACTIVE

    async def test_epyc_4585px(self, checker):
        r = await checker.check(_hw("AMD EPYC 4585PX"))
        assert r.status == EOLStatus.ACTIVE
        assert "Siena" in r.notes

    async def test_epyc_4124p(self, checker):
        r = await checker.check(_hw("EPYC 4124P"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Ryzen 3000 series Zen 2 AM4 (ACTIVE / INFORMATIONAL)
# ===================================================================


class TestRyzen3000:
    async def test_3900x(self, checker):
        r = await checker.check(_hw("9 3900X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.confidence == 85
        assert "Ryzen 3000" in r.notes
        assert r.source_name == "amd-ryzen-generation"

    async def test_3950x(self, checker):
        r = await checker.check(_hw("9 3950X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "Zen 2" in r.notes


# ===================================================================
# Ryzen 5000 series Zen 3 AM4 (ACTIVE / INFORMATIONAL)
# ===================================================================


class TestRyzen5000:
    async def test_5500(self, checker):
        r = await checker.check(_hw("5 5500"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "Ryzen 5000" in r.notes

    async def test_5600g(self, checker):
        r = await checker.check(_hw("5 5600G"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_5700g(self, checker):
        r = await checker.check(_hw("7 5700G"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_5800x(self, checker):
        r = await checker.check(_hw("7 5800X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_5900x(self, checker):
        r = await checker.check(_hw("9 5900X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_5950x(self, checker):
        r = await checker.check(_hw("9 5950X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "Zen 3" in r.notes


# ===================================================================
# Ryzen 7000 series Zen 4 AM5 (ACTIVE / NONE)
# ===================================================================


class TestRyzen7000:
    async def test_7600x(self, checker):
        r = await checker.check(_hw("5 7600X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.NONE
        assert r.confidence == 90
        assert "Ryzen 7000" in r.notes

    async def test_7900x(self, checker):
        r = await checker.check(_hw("9 7900X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_7950x(self, checker):
        r = await checker.check(_hw("9 7950X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_7960x(self, checker):
        r = await checker.check(_hw("9 7960X"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "Zen 4" in r.notes


# ===================================================================
# Threadripper PRO 7000 (ACTIVE / NONE)
# ===================================================================


class TestThreadripper:
    async def test_7965wx(self, checker):
        r = await checker.check(_hw("7965WX"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.NONE
        assert r.confidence == 90
        assert "Threadripper PRO 7000" in r.notes
        assert r.source_name == "amd-ryzen-generation"

    async def test_7965wx_with_pro(self, checker):
        r = await checker.check(_hw("PRO 7965WX"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Ryzen normalization
# ===================================================================


class TestRyzenNormalization:
    def test_strip_tier_digit_and_space(self):
        assert AMDChecker._normalize_ryzen("5 5500") == "5500"

    def test_strip_pro(self):
        assert AMDChecker._normalize_ryzen("PRO 7965WX") == "7965WX"

    def test_strip_ryzen_and_tier(self):
        assert AMDChecker._normalize_ryzen("RYZEN 9 5900X") == "5900X"

    def test_strip_threadripper_pro(self):
        assert AMDChecker._normalize_ryzen("THREADRIPPER PRO 7965WX") == "7965WX"

    def test_bare_model_unchanged(self):
        assert AMDChecker._normalize_ryzen("7965WX") == "7965WX"

    def test_motherboard_passthrough(self):
        assert AMDChecker._normalize_ryzen("WRX90E-SAGE SE") == "WRX90E-SAGE SE"


# ===================================================================
# Unknown / NOT_FOUND
# ===================================================================


class TestNotFound:
    async def test_server_board_not_matched(self, checker):
        r = await checker.check(_hw("WRX90E-SAGE SE"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_random_string(self, checker):
        r = await checker.check(_hw("ACME-Widget-9000"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.source_name == "amd-epyc-generation"


# ===================================================================
# Confidence range
# ===================================================================


class TestConfidence:
    async def test_eol_confidence_85(self, checker):
        r = await checker.check(_hw("EPYC 7282"))
        assert r.confidence == 85

    async def test_active_7003_confidence_85(self, checker):
        r = await checker.check(_hw("EPYC 7763"))
        assert r.confidence == 85

    async def test_genoa_confidence_90(self, checker):
        r = await checker.check(_hw("EPYC 9124"))
        assert r.confidence == 90

    async def test_siena_confidence_90(self, checker):
        r = await checker.check(_hw("EPYC 4564P"))
        assert r.confidence == 90


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_amd(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "amd" in checkers
        assert checkers["amd"] is AMDChecker


# ===================================================================
# All EPYC models from the dataset get classified
# ===================================================================


class TestDatasetCoverage:
    """Verify every EPYC model from the dataset matches a generation."""

    _DATASET_EPYC_MODELS = [
        ("AMD 9174F CPU", "Genoa"),
        ("AMD EPYC 4564P", "Siena"),
        ("AMD EPYC 4584PX", "Siena"),
        ("AMD EPYC 4585PX", "Siena"),
        ("AMD EPYC 7251P", "Naples"),
        ("AMD EPYC 7282", "Rome"),
        ("AMD EPYC 7302P", "Rome"),
        ("AMD EPYC 7402P", "Rome"),
        ("AMD EPYC 7443P", "Milan"),
        ("AMD EPYC 7713", "Milan"),
        ("AMD EPYC 7F53", "Milan"),
        ("AMD EPYC 9124", "Genoa"),
        ("AMD EPYC 9334", "Genoa"),
        ("EPYC 7232P", "Rome"),
        ("EPYC 7251P", "Naples"),
        ("EPYC 7252", "Rome"),
        ("EPYC 7351", "Naples"),
        ("EPYC 7351P", "Naples"),
        ("EPYC 7401P", "Naples"),
        ("EPYC 7413", "Milan"),
        ("EPYC 7452", "Rome"),
        ("EPYC 7551P", "Naples"),
        ("EPYC 7643", "Milan"),
        ("EPYC 7742", "Rome"),
        ("7302P", "Rome"),
    ]

    @pytest.mark.parametrize("model_str,gen_name", _DATASET_EPYC_MODELS)
    async def test_dataset_epyc_model(self, checker, model_str, gen_name):
        r = await checker.check(_hw(model_str))
        assert r.status != EOLStatus.NOT_FOUND, f"{model_str} was not classified"
        assert gen_name in r.notes, f"{model_str} expected {gen_name} but got: {r.notes}"
