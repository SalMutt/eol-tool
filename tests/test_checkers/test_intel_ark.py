"""Tests for IntelARKChecker."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory

pytestmark = pytest.mark.playwright


def _hw(model: str, category: str = "cpu", manufacturer: str = "Intel") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Graceful handling when playwright is not installed
# ===================================================================


class TestPlaywrightNotInstalled:
    async def test_returns_not_found_when_playwright_missing(self):
        with patch.dict(
            "eol_tool.checkers.intel_ark.__dict__",
            {"PLAYWRIGHT_AVAILABLE": False},
        ):
            from eol_tool.checkers.intel_ark import IntelARKChecker

            checker = IntelARKChecker()
            r = await checker.check(_hw("E5-2683 v4"))
            assert r.status == EOLStatus.NOT_FOUND
            assert "playwright" in r.notes.lower()


# ===================================================================
# Non-CPU models return NOT_FOUND
# ===================================================================


class TestNonCPU:
    async def test_nic_returns_not_found(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        r = await checker.check(_hw("X520-DA2", category="nic"))
        assert r.status == EOLStatus.NOT_FOUND
        assert "non-cpu" in r.notes

    async def test_ssd_returns_not_found(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        r = await checker.check(_hw("660P", category="ssd"))
        assert r.status == EOLStatus.NOT_FOUND

    async def test_optic_returns_not_found(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        r = await checker.check(_hw("SFP-10GSR-85", category="optic"))
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# Result parsing from mocked data
# ===================================================================


class TestResultParsing:
    def test_discontinued_maps_to_eol(self):
        from eol_tool.checkers.intel_ark import _to_result

        model = _hw("E5-2683 v4")
        data = {
            "marketing_status": "Discontinued",
            "launch_date": "Q1'16",
            "eol_date": "Thursday June 30 2022",
        }
        r = _to_result(model, data)
        assert r.status == EOLStatus.EOL
        assert r.confidence == 90
        assert r.date_source == "manufacturer_confirmed"
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.SUPPORT

    def test_launched_maps_to_active(self):
        from eol_tool.checkers.intel_ark import _to_result

        model = _hw("Gold 6426Y")
        data = {"marketing_status": "Launched", "launch_date": "Q1'23"}
        r = _to_result(model, data)
        assert r.status == EOLStatus.ACTIVE
        assert r.confidence == 90
        assert r.risk_category == RiskCategory.NONE

    def test_eol_date_parsed(self):
        from eol_tool.checkers.intel_ark import _to_result

        model = _hw("E5-2683 v4")
        data = {
            "marketing_status": "Discontinued",
            "eol_date": "June 30, 2022",
        }
        r = _to_result(model, data)
        assert r.eol_date is not None
        assert r.eol_date.year == 2022
        assert r.eol_date.month == 6
        assert r.eol_date.day == 30

    def test_not_found_cached_result(self):
        from eol_tool.checkers.intel_ark import _to_result

        model = _hw("MYSTERY-CPU")
        r = _to_result(model, {"result_status": "not_found"})
        assert r.status == EOLStatus.NOT_FOUND

    def test_end_of_life_marketing_status(self):
        from eol_tool.checkers.intel_ark import _to_result

        model = _hw("OLD-XEON")
        data = {"marketing_status": "End of Life"}
        r = _to_result(model, data)
        assert r.status == EOLStatus.EOL


# ===================================================================
# Date parsing
# ===================================================================


class TestDateParsing:
    def test_full_date_with_comma(self):
        from eol_tool.checkers.intel_ark import _parse_date

        d = _parse_date("June 30, 2022")
        assert d is not None
        assert d.year == 2022
        assert d.month == 6

    def test_full_date_without_comma(self):
        from eol_tool.checkers.intel_ark import _parse_date

        d = _parse_date("June 30 2022")
        assert d is not None
        assert d.year == 2022

    def test_day_name_date(self):
        from eol_tool.checkers.intel_ark import _parse_date

        d = _parse_date("Thursday June 30 2022")
        assert d is not None
        assert d.year == 2022

    def test_quarter_format(self):
        from eol_tool.checkers.intel_ark import _parse_date

        d = _parse_date("Q1'16")
        assert d is not None
        assert d.year == 2016
        assert d.month == 3

    def test_empty_string(self):
        from eol_tool.checkers.intel_ark import _parse_date

        assert _parse_date("") is None

    def test_none_input(self):
        from eol_tool.checkers.intel_ark import _parse_date

        assert _parse_date("") is None


# ===================================================================
# Cache behaviour
# ===================================================================


class TestCacheBehavior:
    def test_cache_hit_returns_data(self):
        from eol_tool.checkers.intel_ark import _get_cached, _set_cached

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS ark_cache (
                model_key TEXT PRIMARY KEY,
                result_status TEXT,
                marketing_status TEXT,
                launch_date TEXT,
                eol_date TEXT,
                servicing_status TEXT,
                cached_at TEXT NOT NULL
            )"""
        )
        _set_cached(conn, "E5-2683V4", {
            "result_status": "",
            "marketing_status": "Discontinued",
            "launch_date": "Q1'16",
            "eol_date": "June 30, 2022",
        })
        cached = _get_cached(conn, "E5-2683V4")
        assert cached is not None
        assert cached["marketing_status"] == "Discontinued"
        conn.close()

    def test_cache_miss_returns_none(self):
        from eol_tool.checkers.intel_ark import _get_cached

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS ark_cache (
                model_key TEXT PRIMARY KEY,
                result_status TEXT,
                marketing_status TEXT,
                launch_date TEXT,
                eol_date TEXT,
                servicing_status TEXT,
                cached_at TEXT NOT NULL
            )"""
        )
        assert _get_cached(conn, "UNKNOWN") is None
        conn.close()

    def test_expired_cache_returns_none(self):
        from eol_tool.checkers.intel_ark import _get_cached

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS ark_cache (
                model_key TEXT PRIMARY KEY,
                result_status TEXT,
                marketing_status TEXT,
                launch_date TEXT,
                eol_date TEXT,
                servicing_status TEXT,
                cached_at TEXT NOT NULL
            )"""
        )
        old_time = (datetime.now() - timedelta(days=31)).isoformat()
        conn.execute(
            "INSERT INTO ark_cache VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("OLD-KEY", "", "Discontinued", "", "", "", old_time),
        )
        conn.commit()
        assert _get_cached(conn, "OLD-KEY") is None
        conn.close()


# ===================================================================
# Timeout returns NOT_FOUND
# ===================================================================


class TestTimeoutHandling:
    def test_timeout_data_becomes_not_found(self):
        from eol_tool.checkers.intel_ark import _to_result

        model = _hw("TIMEOUT-CPU")
        r = _to_result(model, {"result_status": "timeout"})
        assert r.status == EOLStatus.NOT_FOUND


# ===================================================================
# HTML/Text extraction
# ===================================================================


class TestExtraction:
    def test_extract_from_text_discontinued(self):
        from eol_tool.checkers.intel_ark import _extract_from_text

        text = (
            "Some header\n"
            "Marketing Status Discontinued\n"
            "Launch Date Q1'16\n"
            "End of Servicing Updates Date Thursday June 30 2022\n"
        )
        data = _extract_from_text(text)
        assert data is not None
        assert data["marketing_status"] == "Discontinued"
        assert "June 30 2022" in data.get("eol_date", "")

    def test_extract_from_text_launched(self):
        from eol_tool.checkers.intel_ark import _extract_from_text

        text = "Marketing Status Launched\nLaunch Date Q1'23\n"
        data = _extract_from_text(text)
        assert data is not None
        assert data["marketing_status"] == "Launched"

    def test_extract_from_text_no_status(self):
        from eol_tool.checkers.intel_ark import _extract_from_text

        text = "Some random page content with no useful data"
        assert _extract_from_text(text) is None

    def test_extract_from_html_discontinued(self):
        from eol_tool.checkers.intel_ark import _extract_from_html

        html = '<div>Marketing Status</div><span>Discontinued</span>'
        data = _extract_from_html(html)
        assert data is not None
        assert data["marketing_status"] == "Discontinued"


# ===================================================================
# Registration
# ===================================================================


class TestRegistration:
    def test_registers_for_intel(self):
        from eol_tool.registry import get_checkers

        checkers = get_checkers("Intel")
        class_names = [c.__name__ for c in checkers]
        assert "IntelARKChecker" in class_names

    def test_multiple_intel_checkers(self):
        from eol_tool.registry import get_checkers

        checkers = get_checkers("Intel")
        assert len(checkers) >= 2
