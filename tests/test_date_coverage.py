"""Tests for EOL date coverage across all checkers.

Ensures:
- No checker returns date_source="approximate" anywhere
- Verified dates are correct (Dell, Brocade, EVGA, OCZ, Hitachi)
- Unverifiable dates are None (DDR3 memory, Samsung consumer SSDs, Seagate, etc.)
- Juniper component date propagation works
- Status is still correctly determined even when date is None
"""

import ast
import pathlib
from datetime import date

import pytest

from eol_tool.checkers.amd import AMDChecker
from eol_tool.checkers.broadcom import BroadcomChecker
from eol_tool.checkers.dell import DellChecker
from eol_tool.checkers.intel import IntelChecker
from eol_tool.checkers.juniper import JuniperChecker
from eol_tool.checkers.kingston import KingstonChecker
from eol_tool.checkers.micron import MicronChecker
from eol_tool.checkers.samsung import SamsungChecker
from eol_tool.checkers.seagate import SeagateChecker
from eol_tool.checkers.supermicro import SupermicroChecker
from eol_tool.checkers.tech_generation import TechGenerationChecker
from eol_tool.checkers.wd import WDChecker
from eol_tool.models import EOLStatus, HardwareModel


def _model(model: str, manufacturer: str, category: str) -> HardwareModel:
    return HardwareModel(
        model=model, manufacturer=manufacturer, category=category,
    )


# ── Meta-test: no checker uses "approximate" anywhere ────────────────────


def test_no_approximate_in_any_checker():
    """Scan all checker source files to ensure 'approximate' never appears."""
    checkers_dir = pathlib.Path(__file__).resolve().parent.parent / "src" / "eol_tool" / "checkers"
    for py_file in checkers_dir.glob("*.py"):
        source = py_file.read_text()
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "approximate":
                pytest.fail(
                    f'{py_file.name}:{node.lineno} contains '
                    f'string literal "approximate"'
                )


# ── Verified dates: community database (Dell) ─────────────────────────


@pytest.mark.asyncio
async def test_dell_r630_verified_date():
    checker = DellChecker()
    result = await checker.check(_model("PowerEdge R630", "Dell", "server"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2020, 8, 17)
    assert result.eos_date == date(2023, 8, 17)
    assert result.date_source == "community_database"


@pytest.mark.asyncio
async def test_dell_r730xd_verified_date():
    checker = DellChecker()
    result = await checker.check(_model("PowerEdge R730XD", "Dell", "server"))
    assert result.eol_date == date(2020, 8, 17)
    assert result.date_source == "community_database"


@pytest.mark.asyncio
async def test_dell_perc_h700_verified_date():
    checker = DellChecker()
    result = await checker.check(_model("H700", "Dell", "raid-controller"))
    assert result.eol_date == date(2018, 2, 8)
    assert result.date_source == "community_database"


# ── Verified dates: community database (acquisitions/exits) ──────────────


@pytest.mark.asyncio
async def test_brocade_acquisition_date():
    checker = TechGenerationChecker()
    result = await checker.check(_model("ICX6610-24", "Brocade", "switch"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2017, 11, 17)
    assert result.date_source == "community_database"


@pytest.mark.asyncio
async def test_evga_exit_date():
    checker = TechGenerationChecker()
    result = await checker.check(_model("GTX 1080 Ti", "EVGA", "gpu"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2022, 9, 16)
    assert result.date_source == "community_database"


@pytest.mark.asyncio
async def test_ocz_acquisition_date():
    checker = TechGenerationChecker()
    result = await checker.check(_model("Vector 150", "OCZ", "ssd"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2014, 1, 21)
    assert result.date_source == "community_database"


@pytest.mark.asyncio
async def test_hitachi_acquisition_date():
    checker = TechGenerationChecker()
    result = await checker.check(_model("HDS721010CLA332", "Hitachi", "hdd"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2012, 3, 8)
    assert result.date_source == "community_database"


# ── EOL status with no date (status from generation rules) ──────────────


@pytest.mark.asyncio
async def test_ddr3_sk_hynix_eol_no_date():
    checker = TechGenerationChecker()
    result = await checker.check(_model("HMT351U6CFR8C-PB", "SK Hynix", "memory"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_samsung_860_evo_eol_no_date():
    checker = SamsungChecker()
    result = await checker.check(_model("860 EVO 500GB", "Samsung", "ssd"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_seagate_legacy_drive_eol_no_date():
    checker = SeagateChecker()
    m = HardwareModel(
        model="ST4000NM0033", manufacturer="Seagate", category="hdd",
        original_item="4TB Seagate ENT ST4000NM0033",
    )
    result = await checker.check(m)
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_wd_re_eol_no_date():
    checker = WDChecker()
    result = await checker.check(_model("WD2003FYYZ", "WD", "hdd"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_broadcom_9260_eol_no_date():
    checker = BroadcomChecker()
    result = await checker.check(_model("9260-8i", "Broadcom", "raid-controller"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_micron_5200_eol_no_date():
    checker = MicronChecker()
    result = await checker.check(_model("5200 ECO 960GB", "Micron", "ssd"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_kingston_ddr3_eol_no_date():
    checker = KingstonChecker()
    result = await checker.check(_model("KVR16R11D4/16", "Kingston", "memory"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_samsung_ddr3_eol_no_date():
    checker = SamsungChecker()
    result = await checker.check(_model("M393B1G70QH0-YK0", "Samsung", "memory"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_supermicro_x9_eol_no_date():
    checker = SupermicroChecker()
    result = await checker.check(_model("X9SCM-F", "Supermicro", "server-board"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


@pytest.mark.asyncio
async def test_amd_epyc_7001_eol_no_date():
    checker = AMDChecker()
    result = await checker.check(_model("EPYC 7551", "AMD", "cpu"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date is None
    assert result.date_source == "none"


# ── Juniper component date propagation ──────────────────────────────────


@pytest.mark.asyncio
async def test_juniper_ex4200_psu_inherits_parent_date():
    checker = JuniperChecker()
    checker._listing_families = []
    result = await checker.check(_model("EX-PWR-320-AC", "Juniper", "power-supply"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2014, 1, 31)
    assert result.date_source == "manufacturer_confirmed"


# ── Xeon E-2xxx and Scalable 3rd/4th gen (active, no date) ──────────────


@pytest.mark.asyncio
async def test_xeon_e2236_active():
    checker = TechGenerationChecker()
    result = await checker.check(_model("Xeon E-2236", "Intel", "cpu"))
    assert result.status == EOLStatus.ACTIVE
    assert "E-2200" in result.notes


@pytest.mark.asyncio
async def test_xeon_silver_4310_active():
    checker = TechGenerationChecker()
    result = await checker.check(_model("Xeon Silver 4310", "Intel", "cpu"))
    assert result.status == EOLStatus.ACTIVE
    assert "3rd gen" in result.notes


@pytest.mark.asyncio
async def test_xeon_gold_5412u_active():
    checker = TechGenerationChecker()
    result = await checker.check(_model("Xeon Gold 5412U", "Intel", "cpu"))
    assert result.status == EOLStatus.ACTIVE
    assert "4th gen" in result.notes


# ── Intel NIC verified date still works ──────────────────────────────────


@pytest.mark.asyncio
async def test_intel_x520_community_database():
    checker = IntelChecker()
    result = await checker.check(_model("X520-DA2", "Intel", "nic"))
    assert result.status == EOLStatus.EOL
    assert result.eol_date == date(2021, 7, 1)
    assert result.date_source == "community_database"
