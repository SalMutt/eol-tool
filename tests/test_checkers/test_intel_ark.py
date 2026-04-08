"""Tests for IntelARKChecker."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


def _hw(model: str, category: str = "cpu", manufacturer: str = "Intel") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# Graceful handling when playwright is not installed
# ===================================================================


@pytest.mark.playwright
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
# Unsupported categories return NOT_FOUND
# ===================================================================


@pytest.mark.playwright
class TestUnsupportedCategory:
    async def test_unsupported_category_returns_not_found(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        r = await checker.check(_hw("SOMETHING", category="motherboard"))
        assert r.status == EOLStatus.NOT_FOUND
        assert "unsupported" in r.notes


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


# ===================================================================
# Search term construction
# ===================================================================


class TestSearchTermConstruction:
    def test_e2xxx_basic(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert _prepare_search_term("E-2136", "cpu") == "Intel Xeon E-2136 Processor"

    def test_e2xxx_with_suffix(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert _prepare_search_term("E-2288G", "cpu") == "Intel Xeon E-2288G Processor"

    def test_e5_with_v_suffix(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert (
            _prepare_search_term("E5-2683V4", "cpu")
            == "Intel Xeon E5-2683 v4 Processor"
        )

    def test_e3_with_v_suffix(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert (
            _prepare_search_term("E3-1270V5", "cpu")
            == "Intel Xeon E3-1270 v5 Processor"
        )

    def test_e7_without_v_suffix(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert _prepare_search_term("E7-8890", "cpu") == "Intel Xeon E7-8890 Processor"

    def test_scalable_silver(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert (
            _prepare_search_term("SILVER 4310", "cpu")
            == "Intel Xeon Silver 4310 Processor"
        )

    def test_scalable_gold_with_suffix(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert (
            _prepare_search_term("GOLD 5412U", "cpu")
            == "Intel Xeon Gold 5412U Processor"
        )

    def test_scalable_platinum(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert (
            _prepare_search_term("PLATINUM 8380", "cpu")
            == "Intel Xeon Platinum 8380 Processor"
        )

    def test_scalable_number_first(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        assert (
            _prepare_search_term("6132 GOLD", "cpu")
            == "Intel Xeon Gold 6132 Processor"
        )

    def test_nic_unchanged(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        result = _prepare_search_term("X520-DA2", "nic")
        assert "Intel Ethernet" in result

    def test_ssd_unchanged(self):
        from eol_tool.checkers.intel_ark import _prepare_search_term

        result = _prepare_search_term("D3-S4510", "ssd")
        assert "Intel SSD" in result


# ===================================================================
# Google search - URL extraction
# ===================================================================


def _make_mock_link(href: str) -> AsyncMock:
    """Create a mock Playwright element handle with a given href."""
    link = AsyncMock()
    link.get_attribute = AsyncMock(return_value=href)
    return link


def _make_mock_page(
    body_text: str = "Search results",
    links: list | None = None,
    selector_raises: bool = False,
) -> AsyncMock:
    """Create a mock Playwright page for Google search tests."""
    page = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.goto = AsyncMock()
    page.inner_text = AsyncMock(return_value=body_text)
    if selector_raises:
        page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
    else:
        page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=links or [])
    return page


@pytest.mark.playwright
class TestGoogleSearch:
    async def test_extracts_direct_url(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        url = "https://www.intel.com/content/www/us/en/products/sku/120477/intel-xeon-e2136-processor/specifications.html"
        link = _make_mock_link(url)
        page = _make_mock_page(links=[link])

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result == url

    async def test_extracts_url_from_google_redirect(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        real_url = "https://www.intel.com/content/www/us/en/products/sku/120477/intel-xeon-e2136-processor/specifications.html"
        wrapped = f"/url?q={real_url}&sa=U&ved=abc123"
        link = _make_mock_link(wrapped)
        page = _make_mock_page(links=[link])

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result == real_url

    async def test_appends_specifications_to_bare_url(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        bare_url = "https://www.intel.com/content/www/us/en/products/sku/120477/intel-xeon-e2136-processor.html"
        link = _make_mock_link(bare_url)
        page = _make_mock_page(links=[link])

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result is not None
        assert "/specifications.html" in result

    async def test_captcha_returns_none(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        page = _make_mock_page(
            body_text="Our systems have detected unusual traffic from your computer"
        )

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result is None

    async def test_no_results_returns_none(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        page = _make_mock_page(links=[])

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result is None

    async def test_selector_timeout_returns_none(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        page = _make_mock_page(selector_raises=True)

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result is None

    async def test_exception_returns_none(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        page = AsyncMock()
        page.wait_for_timeout = AsyncMock(side_effect=Exception("network error"))

        checker = IntelARKChecker()
        result = await checker._try_google_search("Intel Xeon E-2136 Processor", page)
        assert result is None


# ===================================================================
# Strategy chain fallthrough
# ===================================================================


@pytest.mark.playwright
class TestStrategyChain:
    async def test_google_success_skips_other_strategies(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        checker._browser = MagicMock()

        mock_page = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.url = "https://www.intel.com/content/www/us/en/products/sku/120477/specifications.html"
        mock_page.inner_text = AsyncMock(
            return_value="Marketing Status Launched\nLaunch Date Q1'19\n"
        )
        mock_page.close = AsyncMock()
        checker._browser.new_page = AsyncMock(return_value=mock_page)

        google_url = "https://www.intel.com/content/www/us/en/products/sku/120477/specifications.html"
        checker._try_google_search = AsyncMock(return_value=google_url)
        checker._try_ark_direct_search = AsyncMock(return_value=None)
        checker._try_intel_search = AsyncMock(return_value=None)
        checker._try_ark_search = AsyncMock(return_value=None)

        result = await checker._playwright_lookup("E-2136", "cpu")
        assert result is not None
        checker._try_google_search.assert_called_once()
        checker._try_ark_direct_search.assert_not_called()
        checker._try_intel_search.assert_not_called()
        checker._try_ark_search.assert_not_called()

    async def test_google_fails_tries_ark_direct(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        checker._browser = MagicMock()

        mock_page = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.url = "https://ark.intel.com/content/www/us/en/products/sku/120477/specifications.html"
        mock_page.inner_text = AsyncMock(
            return_value="Marketing Status Launched\nLaunch Date Q1'19\n"
        )
        mock_page.close = AsyncMock()
        checker._browser.new_page = AsyncMock(return_value=mock_page)

        ark_url = "https://ark.intel.com/content/www/us/en/products/sku/120477/specifications.html"
        checker._try_google_search = AsyncMock(return_value=None)
        checker._try_ark_direct_search = AsyncMock(return_value=ark_url)
        checker._try_intel_search = AsyncMock(return_value=None)
        checker._try_ark_search = AsyncMock(return_value=None)

        result = await checker._playwright_lookup("E-2136", "cpu")
        assert result is not None
        checker._try_google_search.assert_called_once()
        checker._try_ark_direct_search.assert_called_once()
        checker._try_intel_search.assert_not_called()

    async def test_all_strategies_fail_returns_none(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        checker = IntelARKChecker()
        checker._browser = MagicMock()

        mock_page = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        mock_page.close = AsyncMock()
        checker._browser.new_page = AsyncMock(return_value=mock_page)

        checker._try_google_search = AsyncMock(return_value=None)
        checker._try_ark_direct_search = AsyncMock(return_value=None)
        checker._try_intel_search = AsyncMock(return_value=None)
        checker._try_ark_search = AsyncMock(return_value=None)

        result = await checker._playwright_lookup("MYSTERY-9999", "cpu")
        assert result is None
        checker._try_google_search.assert_called_once()
        checker._try_ark_direct_search.assert_called_once()
        checker._try_intel_search.assert_called_once()
        checker._try_ark_search.assert_called_once()


# ===================================================================
# Mock helpers for _find_product_link tests
# ===================================================================


def _make_ark_link(href: str, text: str) -> AsyncMock:
    """Create a mock link element with href, text, and visibility."""
    el = AsyncMock()
    el.is_visible = AsyncMock(return_value=True)
    el.get_attribute = AsyncMock(return_value=href)
    el.inner_text = AsyncMock(return_value=text)
    return el


def _make_search_page(links: list[AsyncMock]) -> AsyncMock:
    """Build a mock page whose first matching selector returns *links*."""
    page = AsyncMock()
    first_call = True

    async def _qsa(selector):
        nonlocal first_call
        if first_call and "products/sku" in selector:
            first_call = False
            return links
        return []

    page.query_selector_all = AsyncMock(side_effect=_qsa)
    return page


# ===================================================================
# Relevance scoring in _find_product_link
# ===================================================================


class TestRelevanceScoring:
    async def test_trademark_symbols_stripped_for_matching(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/134857/specifications.html",
            "Intel\u00ae Xeon\u00ae E-2136 Processor",
        )
        page = _make_search_page([link])
        checker = IntelARKChecker()
        result = await checker._find_product_link(page, "Intel Xeon E-2136 Processor")
        assert result is not None
        assert "/products/sku/134857/" in result

    async def test_reverse_word_order_matches_via_bare_model(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/91766/specifications.html",
            "Intel\u00ae Xeon\u00ae Processor E5-2683 v4",
        )
        page = _make_search_page([link])
        checker = IntelARKChecker()
        result = await checker._find_product_link(
            page, "Intel Xeon E5-2683 v4 Processor"
        )
        assert result is not None
        assert "/products/sku/91766/" in result

    async def test_scalable_xeon_matches(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/215277/specifications.html",
            "Intel\u00ae Xeon\u00ae Silver 4310 Processor",
        )
        page = _make_search_page([link])
        checker = IntelARKChecker()
        result = await checker._find_product_link(
            page, "Intel Xeon Silver 4310 Processor"
        )
        assert result is not None
        assert "/products/sku/" in result

    async def test_irrelevant_results_rejected(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/99999/specifications.html",
            "Intel\u00ae Itanium\u00ae Processor 9500 Series",
        )
        page = _make_search_page([link])
        checker = IntelARKChecker()
        result = await checker._find_product_link(
            page, "Intel Xeon E5-2683 v4 Processor"
        )
        assert result is None

    async def test_version_suffix_distinguishes_models(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link_v4 = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/91766/specifications.html",
            "Intel\u00ae Xeon\u00ae Processor E5-2683 v4",
        )
        link_v3 = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/81055/specifications.html",
            "Intel\u00ae Xeon\u00ae Processor E5-2683 v3",
        )
        page = _make_search_page([link_v4, link_v3])
        checker = IntelARKChecker()
        result = await checker._find_product_link(
            page, "Intel Xeon E5-2683 v4 Processor"
        )
        assert result is not None
        assert "/sku/91766/" in result


# ===================================================================
# _extract_core_model
# ===================================================================


class TestExtractCoreModel:
    def test_strips_intel_prefix(self):
        from eol_tool.checkers.intel_ark import _extract_core_model

        assert _extract_core_model("Intel Xeon E-2136 Processor") == "Xeon E-2136 Processor"

    def test_strips_intel_ethernet(self):
        from eol_tool.checkers.intel_ark import _extract_core_model

        assert _extract_core_model("Intel Ethernet X520-DA2") == "X520-DA2"

    def test_strips_intel_ssd(self):
        from eol_tool.checkers.intel_ark import _extract_core_model

        assert _extract_core_model("Intel SSD S3500") == "S3500"

    def test_passthrough_bare_model(self):
        from eol_tool.checkers.intel_ark import _extract_core_model

        assert _extract_core_model("E5-2683V4") == "E5-2683V4"


# ===================================================================
# Packaging suffix stripping
# ===================================================================


class TestPackagingSuffixStripping:
    def test_normalize_key_strips_retail(self):
        from eol_tool.checkers.intel_ark import _normalize_key

        result = _normalize_key("E3-1230 V6 RETAIL", "cpu")
        assert "RETAIL" not in result.upper()
        assert "E3-1230 V6" in result

    def test_normalize_key_strips_oem(self):
        from eol_tool.checkers.intel_ark import _normalize_key

        result = _normalize_key("E5-2683V4 OEM", "cpu")
        assert "OEM" not in result.upper()
        assert "E5-2683V4" in result

    def test_prepare_search_term_strips_retail(self):
        from eol_tool.checkers.intel_ark import _normalize_key, _prepare_search_term

        key = _normalize_key("E3-1230 V6 RETAIL", "cpu")
        result = _prepare_search_term(key, "cpu")
        assert result == "Intel Xeon E3-1230 v6 Processor"

    async def test_version_mismatch_rejected(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link_v3 = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/75054/specifications.html",
            "Intel\u00ae Xeon\u00ae Processor E3-1230 v3",
        )
        page = _make_search_page([link_v3])
        checker = IntelARKChecker()
        result = await checker._find_product_link(
            page, "Intel Xeon E3-1230 v6 Processor"
        )
        assert result is None

    async def test_version_match_accepted(self):
        from eol_tool.checkers.intel_ark import IntelARKChecker

        link_v6 = _make_ark_link(
            "https://ark.intel.com/content/www/us/en/ark/products/sku/97478/specifications.html",
            "Intel\u00ae Xeon\u00ae Processor E3-1230 v6",
        )
        page = _make_search_page([link_v6])
        checker = IntelARKChecker()
        result = await checker._find_product_link(
            page, "Intel Xeon E3-1230 v6 Processor"
        )
        assert result is not None
        assert "/sku/97478/" in result
