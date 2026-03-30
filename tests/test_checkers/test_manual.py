"""Tests for the ManualChecker."""

import csv
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from eol_tool.checkers.manual import ManualChecker
from eol_tool.models import (
    EOLReason,
    EOLStatus,
    HardwareModel,
    RiskCategory,
)


def _hw(model: str, manufacturer: str = "", category: str = "") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "model", "manufacturer", "status", "eol_reason", "risk_category",
        "eol_date", "eos_date", "source_url", "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.fixture
def checker():
    """ManualChecker loaded from the real CSV."""
    return ManualChecker()


@pytest.fixture
def tmp_checker(tmp_path):
    """Create a ManualChecker with a custom CSV for controlled testing."""
    csv_path = tmp_path / "overrides.csv"
    _write_csv(csv_path, [
        {
            "model": "EX4300",
            "manufacturer": "Juniper",
            "status": "eol",
            "eol_reason": "product_discontinued",
            "risk_category": "support",
            "eol_date": "2024-06-15",
            "eos_date": "2025-06-15",
            "source_url": "https://example.com/eol",
            "notes": "test-eol-entry",
        },
        {
            "model": "SFP-10G-SR",
            "manufacturer": "",
            "status": "unknown",
            "eol_reason": "none",
            "risk_category": "procurement",
            "eol_date": "",
            "eos_date": "",
            "source_url": "",
            "notes": "white-label-optic",
        },
        {
            "model": "ACTIVE-DEVICE",
            "manufacturer": "TestCo",
            "status": "active",
            "eol_reason": "none",
            "risk_category": "none",
            "eol_date": "",
            "eos_date": "",
            "source_url": "",
            "notes": "test-active",
        },
    ])
    with patch("eol_tool.checkers.manual._CSV_PATH", csv_path):
        return ManualChecker()


# ===================================================================
# Loading and exact matching
# ===================================================================


class TestExactMatch:
    async def test_exact_match_returns_correct_status(self, tmp_checker):
        r = await tmp_checker.check(_hw("EX4300", "Juniper", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.notes == "test-eol-entry"

    async def test_exact_match_maps_all_fields(self, tmp_checker):
        r = await tmp_checker.check(_hw("EX4300", "Juniper", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2024, 6, 15)
        assert r.eos_date == date(2025, 6, 15)
        assert r.source_url == "https://example.com/eol"
        assert r.eol_reason == EOLReason.MANUAL_OVERRIDE
        assert r.risk_category == RiskCategory.SUPPORT
        assert r.confidence == 80
        assert r.source_name == "manual-overrides"

    async def test_active_status(self, tmp_checker):
        r = await tmp_checker.check(_hw("ACTIVE-DEVICE", "TestCo", "misc"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Partial model matching
# ===================================================================


class TestPartialMatch:
    async def test_partial_prefix_match(self, tmp_checker):
        """CSV model 'EX4300' should match input 'EX4300-48T'."""
        r = await tmp_checker.check(_hw("EX4300-48T", "Juniper", "switch"))
        assert r.status == EOLStatus.EOL
        assert r.notes == "test-eol-entry"

    async def test_partial_match_longer_suffix(self, tmp_checker):
        """CSV model 'EX4300' should match input 'EX4300-48T-CPO'."""
        r = await tmp_checker.check(_hw("EX4300-48T-CPO", "Juniper", "switch"))
        assert r.status == EOLStatus.EOL

    async def test_partial_match_sfp(self, tmp_checker):
        """CSV model 'SFP-10G-SR' should match 'SFP-10G-SR-EXTENDED'."""
        r = await tmp_checker.check(_hw("SFP-10G-SR-EXTENDED"))
        assert r.notes == "white-label-optic"


# ===================================================================
# Case-insensitive matching
# ===================================================================


class TestCaseInsensitive:
    async def test_lowercase_input(self, tmp_checker):
        r = await tmp_checker.check(_hw("ex4300", "Juniper", "switch"))
        assert r.status == EOLStatus.EOL

    async def test_mixed_case_input(self, tmp_checker):
        r = await tmp_checker.check(_hw("Ex4300-48t", "Juniper", "switch"))
        assert r.status == EOLStatus.EOL

    async def test_uppercase_input(self, tmp_checker):
        r = await tmp_checker.check(_hw("ACTIVE-DEVICE", "TestCo", "misc"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Unmatched model returns UNKNOWN
# ===================================================================


class TestUnmatched:
    async def test_unmatched_returns_unknown(self, tmp_checker):
        r = await tmp_checker.check(_hw("TOTALLY-UNKNOWN-MODEL", "Nobody", "widget"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 0
        assert r.notes == "no-automated-checker-available"
        assert r.source_name == "manual-overrides"

    async def test_unmatched_no_eol_reason(self, tmp_checker):
        r = await tmp_checker.check(_hw("NOPE-123"))
        assert r.eol_reason == EOLReason.NONE


# ===================================================================
# Real CSV loading tests
# ===================================================================


@pytest.mark.skipif(
    ManualChecker()._entries == [],
    reason="manual_overrides.csv has no data rows (inventory data removed)",
)
class TestRealCSV:
    def test_csv_has_at_least_40_entries(self, checker):
        assert len(checker._entries) >= 40

    async def test_real_csv_hitachi_match(self, checker):
        r = await checker.check(_hw("2TB HITACHI 0F12470", "Hitachi", "hdd"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.MANUAL_OVERRIDE
        assert "hitachi-legacy-enterprise-HDD-brand-now-HGST-WD" in r.notes

    async def test_real_csv_ibm_match(self, checker):
        r = await checker.check(_hw("M5210", "IBM", "raid"))
        assert r.status == EOLStatus.EOL
        assert "IBM-ServeRAID-M5210-legacy-RAID" in r.notes

    async def test_real_csv_chenbro_match(self, checker):
        r = await checker.check(_hw("RB23812E3RP8", "Chenbro", "chassis"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.INFORMATIONAL

    async def test_real_csv_white_label_optic(self, checker):
        r = await checker.check(_hw("QSFP-SR4-40G"))
        assert r.notes == "white-label-optic-commodity-still-available"

    async def test_real_csv_partial_qsfp_match(self, checker):
        """QSFP-SR4-40G in CSV should match via partial prefix."""
        r = await checker.check(_hw("QSFP-SR4-40G-EXTENDED"))
        assert r.notes == "white-label-optic-commodity-still-available"

    async def test_real_csv_server_config(self, checker):
        r = await checker.check(_hw("SERVER BAREBONE"))
        assert "generic-barebone-category-not-specific-product" in r.notes

    async def test_real_csv_hpe_active(self, checker):
        r = await checker.check(_hw("HPE QSFP-SR4-100G", "HPE", "optic"))
        assert r.status == EOLStatus.ACTIVE


# ===================================================================
# Registration
# ===================================================================


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "__manual__" in checkers
        assert checkers["__manual__"] is ManualChecker
