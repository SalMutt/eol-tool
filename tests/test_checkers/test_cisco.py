"""Tests for the CiscoChecker (static classification + Playwright scraping)."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

from eol_tool.checkers.cisco import CiscoChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


def _hw(
    model: str, manufacturer: str = "Cisco", category: str = "network",
) -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Static classification
# ===================================================================


class TestStaticClassification:
    """All Cisco classification is now static — no endoflife.date API.

    Patch _get_cached so tests always exercise the static path, regardless
    of any bulletin data that may be in the local scraper cache.
    """

    async def test_asa5516_eol(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("ASA5516-FPWR-K9", category="firewall"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_reason == EOLReason.PRODUCT_DISCONTINUED
        assert r.confidence == 70
        assert r.date_source == "none"
        assert r.eol_date is None

    async def test_asa5506_eol(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("ASA5506-SEC-BUN-K9", category="firewall"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.date_source == "none"

    async def test_asa5525_eol(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("ASA5525-K9", category="firewall"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.date_source == "none"

    async def test_generic_asa_eol(self):
        """Any unrecognised ASA model number should match the generic ASA regex."""
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("ASA9999-K9", category="firewall"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.date_source == "none"

    async def test_aironet_3700_eol(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("Aironet 3700", category="wireless"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.date_source == "none"

    async def test_3700_access_point_eol(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("3700 Access Point", category="wireless"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.date_source == "none"

    async def test_2500_wireless_controller_eol(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("2500 Wireless Controller", category="wireless"))
        assert r.status == EOLStatus.EOL
        assert r.risk_category == RiskCategory.SECURITY
        assert r.date_source == "none"

    async def test_qsfp_univ_active(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("QSFP+-UNIV", category="optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE
        assert r.date_source == "none"

    async def test_40g_qsfp_active(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("40G QSFP Transceiver", category="optic"))
        assert r.status == EOLStatus.ACTIVE
        assert r.date_source == "none"

    async def test_unknown_model(self):
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("MYSTERY-CISCO"))
        assert r.status == EOLStatus.UNKNOWN
        assert r.confidence == 50
        assert r.date_source == "none"


# ===================================================================
# No HTTP calls should ever be made (static path)
# ===================================================================


class TestNoHttpCalls:
    async def test_asa_does_not_call_api(self, httpx_mock):
        with patch.dict(
            "eol_tool.checkers.cisco.__dict__",
            {"PLAYWRIGHT_AVAILABLE": False},
        ):
            async with CiscoChecker() as c:
                r = await c.check(_hw("ASA5516-FPWR-K9", category="firewall"))
            assert r.status == EOLStatus.EOL
            assert len(httpx_mock.get_requests()) == 0

    async def test_aironet_does_not_call_api(self, httpx_mock):
        with patch.dict(
            "eol_tool.checkers.cisco.__dict__",
            {"PLAYWRIGHT_AVAILABLE": False},
        ):
            async with CiscoChecker() as c:
                r = await c.check(_hw("Aironet 3700", category="wireless"))
            assert r.status == EOLStatus.EOL
            assert len(httpx_mock.get_requests()) == 0

    async def test_qsfp_does_not_call_api(self, httpx_mock):
        with patch.dict(
            "eol_tool.checkers.cisco.__dict__",
            {"PLAYWRIGHT_AVAILABLE": False},
        ):
            async with CiscoChecker() as c:
                r = await c.check(_hw("40G QSFP Transceiver", category="optic"))
            assert r.status == EOLStatus.ACTIVE
            assert len(httpx_mock.get_requests()) == 0


# ===================================================================
# Normalization
# ===================================================================


class TestNormalization:
    def test_strip_cisco_prefix(self):
        assert CiscoChecker._normalize("Cisco ASA5516-FPWR-K9") == "ASA5516-FPWR-K9"


# ===================================================================
# Auto-registration
# ===================================================================


class TestRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "cisco" in checkers
        assert checkers["cisco"] is CiscoChecker


# ===================================================================
# Playwright fallback when not installed
# ===================================================================


class TestPlaywrightNotInstalled:
    async def test_static_fallback_when_playwright_missing(self):
        with patch.dict(
            "eol_tool.checkers.cisco.__dict__",
            {"PLAYWRIGHT_AVAILABLE": False},
        ), patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            r = await checker.check(_hw("ASA5516-FPWR-K9", category="firewall"))
            assert r.status == EOLStatus.EOL
            assert r.date_source == "none"
            assert r.confidence == 70


# ===================================================================
# Bulletin date extraction
# ===================================================================


class TestBulletinExtraction:
    def test_extract_all_dates(self):
        from eol_tool.checkers.cisco import _extract_bulletin_dates

        text = (
            "End-of-Sale Date: August 2, 2021\n"
            "End-of-SW-Maintenance Releases Date: August 2, 2022\n"
            "End-of-Security/Vulnerability Support: August 2, 2024\n"
            "Last Date of Support: July 31, 2026\n"
        )
        data = _extract_bulletin_dates(text)
        assert data is not None
        assert "August 2, 2021" in data["eol_date"]
        assert "July 31, 2026" in data["eos_date"]
        assert "August 2, 2022" in data["eo_sw_maint"]

    def test_extract_partial_dates(self):
        from eol_tool.checkers.cisco import _extract_bulletin_dates

        text = "End-of-Sale Date: March 15, 2020\nSome other content"
        data = _extract_bulletin_dates(text)
        assert data is not None
        assert "March 15, 2020" in data["eol_date"]

    def test_no_dates_returns_none(self):
        from eol_tool.checkers.cisco import _extract_bulletin_dates

        text = "This page has no EOL date information"
        assert _extract_bulletin_dates(text) is None


# ===================================================================
# Cached bulletin result conversion
# ===================================================================


class TestCachedResult:
    def test_cached_bulletin_to_result(self):
        from eol_tool.checkers.cisco import _cached_to_result

        model = _hw("ASA5516-FPWR-K9", category="firewall")
        data = {
            "eol_date": "August 2, 2021",
            "eos_date": "July 31, 2026",
        }
        r = _cached_to_result(model, data)
        assert r.status == EOLStatus.EOL
        assert r.confidence == 95
        assert r.date_source == "manufacturer_confirmed"
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.SECURITY
        assert r.eol_date is not None
        assert r.eol_date.year == 2021
        assert r.eos_date is not None
        assert r.eos_date.year == 2026

    def test_cached_with_all_dates(self):
        from eol_tool.checkers.cisco import _cached_to_result

        model = _hw("ASA5506", category="firewall")
        data = {
            "eol_date": "January 10, 2022",
            "eos_date": "January 31, 2027",
            "eo_sw_maint": "January 10, 2023",
            "eo_vuln_support": "January 10, 2025",
        }
        r = _cached_to_result(model, data)
        assert r.eol_date is not None
        assert r.eos_date is not None
        assert "End-of-Sale" in r.notes
        assert "Last Date of Support" in r.notes
        assert "End-of-SW-Maintenance" in r.notes


# ===================================================================
# Date parsing
# ===================================================================


class TestDateParsing:
    def test_standard_format(self):
        from eol_tool.checkers.cisco import _parse_cisco_date

        d = _parse_cisco_date("August 2, 2021")
        assert d is not None
        assert d.year == 2021
        assert d.month == 8
        assert d.day == 2

    def test_no_comma(self):
        from eol_tool.checkers.cisco import _parse_cisco_date

        d = _parse_cisco_date("August 2 2021")
        assert d is not None
        assert d.year == 2021

    def test_empty_returns_none(self):
        from eol_tool.checkers.cisco import _parse_cisco_date

        assert _parse_cisco_date("") is None
        assert _parse_cisco_date("   ") is None


# ===================================================================
# Cache behavior
# ===================================================================


class TestCacheBehavior:
    def test_cache_hit(self):
        from eol_tool.checkers.cisco import _get_cached, _set_cached

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cisco_cache (
                model_key TEXT PRIMARY KEY,
                result_status TEXT,
                eol_date TEXT,
                eos_date TEXT,
                eo_sw_maint TEXT,
                eo_vuln_support TEXT,
                cached_at TEXT NOT NULL
            )"""
        )
        _set_cached(conn, "ASA5516-FPWR-K9", {
            "result_status": "found",
            "eol_date": "August 2, 2021",
            "eos_date": "July 31, 2026",
        })
        cached = _get_cached(conn, "ASA5516-FPWR-K9")
        assert cached is not None
        assert cached["eol_date"] == "August 2, 2021"
        conn.close()

    def test_cache_miss(self):
        from eol_tool.checkers.cisco import _get_cached

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cisco_cache (
                model_key TEXT PRIMARY KEY,
                result_status TEXT,
                eol_date TEXT,
                eos_date TEXT,
                eo_sw_maint TEXT,
                eo_vuln_support TEXT,
                cached_at TEXT NOT NULL
            )"""
        )
        assert _get_cached(conn, "UNKNOWN") is None
        conn.close()

    def test_expired_cache(self):
        from eol_tool.checkers.cisco import _get_cached

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cisco_cache (
                model_key TEXT PRIMARY KEY,
                result_status TEXT,
                eol_date TEXT,
                eos_date TEXT,
                eo_sw_maint TEXT,
                eo_vuln_support TEXT,
                cached_at TEXT NOT NULL
            )"""
        )
        old_time = (datetime.now() - timedelta(days=31)).isoformat()
        conn.execute(
            "INSERT INTO cisco_cache VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("OLD-KEY", "found", "Jan 1, 2020", "", "", "", old_time),
        )
        conn.commit()
        assert _get_cached(conn, "OLD-KEY") is None
        conn.close()


# ===================================================================
# Timeout handling
# ===================================================================


class TestTimeoutHandling:
    async def test_timeout_uses_static_fallback(self):
        """When Playwright is unavailable, static fallback is used."""
        with patch("eol_tool.checkers.cisco._get_cached", return_value=None):
            checker = CiscoChecker()
            checker._checker_disabled = True
            r = await checker.check(_hw("ASA5516-FPWR-K9", category="firewall"))
            assert r.status == EOLStatus.EOL
            assert r.date_source == "none"
            assert r.confidence == 70
