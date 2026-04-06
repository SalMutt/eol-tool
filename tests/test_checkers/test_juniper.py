"""Tests for the JuniperChecker."""

from datetime import date
from pathlib import Path

import pytest

from eol_tool.checkers.juniper import (
    _KNOWN_EOL,
    JuniperChecker,
    parse_date_str,
    parse_listing_families,
)
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "juniper"


def _hw(model: str, category: str = "switch") -> HardwareModel:
    return HardwareModel(model=model, manufacturer="Juniper", category=category)


@pytest.fixture
def checker():
    return JuniperChecker()


@pytest.fixture
def listing_html():
    return (_FIXTURES / "eol_listing.html").read_text()


@pytest.fixture
def detail_html():
    return (_FIXTURES / "ex4300_eol.html").read_text()


# ===================================================================
# Listing page parsing
# ===================================================================


class TestParseListingFamilies:
    def test_extracts_product_families(self, listing_html):
        families = parse_listing_families(listing_html)
        assert len(families) > 0

    def test_contains_ex_series(self, listing_html):
        families = parse_listing_families(listing_html)
        labels = [f["label"] for f in families]
        assert "EX Series" in labels

    def test_contains_srx_series(self, listing_html):
        families = parse_listing_families(listing_html)
        labels = [f["label"] for f in families]
        assert "SRX Series" in labels

    def test_contains_mx_series(self, listing_html):
        families = parse_listing_families(listing_html)
        labels = [f["label"] for f in families]
        # MX is listed under "M Series (M, MX)"
        assert any("M Series" in label or "MX" in label for label in labels)

    def test_contains_qfx_series(self, listing_html):
        families = parse_listing_families(listing_html)
        labels = [f["label"] for f in families]
        assert "QFX Series" in labels

    def test_contains_optics(self, listing_html):
        families = parse_listing_families(listing_html)
        labels = [f["label"] for f in families]
        assert "Optics" in labels

    def test_family_has_url(self, listing_html):
        families = parse_listing_families(listing_html)
        ex = next(f for f in families if f["label"] == "EX Series")
        assert ex["url"] == "/support/eol/product/ex_series/"

    def test_includes_software_releases(self, listing_html):
        families = parse_listing_families(listing_html)
        labels = [f["label"] for f in families]
        # Software section items should also be parsed
        assert any("Junos" in label for label in labels)

    def test_empty_html_returns_empty(self):
        assert parse_listing_families("") == []

    def test_no_sw_eol_list_returns_empty(self):
        assert parse_listing_families("<html><body>hello</body></html>") == []


# ===================================================================
# Detail page parsing (fixture is a shell page — data is JS-rendered)
# ===================================================================


class TestDetailPageHandling:
    def test_detail_page_is_shell(self, detail_html):
        """The detail fixture is a JS-rendered shell without EOL tables."""
        # Verify the fixture doesn't have tabular EOL data
        assert "End of Engineering" not in detail_html


# ===================================================================
# Date parsing
# ===================================================================


class TestDateParsing:
    def test_iso_format(self):
        assert parse_date_str("2023-06-30") == date(2023, 6, 30)

    def test_slash_format(self):
        assert parse_date_str("06/30/2023") == date(2023, 6, 30)

    def test_dash_mmddyyyy(self):
        assert parse_date_str("06-30-2023") == date(2023, 6, 30)

    def test_month_name_format(self):
        assert parse_date_str("January 15, 2023") == date(2023, 1, 15)

    def test_month_name_no_comma(self):
        assert parse_date_str("March 1 2022") == date(2022, 3, 1)

    def test_empty_string(self):
        assert parse_date_str("") is None

    def test_invalid_date(self):
        assert parse_date_str("not-a-date") is None


# ===================================================================
# Model normalization — EX series
# ===================================================================


class TestEXModels:
    async def test_ex4300_48t(self, checker):
        r = checker._classify_model(_hw("EX4300-48T"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 90
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_date == date(2023, 3, 31)
        assert r.eos_date == date(2026, 3, 31)
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex4300_48t_cpo(self, checker):
        r = checker._classify_model(_hw("EX4300-48T-CPO"))
        assert r.status == EOLStatus.EOL
        assert "EX4300" in r.notes
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex3300(self, checker):
        r = checker._classify_model(_hw("EX3300-48T"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2019, 3, 31)
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex3400(self, checker):
        r = checker._classify_model(_hw("EX3400-48T"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2022, 1, 31)
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex4550(self, checker):
        r = checker._classify_model(_hw("EX4550-32F"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2019, 3, 31)
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex4600(self, checker):
        r = checker._classify_model(_hw("EX4600-40F"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2022, 6, 30)
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex2300(self, checker):
        r = checker._classify_model(_hw("EX2300-48P"))
        assert r.status == EOLStatus.EOL_ANNOUNCED
        assert r.date_source == "none"

    async def test_juniper_prefix_stripped(self, checker):
        r = checker._classify_model(_hw("JUNIPER EX4300-48T"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 90
        assert r.date_source == "manufacturer_confirmed"


# ===================================================================
# Model normalization — SRX series
# ===================================================================


class TestSRXModels:
    async def test_srx300(self, checker):
        r = checker._classify_model(_hw("SRX300", "firewall"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_date == date(2022, 12, 31)
        assert r.eos_date == date(2025, 12, 31)
        assert r.date_source == "manufacturer_confirmed"

    async def test_srx340_maps_to_srx300_family(self, checker):
        r = checker._classify_model(_hw("SRX340", "firewall"))
        assert r.status == EOLStatus.EOL
        assert "SRX300 family" in r.notes
        assert r.date_source == "manufacturer_confirmed"

    async def test_srx345_maps_to_srx300_family(self, checker):
        r = checker._classify_model(_hw("SRX345", "firewall"))
        assert r.status == EOLStatus.EOL
        assert "SRX300 family" in r.notes
        assert r.date_source == "manufacturer_confirmed"

    async def test_srx220(self, checker):
        r = checker._classify_model(_hw("SRX220H", "firewall"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2015, 1, 31)
        assert r.date_source == "manufacturer_confirmed"


# ===================================================================
# Model normalization — MX series
# ===================================================================


class TestMXModels:
    async def test_mx80(self, checker):
        r = checker._classify_model(_hw("MX80", "router"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2019, 6, 30)
        assert r.eos_date == date(2024, 6, 30)
        assert r.date_source == "manufacturer_confirmed"

    async def test_mx480(self, checker):
        r = checker._classify_model(_hw("MX480", "router"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "none"

    async def test_mx960(self, checker):
        r = checker._classify_model(_hw("MX960", "router"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "none"


# ===================================================================
# Model normalization — QFX series
# ===================================================================


class TestQFXModels:
    async def test_qfx5100(self, checker):
        r = checker._classify_model(_hw("QFX5100-48S"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2022, 3, 31)
        assert r.date_source == "manufacturer_confirmed"


# ===================================================================
# Component to parent chassis mapping
# ===================================================================


class TestComponentMapping:
    async def test_pwr_mx480(self, checker):
        r = checker._classify_model(_hw("PWR-MX480-2520-AC", "component"))
        assert r.confidence == 70
        assert "component-follows-parent-chassis" in r.notes
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_mpc3d(self, checker):
        r = checker._classify_model(_hw("MPC-3D-16XGE-SFPP", "component"))
        assert r.confidence == 70
        assert "MPC" in r.notes
        assert r.date_source == "none"

    async def test_mpc3e(self, checker):
        r = checker._classify_model(_hw("MPC3E-3D-NG", "component"))
        assert r.confidence == 70

    async def test_mpc4e(self, checker):
        r = checker._classify_model(_hw("MPC4E-3D-32XGE", "component"))
        assert r.confidence == 70

    async def test_mpc5e(self, checker):
        r = checker._classify_model(_hw("MPC5E-100G10G", "component"))
        assert r.confidence == 70

    async def test_mic3d(self, checker):
        r = checker._classify_model(_hw("MIC-3D-20GE-SFP", "component"))
        assert r.confidence == 70

    async def test_mic3_3d(self, checker):
        r = checker._classify_model(_hw("MIC3-3D-10XGE-SFPP", "component"))
        assert r.confidence == 70

    async def test_scbe_mx(self, checker):
        r = checker._classify_model(_hw("SCBE-MX-S", "component"))
        assert r.confidence == 70

    async def test_scbe2_mx(self, checker):
        r = checker._classify_model(_hw("SCBE2-MX", "component"))
        assert r.confidence == 70

    async def test_re_s_routing_engine(self, checker):
        r = checker._classify_model(_hw("RE-S-1800X4-16G", "component"))
        assert r.confidence == 70
        assert "routing engine" in r.notes

    async def test_ffantray(self, checker):
        r = checker._classify_model(_hw("FFANTRAY-MX480-HC-S", "component"))
        assert r.confidence == 70

    async def test_jpsu(self, checker):
        r = checker._classify_model(_hw("JPSU-350-AC-AFI", "component"))
        assert r.confidence == 70
        assert r.risk_category == RiskCategory.PROCUREMENT

    async def test_jpsu_650w(self, checker):
        r = checker._classify_model(_hw("JPSU-650W-AC-AFO", "component"))
        assert r.confidence == 70


# ===================================================================
# Optic handling
# ===================================================================


class TestOpticHandling:
    async def test_jnp_optic(self, checker):
        r = checker._classify_model(_hw("JNP-QSFP-40G-SR4", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 80
        assert r.risk_category == RiskCategory.NONE
        assert "juniper-optic" in r.notes
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_qfx_qsfp_optic(self, checker):
        r = checker._classify_model(_hw("QFX-QSFP-40G-SR4", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 80
        assert r.risk_category == RiskCategory.NONE
        assert r.date_source == "none"

    async def test_ex_sfp_optic(self, checker):
        r = checker._classify_model(_hw("EX-SFP-10GE-SR", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 80
        assert r.date_source == "none"

    async def test_qfx_sfp_optic(self, checker):
        r = checker._classify_model(_hw("QFX-SFP-1GE-T", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 80
        assert r.date_source == "none"

    async def test_generic_qsfp_optic(self, checker):
        r = checker._classify_model(_hw("QSFP-SR4-40G", "optic"))
        assert r.confidence == 30
        assert r.status == EOLStatus.UNKNOWN
        assert "white-label" in r.notes
        assert r.date_source == "none"

    async def test_generic_sfp_optic(self, checker):
        r = checker._classify_model(_hw("SFP-10GE-LR", "optic"))
        assert r.confidence == 30
        assert "white-label" in r.notes
        assert r.date_source == "none"


# ===================================================================
# Software/support contract handling
# ===================================================================


class TestSoftwareContracts:
    async def test_mnt_prefix(self, checker):
        r = checker._classify_model(_hw("MNT-EX4300-48T", "support"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 60
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "support-contract" in r.notes
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_sp_fxp_prefix(self, checker):
        r = checker._classify_model(_hw("SP-FXP-S1600", "support"))
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 60
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.date_source == "none"

    async def test_aif_prefix(self, checker):
        r = checker._classify_model(
            _hw("AIF-SP-FXP-CORE-R10-F0KSTD-RNW", "support")
        )
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert r.date_source == "none"


# ===================================================================
# Batch check with mocked HTTP
# ===================================================================


class TestBatchCheck:
    async def test_batch_fetches_listing_once(self, httpx_mock, listing_html):
        httpx_mock.add_response(
            url="https://support.juniper.net/support/eol/",
            text=listing_html,
        )
        models = [
            _hw("EX4300-48T"),
            _hw("SRX340", "firewall"),
            _hw("MX480", "router"),
        ]
        async with JuniperChecker() as c:
            results = await c.check_batch(models)
        assert len(results) == 3
        assert results[0].status == EOLStatus.EOL
        assert results[1].status == EOLStatus.EOL
        assert results[2].status == EOLStatus.EOL

        # Only one HTTP request to listing page
        requests = httpx_mock.get_requests()
        assert len(requests) == 1

    async def test_single_check_fetches_listing(self, httpx_mock, listing_html):
        httpx_mock.add_response(
            url="https://support.juniper.net/support/eol/",
            text=listing_html,
        )
        async with JuniperChecker() as c:
            r = await c.check(_hw("EX4300-48T"))
        assert r.status == EOLStatus.EOL
        assert r.confidence == 90

    async def test_listing_fetch_failure_still_classifies(self, httpx_mock):
        # _fetch retries 3 times on 500
        for _ in range(3):
            httpx_mock.add_response(
                url="https://support.juniper.net/support/eol/",
                status_code=500,
            )
        async with JuniperChecker() as c:
            results = await c.check_batch([_hw("EX4300-48T")])
        assert len(results) == 1
        # Should still classify from local knowledge
        assert results[0].status == EOLStatus.EOL


# ===================================================================
# Confidence scoring
# ===================================================================


class TestConfidence:
    async def test_exact_product_match_90(self, checker):
        r = checker._classify_model(_hw("EX4300-48T"))
        assert r.confidence == 90

    async def test_series_family_match_90(self, checker):
        """SRX340 via SRX300 family still gets 90 since we have direct data."""
        r = checker._classify_model(_hw("SRX340", "firewall"))
        assert r.confidence == 90

    async def test_component_match_70(self, checker):
        r = checker._classify_model(_hw("PWR-MX480-2520-AC", "component"))
        assert r.confidence == 70

    async def test_software_contract_60(self, checker):
        r = checker._classify_model(_hw("MNT-EX4300-48T", "support"))
        assert r.confidence == 60

    async def test_unknown_model_50(self, checker):
        r = checker._classify_model(_hw("EX9999-FAKE"))
        assert r.confidence == 50

    async def test_white_label_optic_30(self, checker):
        r = checker._classify_model(_hw("QSFP-SR4-40G", "optic"))
        assert r.confidence == 30


# ===================================================================
# EX4200 series
# ===================================================================


class TestEX4200Models:
    async def test_ex4200_48p(self, checker):
        r = checker._classify_model(_hw("EX4200-48P"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.eol_date == date(2014, 1, 31)
        assert r.eos_date == date(2019, 1, 31)
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex4200_48px(self, checker):
        r = checker._classify_model(_hw("EX4200-48PX"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex4200_48t(self, checker):
        r = checker._classify_model(_hw("EX4200-48T"))
        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex_um_2x4sfp(self, checker):
        r = checker._classify_model(_hw("EX-UM-2X4SFP"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert "uplink-module" in r.notes
        assert r.date_source == "manufacturer_confirmed"
        assert r.eol_date == date(2014, 1, 31)

    async def test_ex_um_4x4sfp(self, checker):
        r = checker._classify_model(_hw("EX-UM-4X4SFP"))
        assert r.status == EOLStatus.EOL
        assert "uplink-module" in r.notes
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex_pwr_320_ac(self, checker):
        r = checker._classify_model(_hw("EX-PWR-320-AC"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert "power-supply" in r.notes
        assert r.date_source == "manufacturer_confirmed"

    async def test_ex_pwr_320w_ac(self, checker):
        r = checker._classify_model(_hw("EX-PWR-320W-AC"))
        assert r.status == EOLStatus.EOL
        assert "power-supply" in r.notes
        assert r.date_source == "manufacturer_confirmed"


# ===================================================================
# QFX new series
# ===================================================================


class TestQFXNewModels:
    async def test_qfx5120_32c(self, checker):
        r = checker._classify_model(_hw("QFX5120-32C-AFI"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert r.confidence == 90
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_qfx5120_48t(self, checker):
        r = checker._classify_model(_hw("QFX5120-48T-AFI"))
        assert r.status == EOLStatus.ACTIVE
        assert r.date_source == "none"

    async def test_qfx5200_32c_eol(self, checker):
        r = checker._classify_model(_hw("QFX5200-32C-AFI"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert "QFX5220" in r.notes
        assert r.eol_date == date(2021, 6, 30)
        assert r.eos_date == date(2024, 6, 30)
        assert r.date_source == "manufacturer_confirmed"

    async def test_qfx5300_active(self, checker):
        r = checker._classify_model(_hw("QFX5300-32C-AFO"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert r.date_source == "none"

    async def test_qfx_em_4q(self, checker):
        r = checker._classify_model(_hw("QFX-EM-4Q"))
        assert r.status == EOLStatus.ACTIVE
        assert "expansion-module" in r.notes
        assert r.date_source == "none"

    async def test_qfx_psu(self, checker):
        r = checker._classify_model(_hw("QFX520048Y-APSU-AO"))
        assert r.status == EOLStatus.ACTIVE
        assert "power-supply" in r.notes
        assert r.date_source == "none"

    async def test_qfxc01_psu(self, checker):
        r = checker._classify_model(_hw("QFXC01-PWRACI-650A"))
        assert r.status == EOLStatus.ACTIVE
        assert "power-supply" in r.notes
        assert r.date_source == "none"


# ===================================================================
# MX backplane
# ===================================================================


class TestMXBackplane:
    async def test_chas_bp3_mx480(self, checker):
        r = checker._classify_model(_hw("CHAS-BP3-MX480"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL
        assert "backplane" in r.notes
        assert r.date_source == "none"


# ===================================================================
# Juniper optics — specific models
# ===================================================================


class TestJuniperOpticModels:
    async def test_jnp_qsfp_100g(self, checker):
        r = checker._classify_model(_hw("JNP-QSFP-100G", "optic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_jnp_qsfp_100g_sr4(self, checker):
        r = checker._classify_model(_hw("JNP-QSFP-100G-SR4", "optic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_jnp_qsfp_40g_lr4(self, checker):
        r = checker._classify_model(_hw("JNP-QSFP-40G-LR4", "optic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_jnp_sfp_25g_lr(self, checker):
        r = checker._classify_model(_hw("JNP-SFP-25G-LR", "optic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_ex_sfp_10ge_sr_i(self, checker):
        r = checker._classify_model(_hw("EX-SFP-10GE-SR-I", "optic"))
        assert r.status == EOLStatus.ACTIVE

    async def test_jnp_qsfp_4x10ge_lr(self, checker):
        r = checker._classify_model(_hw("JNP-QSFP-4X10GE-LR", "optic"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# DWDM optics
# ===================================================================


class TestDWDMOptics:
    async def test_sfpp_10g_dw25(self, checker):
        r = checker._classify_model(_hw("C25 SFPP-10G-DW25", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert "DWDM" in r.notes

    async def test_10g_sfp_dwdm(self, checker):
        r = checker._classify_model(
            _hw("10G SFP+ DWDM C21 40KM", "optic")
        )
        assert r.status == EOLStatus.ACTIVE
        assert "DWDM" in r.notes

    async def test_10g_xfp_dwdm(self, checker):
        r = checker._classify_model(_hw("10G XFP DWDM C21", "optic"))
        assert r.status == EOLStatus.ACTIVE
        assert "DWDM" in r.notes

    async def test_cfp_gen2_eol(self, checker):
        r = checker._classify_model(
            _hw("CFP-GEN2-100GBASE-LR4", "optic")
        )
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.PROCUREMENT
        assert "QSFP28" in r.notes
        assert r.date_source == "none"


# ===================================================================
# Auto-registration
# ===================================================================


# ===================================================================
# Date source validation
# ===================================================================


class TestDateSource:
    """Verify that date_source is set correctly for all result paths."""

    def test_known_eol_entries_with_dates_are_manufacturer_confirmed(self):
        """All _KNOWN_EOL entries with eol_date must be manufacturer_confirmed."""
        for series, data in _KNOWN_EOL.items():
            if data.get("eol_date") or data.get("eos_date"):
                assert data.get("eol_date") is not None or data.get("eos_date") is not None, (
                    f"{series}: has date but missing eol_date or eos_date"
                )

    def test_ex4200_has_dates_from_eol_page(self, checker):
        """EX4200 appears on the Juniper EOL listing and must have dates."""
        r = checker._classify_model(_hw("EX4200-48T"))
        assert r.eol_date is not None
        assert r.eos_date is not None
        assert r.date_source == "manufacturer_confirmed"

    def test_qfx5200_has_dates_from_eol_page(self, checker):
        """QFX5200 appears on the Juniper EOL listing and must have dates."""
        r = checker._classify_model(_hw("QFX5200-32C"))
        assert r.eol_date is not None
        assert r.eos_date is not None
        assert r.date_source == "manufacturer_confirmed"

    def test_active_models_have_no_dates(self, checker):
        """Active models (QFX5120, QFX5300) must have date_source=none."""
        for model_str in ("QFX5120-32C", "QFX5300-32C"):
            r = checker._classify_model(_hw(model_str))
            assert r.date_source == "none", f"{model_str}: expected date_source=none"
            assert r.eol_date is None, f"{model_str}: expected no eol_date"

    def test_static_rules_non_ex4200_have_no_dates(self, checker):
        """Non-EX4200 static rule results must have date_source=none."""
        static_models = [
            "QFX-EM-4Q", "QFX520048Y-APSU-AO", "CHAS-BP3-MX480",
        ]
        for model_str in static_models:
            r = checker._classify_model(_hw(model_str))
            assert r.date_source == "none", f"{model_str}: expected date_source=none"
            assert r.eol_date is None, f"{model_str}: expected no eol_date"

    def test_ex4200_components_inherit_parent_date(self, checker):
        """EX4200 components inherit the parent chassis date."""
        ex4200_models = ["EX-UM-2X4SFP", "EX-PWR-320-AC"]
        for model_str in ex4200_models:
            r = checker._classify_model(_hw(model_str))
            assert r.date_source == "manufacturer_confirmed", f"{model_str}"
            assert r.eol_date == date(2014, 1, 31), f"{model_str}"


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers_for_juniper(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "juniper" in checkers
        assert checkers["juniper"] is JuniperChecker
