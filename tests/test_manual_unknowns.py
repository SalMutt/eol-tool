"""Tests for manual override entries that resolve previously-unknown models."""

import pytest

from eol_tool.checkers.manual import ManualChecker
from eol_tool.models import EOLStatus, HardwareModel, RiskCategory


@pytest.fixture
def checker():
    return ManualChecker()


def _hw(model: str, manufacturer: str = "", category: str = "unknown") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


@pytest.mark.asyncio
async def test_adata_su650_active(checker):
    result = await checker.check(_hw("SU650 SATA3 2.5", "ADATA"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_samsung_883_dct_eol(checker):
    result = await checker.check(_hw("883 DCT", "Samsung"))
    assert result.status == EOLStatus.EOL


@pytest.mark.asyncio
async def test_supermicro_rsc_w_66g4_active(checker):
    result = await checker.check(_hw("RSC-W-66G4 RISER", "Supermicro"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_kingston_sl16d316_eol(checker):
    result = await checker.check(_hw("SL16D316R11D4KF", "Kingston"))
    assert result.status == EOLStatus.EOL
    assert result.risk_category == RiskCategory.PROCUREMENT


@pytest.mark.asyncio
async def test_dell_m2_unknown(checker):
    result = await checker.check(_hw("M.2", "Dell"))
    assert result.status == EOLStatus.UNKNOWN


@pytest.mark.asyncio
async def test_chenbro_rb23812_active(checker):
    result = await checker.check(_hw("RB23812E3RP8", "Chenbro"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_hpe_mb4000fcwdk_eol(checker):
    result = await checker.check(_hw("HP MB4000FCWDK", "HPE"))
    assert result.status == EOLStatus.EOL
    assert result.risk_category == RiskCategory.PROCUREMENT


@pytest.mark.asyncio
async def test_wd_green_sata_active(checker):
    result = await checker.check(_hw("GREEN SATA3 2.5", "WD"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_intel_sfp_10gsr_active(checker):
    result = await checker.check(_hw("SFP-10GSR-85", "Intel"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_corsair_ddr5_active(checker):
    result = await checker.check(_hw("CP2K48G56C46U5", "Corsair"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_transcend_ssd225s_active(checker):
    result = await checker.check(_hw("SSD225S", "Transcend"))
    assert result.status == EOLStatus.ACTIVE


@pytest.mark.asyncio
async def test_pny_optima_eol(checker):
    result = await checker.check(_hw("OPTIMA", "PNY"))
    assert result.status == EOLStatus.EOL
