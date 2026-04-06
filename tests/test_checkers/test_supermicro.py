"""Tests for the SupermicroChecker (generation-based classification only)."""

import pytest

from eol_tool.checkers.supermicro import SupermicroChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return SupermicroChecker()


def _hw(
    model: str, manufacturer: str = "Supermicro", category: str = "server-board"
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Model normalization
# ===================================================================


class TestNormalization:
    def test_strip_trailing_quantity(self):
        assert SupermicroChecker._normalize("CSE-113AC2-605WB - 2") == "CSE-113AC2-605WB"

    def test_strip_w_suffix(self):
        assert SupermicroChecker._normalize("X10SLL-F W/HS") == "X10SLL-F"

    def test_strip_optics_prefix(self):
        assert SupermicroChecker._normalize("OPTICS:JNP-QSFP-4X10GE-LR") == "JNP-QSFP-4X10GE-LR"

    def test_strip_description_suffix(self):
        assert SupermicroChecker._normalize("AOC-S40G-I2Q DUAL PORT 40G NIC") == "AOC-S40G-I2Q"

    def test_extract_board_from_description(self):
        assert SupermicroChecker._normalize("1U X10S W/E31241/1270 32GB") == "X10S"

    def test_bare_model_unchanged(self):
        assert SupermicroChecker._normalize("X10DRI") == "X10DRI"

    def test_whitespace(self):
        assert SupermicroChecker._normalize("  X13SCH-F  ") == "X13SCH-F"


# ===================================================================
# Static fallback — generation rules
# ===================================================================


class TestBoardGenerationEOL:
    """X9/X10 boards -- EOL via generation rules, no dates."""

    async def test_x9_board(self, checker):
        r = await checker.check(_hw("X9SCM-F"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 65
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION
        assert "X9" in r.notes
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_x10_board(self, checker):
        r = await checker.check(_hw("X10DRI"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 65
        assert "X10" in r.notes
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_x10_variant_drl(self, checker):
        r = await checker.check(_hw("X10DRL-I"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "none"

    async def test_x10_sdv(self, checker):
        r = await checker.check(_hw("X10SDV-8C+-LN2F"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "none"

    async def test_x10_board_with_description(self, checker):
        r = await checker.check(_hw("X10SLL-F W/HS"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "none"

    async def test_x10_in_server_description(self, checker):
        r = await checker.check(_hw("1U X10S W/E31241/1270 32GB", category="server"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.date_source == "none"

    async def test_h11_board_eol(self, checker):
        r = await checker.check(_hw("H11SSL-I"))
        assert r.status == EOLStatus.EOL
        assert "H11" in r.notes
        assert "Naples" in r.notes
        assert r.date_source == "none"


class TestBoardGenerationEOLAnnounced:
    """X11/H12 boards -- EOL_ANNOUNCED via generation rules, date_source='none'."""

    async def test_x11_board(self, checker):
        r = await checker.check(_hw("X11DDW-NT"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert r.confidence == 65
        assert "X11" in r.notes
        assert "Skylake" in r.notes
        assert r.date_source == "none"

    async def test_x11_ssl(self, checker):
        r = await checker.check(_hw("X11SSL-F"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert r.date_source == "none"

    async def test_h12_board(self, checker):
        r = await checker.check(_hw("H12SSL-I"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert "H12" in r.notes
        assert r.date_source == "none"

    async def test_spc621_maps_to_x11(self, checker):
        r = await checker.check(_hw("SPC621D8-2L2T"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert "X11" in r.notes
        assert r.date_source == "none"


class TestBoardGenerationActive:
    """X12/X13/X14/H13/H14 boards -- ACTIVE via generation rules."""

    async def test_x12_board(self, checker):
        r = await checker.check(_hw("X12DPL-I6"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 65
        assert "X12" in r.notes
        assert r.date_source == "none"

    async def test_x13_board(self, checker):
        r = await checker.check(_hw("X13SCH-F"))
        assert r.status == EOLStatus.ACTIVE
        assert "X13" in r.notes

    async def test_x14_board(self, checker):
        r = await checker.check(_hw("X14SSL-N", category="server-board"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_h13_board(self, checker):
        r = await checker.check(_hw("H13SAE-MF"))
        assert r.status == EOLStatus.ACTIVE
        assert "H13" in r.notes

    async def test_h14_board(self, checker):
        r = await checker.check(_hw("H14SSL-N"))
        assert r.status == EOLStatus.ACTIVE
        assert "H14" in r.notes


class TestSystemGeneration:
    async def test_sys_x9_era(self, checker):
        r = await checker.check(_hw("SYS-6017R-N3RF4+", category="server-barebone"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert "X9" in r.notes
        assert r.date_source == "none"

    async def test_sys_x10_era(self, checker):
        r = await checker.check(_hw("SYS-1028R-WTR", category="server-barebone"))
        assert r.status == EOLStatus.EOL
        assert "X10" in r.notes

    async def test_sys_x10_era_5018(self, checker):
        r = await checker.check(_hw("SYS-5018R-WR", category="server-barebone"))
        assert r.status == EOLStatus.EOL

    async def test_sys_x11_era(self, checker):
        r = await checker.check(_hw("SYS-1029P-WTRT", category="server-barebone"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert "X11" in r.notes

    async def test_sys_x11_era_2029(self, checker):
        r = await checker.check(_hw("SYS-2029GP-TR", category="server"))
        assert r.status == EOLStatus.EOL_ANNOUNCED

    async def test_as_system(self, checker):
        r = await checker.check(_hw("AS-1014S-WTRT", category="server-barebone"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert "H11" in r.notes


class TestHeatsinkGeneration:
    async def test_snk_x10_era(self, checker):
        r = await checker.check(_hw("SNK-P0047P", category="cooling"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.confidence == 65
        assert r.date_source == "none"

    async def test_snk_x10_era_46(self, checker):
        r = await checker.check(_hw("SNK-P0046A4", category="cooling"))
        assert r.status == EOLStatus.EOL

    async def test_snk_x11_era(self, checker):
        r = await checker.check(_hw("SNK-P0068APS4", category="cooling"))
        assert r.status == EOLStatus.EOL_ANNOUNCED

    async def test_snk_x11_era_62(self, checker):
        r = await checker.check(_hw("SNK-P0062P", category="cooling"))
        assert r.status == EOLStatus.EOL_ANNOUNCED

    async def test_snk_x12_era(self, checker):
        r = await checker.check(_hw("SNK-P0077P", category="cooling"))
        assert r.status == EOLStatus.ACTIVE

    async def test_snk_x13_era(self, checker):
        r = await checker.check(_hw("SNK-P0083AP4", category="cooling"))
        assert r.status == EOLStatus.ACTIVE

    async def test_snk_x13_era_87(self, checker):
        r = await checker.check(_hw("SNK-P0087P", category="cooling"))
        assert r.status == EOLStatus.ACTIVE


class TestChassis:
    async def test_chassis_113_eol(self, checker):
        r = await checker.check(_hw("CSE-113AC2-605WB - 2", category="chassis"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 75
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.date_source == "none"

    async def test_chassis_213_eol(self, checker):
        r = await checker.check(_hw("CSE-213A-R900LPB", category="chassis"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_chassis_825_eol(self, checker):
        r = await checker.check(_hw("CSE-825TQC-R740LPB", category="chassis"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED

    async def test_chassis_826_eol(self, checker):
        r = await checker.check(_hw("CSE-826BE1C4", category="chassis"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_chassis_la26_active(self, checker):
        r = await checker.check(_hw("CSE-LA26E1C4-R609LP", category="chassis"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75

    async def test_chassis_unknown_fallback(self, checker):
        r = await checker.check(_hw("CSE-999X", category="chassis"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 40
        assert r.risk_category == RiskCategory.PROCUREMENT


class TestAddonCards:
    async def test_aoc_sas2lp_eol(self, checker):
        r = await checker.check(_hw("AOC-SAS2LP-H8IR", category="storage"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 75
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_aoc_stgn_eol(self, checker):
        r = await checker.check(_hw("AOC-STGN-I2S", category="nic"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_aoc_s40g_active(self, checker):
        r = await checker.check(_hw("AOC-S40G-I2Q DUAL PORT 40G NIC", category="nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75

    async def test_aoc_cgp_active(self, checker):
        r = await checker.check(_hw("AOC-CGP-I2M", category="nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75

    async def test_aom_module_unknown(self, checker):
        r = await checker.check(_hw("AOM-CGP-I2M", category="nic"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_riser_card_follows_board(self, checker):
        r = await checker.check(_hw("RSC-W-66G4 RISER", category="unknown"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert "riser-card-follows-board-lifecycle" in r.notes


class TestNonSupermicroModels:
    async def test_nvidia_gpu(self, checker):
        r = await checker.check(_hw("VCGGTX1080T11-CG2-BLK", category="gpu"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.confidence == 40

    async def test_juniper_optic_lr(self, checker):
        r = await checker.check(_hw("OPTICS:JNP-QSFP-4X10GE-LR", category="optic"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_juniper_optic_sr(self, checker):
        r = await checker.check(_hw("JNP-QSFP-4X10GE-SR", category="optic"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_juniper_mx960(self, checker):
        r = await checker.check(_hw("MX960", category="network-device"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_juniper_pwr_mx960(self, checker):
        r = await checker.check(_hw("PWR-MX960-AC-S", category="power-supply"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_juniper_mic3(self, checker):
        r = await checker.check(_hw("MIC3-3D-1X100GE-CFP", category="network-module"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_toshiba_ssd(self, checker):
        r = await checker.check(_hw("TOS THNSNH128GBST", category="ssd"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_asrock_board(self, checker):
        r = await checker.check(_hw("S8016AGM2NR", category="server-board"))
        assert r.status == EOLStatus.NOT_FOUND


class TestStaticMemory:
    async def test_vlp_memory_active(self, checker):
        r = await checker.check(_hw("VLP MEM-VR416LD-EU26", category="memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 75


class TestRiskCategory:
    async def test_server_board_support(self, checker):
        r = await checker.check(_hw("X12STH-F", category="server-board"))
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_server_support(self, checker):
        r = await checker.check(_hw("SYS-6019P-MT", category="server-barebone"))
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_cooling_procurement(self, checker):
        r = await checker.check(_hw("SNK-P0083P", category="cooling"))
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_chassis_procurement(self, checker):
        r = await checker.check(_hw("CSE-826BE1C4", category="chassis"))
        assert r.risk_category == RiskCategory.PROCUREMENT


class TestSourceName:
    async def test_generation_source(self, checker):
        r = await checker.check(_hw("X10DRI"))
        assert r.source_name == "supermicro-generation"

    async def test_not_found_source(self, checker):
        r = await checker.check(_hw("MX960", category="network-device"))
        assert r.source_name == "supermicro-generation"


class TestRegistration:
    def test_auto_registers_for_supermicro(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "supermicro" in checkers
        assert checkers["supermicro"] is SupermicroChecker
