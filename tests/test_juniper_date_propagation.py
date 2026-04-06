"""Tests for Juniper component date propagation.

Components (power supplies, fan trays, line cards, etc.) that follow a parent
chassis should inherit the parent's scraped EOL dates when available.
"""

from datetime import date

import pytest

from eol_tool.checkers.juniper import JuniperChecker
from eol_tool.models import EOLStatus, HardwareModel


def _hw(model: str, category: str = "component") -> HardwareModel:
    return HardwareModel(model=model, manufacturer="Juniper", category=category)


@pytest.fixture
def checker():
    return JuniperChecker()


class TestEX4200ComponentPropagation:
    """EX4200 components inherit eol_date=2014-01-31, eos_date=2019-01-31."""

    def test_ex_pwr_320_ac_inherits_eol_date(self, checker):
        r = checker._classify_model(_hw("EX-PWR-320-AC"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2014, 1, 31)
        assert r.eos_date == date(2019, 1, 31)
        assert r.date_source == "manufacturer_confirmed"

    def test_ex_pwr_320w_ac_inherits_eol_date(self, checker):
        r = checker._classify_model(_hw("EX-PWR-320W-AC"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2014, 1, 31)
        assert r.date_source == "manufacturer_confirmed"

    def test_ex_um_2x4sfp_inherits_ex4200_dates(self, checker):
        r = checker._classify_model(_hw("EX-UM-2X4SFP"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2014, 1, 31)
        assert r.eos_date == date(2019, 1, 31)
        assert r.date_source == "manufacturer_confirmed"

    def test_ex_um_4x4sfp_inherits_ex4200_dates(self, checker):
        r = checker._classify_model(_hw("EX-UM-4X4SFP"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2014, 1, 31)
        assert r.date_source == "manufacturer_confirmed"


class TestEX4300ComponentPropagation:
    """EX4300/QFX JPSU-650W components inherit eol_date=2023-03-31."""

    def test_jpsu_650w_ac_afi_inherits_ex4300_date(self, checker):
        r = checker._classify_model(_hw("JPSU-650W-AC-AFI"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2023, 3, 31)
        assert r.eos_date == date(2026, 3, 31)
        assert r.date_source == "manufacturer_confirmed"

    def test_jpsu_650w_ac_afo_inherits_ex4300_date(self, checker):
        r = checker._classify_model(_hw("JPSU-650W-AC-AFO"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2023, 3, 31)
        assert r.date_source == "manufacturer_confirmed"

    def test_jpsu_650w_ac_ao_inherits_ex4300_date(self, checker):
        r = checker._classify_model(_hw("JPSU-650W-AC-AO"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2023, 3, 31)
        assert r.date_source == "manufacturer_confirmed"


class TestQFX5100ComponentPropagation:
    """QFX5100 JPSU-350 components inherit eol_date=2022-03-31."""

    def test_jpsu_350_ac_afi_inherits_qfx5100_date(self, checker):
        r = checker._classify_model(_hw("JPSU-350-AC-AFI"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2022, 3, 31)
        assert r.eos_date == date(2025, 3, 31)
        assert r.date_source == "manufacturer_confirmed"


class TestMXComponentPropagation:
    """MX components use parent MX date if available (MX480/MX960 have no date)."""

    def test_pwr_mx480_no_date_when_parent_has_none(self, checker):
        r = checker._classify_model(_hw("PWR-MX480-2520-AC"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date is None
        assert r.date_source == "none"

    def test_mpc3d_no_date_when_parent_unknown(self, checker):
        r = checker._classify_model(_hw("MPC-3D-16XGE-SFPP"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date is None
        assert r.date_source == "none"

    def test_ffantray_mx480_no_date(self, checker):
        r = checker._classify_model(_hw("FFANTRAY-MX480-HC-S"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date is None
        assert r.date_source == "none"

    def test_re_s_routing_engine_no_date(self, checker):
        r = checker._classify_model(_hw("RE-S-1800X4-16G"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date is None
        assert r.date_source == "none"


class TestActiveComponentsNotPropagated:
    """Active components must NOT receive a propagated EOL date."""

    def test_qfx_em_4q_stays_active_no_date(self, checker):
        r = checker._classify_model(_hw("QFX-EM-4Q"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_date is None
        assert r.date_source == "none"

    def test_qfx_psu_stays_active_no_date(self, checker):
        r = checker._classify_model(_hw("QFX520048Y-APSU-AO"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_date is None
        assert r.date_source == "none"

    def test_chas_bp3_mx480_stays_active_no_date(self, checker):
        r = checker._classify_model(_hw("CHAS-BP3-MX480"))
        assert r.status == EOLStatus.ACTIVE
        assert r.eol_date is None
        assert r.date_source == "none"
