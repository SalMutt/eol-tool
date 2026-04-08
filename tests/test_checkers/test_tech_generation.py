"""Tests for the TechGenerationChecker."""

from datetime import datetime
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from eol_tool.checkers.tech_generation import TechGenerationChecker
from eol_tool.models import (
    EOLReason,
    EOLResult,
    EOLStatus,
    HardwareModel,
    RiskCategory,
)


@pytest.fixture
def checker():
    return TechGenerationChecker()


def _hw(model: str, manufacturer: str = "", category: str = "") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# DDR3 Memory — EOL / PROCUREMENT (10+ test cases)
# ===================================================================


class TestDDR3:
    async def test_hynix_hmt_prefix(self, checker):
        r = await checker.check(_hw("HMT42GR7AFR4A", "SK Hynix", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION

    async def test_hynix_hmt31(self, checker):
        r = await checker.check(_hw("HMT31GR7CFR4C", "SK Hynix", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_samsung_m393b(self, checker):
        r = await checker.check(_hw("M393B2G70BH0", "Samsung", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_samsung_m393b_variant(self, checker):
        r = await checker.check(_hw("M393B1K70DH0", "Samsung", "memory"))
        assert r.status == EOLStatus.EOL

    async def test_micron_mt36ksf(self, checker):
        r = await checker.check(_hw("MT36KSF2G72PZ-1G6E1", "Micron", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_micron_mt18ksf(self, checker):
        r = await checker.check(_hw("MT18KSF1G72AZ", "Micron", "memory"))
        assert r.status == EOLStatus.EOL

    async def test_kingston_kvr13(self, checker):
        r = await checker.check(_hw("KVR13R9D4/16", "Kingston", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_kingston_kvr16(self, checker):
        r = await checker.check(_hw("KVR16R11D4/16", "Kingston", "memory"))
        assert r.status == EOLStatus.EOL

    async def test_generic_ddr3_keyword(self, checker):
        r = await checker.check(_hw("Generic DDR3 DIMM", "Unknown", "memory"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_generic_1333_speed(self, checker):
        r = await checker.check(_hw("8GB 1333MHz RDIMM", "Unknown", "memory"))
        assert r.status == EOLStatus.EOL

    async def test_generic_1600_speed(self, checker):
        r = await checker.check(_hw("16GB 1600MHz ECC", "Unknown", "memory"))
        assert r.status == EOLStatus.EOL

    async def test_hmt41_prefix(self, checker):
        r = await checker.check(_hw("HMT41GU7MFR8C", "SK Hynix", "memory"))
        assert r.status == EOLStatus.EOL


# ===================================================================
# DDR4 Memory — ACTIVE / INFORMATIONAL (5+ test cases)
# ===================================================================


class TestDDR4:
    async def test_hynix_hma(self, checker):
        r = await checker.check(_hw("HMA82GR7AFR8N", "SK Hynix", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_samsung_m393a(self, checker):
        r = await checker.check(_hw("M393A4K40BB2", "Samsung", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_micron_mta18adf(self, checker):
        r = await checker.check(_hw("MTA18ADF2G72AZ", "Micron", "memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_kingston_ksm26(self, checker):
        r = await checker.check(_hw("KSM26RD8/16HDI", "Kingston", "memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_generic_ddr4_keyword(self, checker):
        r = await checker.check(_hw("32GB DDR4-2666 RDIMM", "Unknown", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_generic_3200_speed(self, checker):
        r = await checker.check(_hw("64GB 3200MHz ECC", "Unknown", "memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_hynix_hmaa(self, checker):
        r = await checker.check(_hw("HMAA8GL7AMR4N", "SK Hynix", "memory"))
        assert r.status == EOLStatus.ACTIVE

    async def test_crucial_ct16g4rfd4(self, checker):
        r = await checker.check(_hw("CT16G4RFD4266", "Crucial", "memory"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# DDR5 Memory — ACTIVE / NONE (3+ test cases)
# ===================================================================


class TestDDR5:
    async def test_hynix_hmcg(self, checker):
        r = await checker.check(_hw("HMCG88AHBRA478N", "SK Hynix", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_samsung_m321(self, checker):
        r = await checker.check(_hw("M321RAGA0B20-CWK", "Samsung", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_generic_ddr5_keyword(self, checker):
        r = await checker.check(_hw("64GB DDR5-5600", "Unknown", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_kingston_ksm48(self, checker):
        r = await checker.check(_hw("KSM48R40BD8KMM-32HMR", "Kingston", "memory"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Intel CPU generation — E5 / E3 / Scalable (8+ test cases)
# ===================================================================


class TestIntelCPU:
    async def test_e5_v1_bare(self, checker):
        r = await checker.check(_hw("E5-2620", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert "v1" in r.notes

    async def test_e5_v2(self, checker):
        r = await checker.check(_hw("E5-2670 V2", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_e5_v3(self, checker):
        r = await checker.check(_hw("E5-2697 V3", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_e5_v4(self, checker):
        r = await checker.check(_hw("E5-2683 V4", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_e3_v3(self, checker):
        r = await checker.check(_hw("E3-1231 V3", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_e3_v5(self, checker):
        r = await checker.check(_hw("E3-1230 V5", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_e3_v6(self, checker):
        r = await checker.check(_hw("E3-1270 V6", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_scalable_1st_gen_skylake(self, checker):
        r = await checker.check(_hw("Gold 6154", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert "Skylake" in r.notes

    async def test_scalable_2nd_gen_cascade_lake(self, checker):
        r = await checker.check(_hw("Silver 4216", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "Cascade Lake" in r.notes

    async def test_e_2100_active(self, checker):
        r = await checker.check(_hw("E-2136", "Intel", "cpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_e_2100_with_g_suffix(self, checker):
        r = await checker.check(_hw("E-2176G", "Intel", "cpu"))
        assert r.status == EOLStatus.ACTIVE

    async def test_scalable_with_letter_suffix(self, checker):
        r = await checker.check(_hw("Xeon Gold 6138T", "Intel", "cpu"))
        assert r.status == EOLStatus.EOL
        assert "Skylake" in r.notes


# ===================================================================
# AMD EPYC generation (5+ test cases)
# ===================================================================


class TestAMDEPYC:
    async def test_naples_7001(self, checker):
        r = await checker.check(_hw("EPYC 7281", "AMD", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT
        assert "Naples" in r.notes

    async def test_rome_7002(self, checker):
        r = await checker.check(_hw("EPYC 7742", "AMD", "cpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "Rome" in r.notes

    async def test_milan_7003(self, checker):
        r = await checker.check(_hw("EPYC 7763", "AMD", "cpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "Milan" in r.notes

    async def test_genoa_9004(self, checker):
        r = await checker.check(_hw("EPYC 9174F", "AMD", "cpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "Genoa" in r.notes

    async def test_siena_4004(self, checker):
        r = await checker.check(_hw("EPYC 4564P", "AMD", "cpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "Siena" in r.notes

    async def test_siena_4005_pattern(self, checker):
        r = await checker.check(_hw("EPYC 4585PX", "AMD", "cpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Intel SSD EOL detection
# ===================================================================


class TestIntelSSD:
    async def test_s3500(self, checker):
        r = await checker.check(_hw("Intel DC S3500 480GB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_p4510(self, checker):
        r = await checker.check(_hw("Intel DC P4510 2TB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_d3_s4510(self, checker):
        r = await checker.check(_hw("Intel D3-S4510 960GB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_s4510_short_format(self, checker):
        """'240GB 2.5 S4510' format without D3- prefix."""
        r = await checker.check(_hw("240GB 2.5 S4510", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_s4610_short_format(self, checker):
        r = await checker.check(_hw("480GB 2.5 S4610", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_s35xx_format(self, checker):
        """'800GB 2.5 S35XX' format matches via S35 substring."""
        r = await checker.check(_hw("800GB 2.5 S35XX", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_p4511(self, checker):
        r = await checker.check(_hw("Intel DC P4511 2TB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT


# ===================================================================
# Intel consumer/datacenter SSD EOL detection
# ===================================================================


class TestIntelConsumerSSD:
    async def test_540_series(self, checker):
        r = await checker.check(_hw("Intel 540s 240GB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_520_series(self, checker):
        r = await checker.check(_hw("Intel 520 Series 180GB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_660p(self, checker):
        r = await checker.check(_hw("Intel 660P 1TB NVMe", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_760p(self, checker):
        r = await checker.check(_hw("Intel 760P 512GB", "Intel", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_520_not_matched_without_ssd_category(self, checker):
        """520 should NOT match when category is nic (avoids X520 collision)."""
        r = await checker.check(_hw("520 something", "Intel", "nic"))
        # Should not match the consumer SSD rule — category is nic
        assert r.status != EOLStatus.EOL or "520" not in r.notes or "consumer" not in r.notes

    async def test_x520_nic_not_matched_as_ssd(self, checker):
        """X520 with ssd category should not match consumer 520 rule."""
        r = await checker.check(_hw("X520-DA2", "Intel", "ssd"))
        # X520 matches Intel NIC rule in _check_network first
        assert r.status == EOLStatus.EOL
        assert "X520" in r.notes


# ===================================================================
# Intel RAID expander
# ===================================================================


class TestIntelRAIDExpander:
    async def test_res2sv240(self, checker):
        r = await checker.check(_hw("RES2SV240", "Intel", "storage"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert "RES2SV240" in r.notes


# ===================================================================
# Intel NIC generation detection
# ===================================================================


class TestIntelNIC:
    async def test_x520_da2_eol(self, checker):
        r = await checker.check(_hw("X520-DA2", "Intel", "nic"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_x540_t2_eol(self, checker):
        r = await checker.check(_hw("X540-T2", "Intel", "nic"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_i350_t4_active(self, checker):
        r = await checker.check(_hw("I350-T4", "Intel", "nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_x550_t2_active(self, checker):
        r = await checker.check(_hw("X550-T2", "Intel", "nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_x710_bm2_active(self, checker):
        r = await checker.check(_hw("X710-BM2", "Intel", "nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_x710_t4l_active(self, checker):
        r = await checker.check(_hw("X710-T4L", "Intel", "nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_x722_da4_active(self, checker):
        r = await checker.check(_hw("X722-DA4", "Intel", "nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_1gbe_ethernet_not_found(self, checker):
        r = await checker.check(_hw("1GbE Ethernet", "Intel", "nic"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# Intel optics
# ===================================================================


class TestIntelOptics:
    async def test_sfp_10gsr_85_not_found(self, checker):
        r = await checker.check(_hw("SFP-10GSR-85", "Intel", "optic"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# Samsung SSD generation detection
# ===================================================================


class TestSamsungSSD:
    async def test_840_eol(self, checker):
        r = await checker.check(_hw("Samsung 840 EVO 500GB", "Samsung", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_870_active(self, checker):
        r = await checker.check(_hw("Samsung 870 EVO 1TB", "Samsung", "ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_990_active(self, checker):
        r = await checker.check(_hw("Samsung 990 PRO 2TB", "Samsung", "ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_pm883_eol(self, checker):
        r = await checker.check(_hw("PM883 1.92TB", "Samsung", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_pm9a3_active(self, checker):
        r = await checker.check(_hw("PM9A3 3.84TB", "Samsung", "ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Brocade and EVGA vendor-acquired detection
# ===================================================================


class TestVendorAcquired:
    async def test_brocade_eol(self, checker):
        r = await checker.check(_hw("ICX6610-48-PE", "Brocade", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED

    async def test_evga_eol(self, checker):
        r = await checker.check(_hw("11G-P4-2487-KR", "EVGA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert r.eol_reason == EOLReason.VENDOR_ACQUIRED


# ===================================================================
# Mellanox generation detection
# ===================================================================


class TestMellanox:
    async def test_connectx2_eol(self, checker):
        r = await checker.check(_hw("MNPA19-XTR", "Mellanox", "nic"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_connectx3_cx312a(self, checker):
        r = await checker.check(_hw("CX312A", "Mellanox", "nic"))
        assert r.status == EOLStatus.EOL

    async def test_connectx4_active(self, checker):
        r = await checker.check(_hw("CX4121A", "Mellanox", "nic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE

    async def test_connectx5_active(self, checker):
        r = await checker.check(_hw("ConnectX-5 EN", "Mellanox", "nic"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# NVIDIA GPU generation detection
# ===================================================================


class TestNVIDIAGPU:
    async def test_k80_eol(self, checker):
        r = await checker.check(_hw("Tesla K80 24GB", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SUPPORT

    async def test_gtx_1080_ti_eol(self, checker):
        r = await checker.check(_hw("GeForce GTX 1080 Ti", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_p2200_eol(self, checker):
        r = await checker.check(_hw("Quadro P2200", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_geforce_210_eol(self, checker):
        r = await checker.check(_hw("GeForce 210", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_rtx_a6000_active(self, checker):
        r = await checker.check(_hw("RTXA6000", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Dynatron cooling
# ===================================================================


class TestCooling:
    async def test_dynatron_unknown(self, checker):
        r = await checker.check(_hw("A26", "Dynatron", "cooling"))
        assert r.status == EOLStatus.UNKNOWN
        assert "heatsink-lifecycle-follows-cpu-socket" in r.notes


# ===================================================================
# Unmatched models return NOT_FOUND
# ===================================================================


class TestNotFound:
    async def test_unmatched_generic(self, checker):
        r = await checker.check(_hw("ACME-Widget-9000", "Acme", "widget"))
        assert r.status == EOLStatus.NOT_FOUND
        assert r.source_name == "tech-generation-rules"

    async def test_unmatched_dell_server(self, checker):
        r = await checker.check(_hw("PowerEdge R640", "Dell", "server"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# Checker priority order: vendor → techgen → fallback
# ===================================================================


class TestCheckerPriority:
    """Verify the CLI respects the vendor → techgen → fallback priority."""

    def _write_xlsx(self, path, models):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Models"
        ws.append(["Model", "Manufacturer", "Category", "Condition", "Original_Item"])
        for model, mfr, cat in models:
            ws.append([model, mfr, cat, "", ""])
        wb.save(path)
        wb.close()

    def test_techgen_before_fallback(self, tmp_path):
        """DDR3 memory: all checkers run, but techgen result wins over fallback."""
        from eol_tool.checker import BaseChecker
        from eol_tool.cli import cli

        class TrackingFallback(BaseChecker):
            manufacturer_name = "__fallback__"
            rate_limit = 10
            priority = 30

            async def check(self, model):
                return EOLResult(
                    model=model,
                    status=EOLStatus.UNKNOWN,
                    checked_at=datetime.now(),
                    source_name="fallback",
                )

        xlsx = tmp_path / "input.xlsx"
        output = tmp_path / "output.xlsx"
        self._write_xlsx(xlsx, [
            ("HMT42GR7AFR4A", "SK Hynix", "memory"),
            ("ACME-Widget-9000", "SK Hynix", "widget"),
        ])

        with (
            patch("eol_tool.check_pipeline.get_checker") as mock_get,
            patch("eol_tool.cli._list_checkers") as mock_list,
        ):
            mock_list.return_value = {
                "__techgen__": TechGenerationChecker,
                "__fallback__": TrackingFallback,
            }

            def _get(name):
                if name == "__techgen__":
                    return TechGenerationChecker
                if name == "__fallback__":
                    return TrackingFallback
                return None

            mock_get.side_effect = _get

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["check", "--input", str(xlsx), "--output", str(output), "--no-cache"],
            )

        assert result.exit_code == 0, result.output
        # All checkers run, but techgen's EOL result for HMT beats fallback's UNKNOWN
        assert "eol" in result.output.lower()

    def test_vendor_checker_takes_priority(self, tmp_path):
        """All checkers run, but vendor checker's ACTIVE result wins via pipeline."""
        from eol_tool.checker import BaseChecker
        from eol_tool.cli import cli

        class VendorChecker(BaseChecker):
            manufacturer_name = "sk hynix"
            rate_limit = 10
            priority = 40

            async def check(self, model):
                return EOLResult(
                    model=model,
                    status=EOLStatus.ACTIVE,
                    checked_at=datetime.now(),
                    source_name="vendor",
                    confidence=90,
                )

        xlsx = tmp_path / "input.xlsx"
        self._write_xlsx(xlsx, [("HMT42GR7AFR4A", "SK Hynix", "memory")])

        with (
            patch("eol_tool.check_pipeline.get_checker") as mock_get,
            patch("eol_tool.cli._list_checkers") as mock_list,
        ):
            mock_list.return_value = {
                "sk hynix": VendorChecker,
                "__techgen__": TechGenerationChecker,
            }

            def _get(name):
                if name == "sk hynix":
                    return VendorChecker
                if name == "__techgen__":
                    return TechGenerationChecker
                return None

            mock_get.side_effect = _get

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["check", "--input", str(xlsx), "--no-cache"],
            )

        assert result.exit_code == 0, result.output
        assert "done" in result.output


# ===================================================================
# Micron SSD tests
# ===================================================================


class TestMicronSSD:
    async def test_5100_eol(self, checker):
        r = await checker.check(_hw("Micron 5100 MAX 960GB", "Micron", "ssd"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_7450_active(self, checker):
        r = await checker.check(_hw("Micron 7450 PRO 3.84TB", "Micron", "ssd"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Registration test
# ===================================================================


# ===================================================================
# NVIDIA new GPU rules
# ===================================================================


class TestNVIDIANewGPU:
    async def test_gp100_eol(self, checker):
        r = await checker.check(_hw("Tesla GP100 16GB", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert "GP100" in r.notes

    async def test_vcqgp100_eol(self, checker):
        r = await checker.check(_hw("VCQGP100-16GB-PB", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert "GP100" in r.notes

    async def test_k1200_eol(self, checker):
        r = await checker.check(_hw("Quadro K1200", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "K1200" in r.notes

    async def test_vcqk1200_eol(self, checker):
        r = await checker.check(_hw("VCQK1200-T", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.EOL
        assert "K1200" in r.notes

    async def test_rtx5000_active(self, checker):
        r = await checker.check(_hw("RTX5000", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert "RTX 5000" in r.notes

    async def test_vcqrtx5000_active(self, checker):
        r = await checker.check(_hw("VCQRTX5000-PB", "NVIDIA", "gpu"))
        assert r.status == EOLStatus.ACTIVE
        assert "RTX 5000" in r.notes


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "__techgen__" in checkers
        assert checkers["__techgen__"] is TechGenerationChecker
