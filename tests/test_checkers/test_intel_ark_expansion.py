"""Tests for IntelARKChecker expansion to NICs, SSDs, and optics."""

from unittest.mock import AsyncMock, MagicMock, patch

from eol_tool.checkers.intel_ark import (
    IntelARKChecker,
    _extract_core_model,
    _normalize_key,
    _prepare_search_term,
    _to_result,
)
from eol_tool.models import EOLReason, EOLStatus, HardwareModel, RiskCategory


def _hw(model: str, category: str = "cpu", manufacturer: str = "Intel") -> HardwareModel:
    return HardwareModel(model=model, manufacturer=manufacturer, category=category)


# ===================================================================
# NIC / SSD / optic categories pass the gate
# ===================================================================


class TestCategoryAccepted:
    async def test_nic_passes_category_gate(self):
        checker = IntelARKChecker()
        r = await checker.check(_hw("X520-DA2", category="nic"))
        assert "unsupported" not in r.notes

    async def test_ssd_passes_category_gate(self):
        checker = IntelARKChecker()
        r = await checker.check(_hw("INT S3500", category="ssd"))
        assert "unsupported" not in r.notes

    async def test_optic_passes_category_gate(self):
        checker = IntelARKChecker()
        r = await checker.check(_hw("SFP-10GSR", category="optic"))
        assert "unsupported" not in r.notes


# ===================================================================
# NIC model-to-query normalization
# ===================================================================


class TestNICNormalization:
    def test_strips_speed_port_suffix(self):
        key = _normalize_key("X520-DA2 10GB/S DUAL", "nic")
        assert key == "X520-DA2"

    def test_preserves_bare_adapter_family(self):
        key = _normalize_key("X520-DA2", "nic")
        assert key == "X520-DA2"

    def test_strips_intel_prefix(self):
        key = _normalize_key("INTEL X710-BM2", "nic")
        assert key == "X710-BM2"

    def test_i350_extraction(self):
        key = _normalize_key("I350-T4 1GB/S QUAD", "nic")
        assert key == "I350-T4"

    def test_search_term_is_adapter_family(self):
        key = _normalize_key("X520-DA2 10GB/S DUAL", "nic")
        term = _prepare_search_term(key, "nic")
        assert term == "Intel Ethernet X520-DA2"


# ===================================================================
# SSD model-to-query normalization
# ===================================================================


class TestSSDNormalization:
    def test_int_prefix_stripped_and_ssd_prepended(self):
        key = _normalize_key("INT S3500", "ssd")
        term = _prepare_search_term(key, "ssd")
        assert term == "Intel SSD S3500"

    def test_int_d3_model(self):
        key = _normalize_key("INT D3-S4510", "ssd")
        term = _prepare_search_term(key, "ssd")
        assert term == "Intel SSD D3-S4510"

    def test_bare_ssd_model(self):
        key = _normalize_key("660P", "ssd")
        term = _prepare_search_term(key, "ssd")
        assert term == "Intel SSD 660P"


# ===================================================================
# ARK result for NIC returns manufacturer_confirmed
# ===================================================================


class TestNICARKResult:
    def test_discontinued_nic_returns_manufacturer_confirmed(self):
        model = _hw("X520-DA2", category="nic")
        data = {
            "marketing_status": "Discontinued",
            "launch_date": "Q4'12",
            "eol_date": "July 1, 2021",
        }
        r = _to_result(model, data)
        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.confidence == 90
        assert r.risk_category == RiskCategory.SUPPORT

    def test_active_nic_returns_active(self):
        model = _hw("X550-T2", category="nic")
        data = {"marketing_status": "Launched", "launch_date": "Q3'15"}
        r = _to_result(model, data)
        assert r.status == EOLStatus.ACTIVE
        assert r.risk_category == RiskCategory.NONE


# ===================================================================
# Full check with mocked Playwright (never hits real ARK)
# ===================================================================


class TestMockedPlaywrightCheck:
    async def test_nic_check_with_mocked_playwright(self):
        checker = IntelARKChecker()
        checker._checker_disabled = False

        mock_data = {
            "marketing_status": "Discontinued",
            "launch_date": "Q4'12",
            "eol_date": "July 1, 2021",
        }

        with (
            patch.object(
                checker,
                "_playwright_lookup",
                new_callable=AsyncMock,
                return_value=mock_data,
            ),
            patch("eol_tool.checkers.intel_ark.PLAYWRIGHT_AVAILABLE", True),
            patch("eol_tool.checkers.intel_ark._init_cache_db") as mock_db,
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_db.return_value = mock_conn

            r = await checker.check(_hw("X520-DA2", category="nic"))

        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"
        assert r.source_name == "intel-ark"

    async def test_ssd_check_with_mocked_playwright(self):
        checker = IntelARKChecker()
        checker._checker_disabled = False

        mock_data = {
            "marketing_status": "Discontinued",
            "eol_date": "March 15, 2020",
        }

        with (
            patch.object(
                checker,
                "_playwright_lookup",
                new_callable=AsyncMock,
                return_value=mock_data,
            ),
            patch("eol_tool.checkers.intel_ark.PLAYWRIGHT_AVAILABLE", True),
            patch("eol_tool.checkers.intel_ark._init_cache_db") as mock_db,
        ):
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_db.return_value = mock_conn

            r = await checker.check(_hw("INT D3-S4510", category="ssd"))

        assert r.status == EOLStatus.EOL
        assert r.date_source == "manufacturer_confirmed"
        assert r.source_name == "intel-ark"


# ===================================================================
# ARK direct search routing and strategy tests
# ===================================================================


def _make_mock_page(url_after_goto="https://ark.intel.com/search-results"):
    """Create a mock Playwright page for testing search strategies."""
    page = AsyncMock()
    page.url = url_after_goto
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.title = AsyncMock(return_value="Intel Search")
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=None)

    async def update_url_on_goto(url, **kwargs):
        page.url = url

    page.goto.side_effect = update_url_on_goto
    return page


class TestArkDirectSearchRouting:
    """Verify NIC/SSD categories use _try_ark_direct_search first."""

    async def test_nic_calls_ark_direct_search_first(self):
        checker = IntelARKChecker()
        checker._browser = MagicMock()

        page = _make_mock_page()
        checker._browser.new_page = AsyncMock(return_value=page)

        with patch.object(
            checker, "_try_ark_direct_search", new_callable=AsyncMock
        ) as mock_ark, patch.object(
            checker, "_try_intel_search", new_callable=AsyncMock
        ) as mock_intel:
            # ARK direct search succeeds
            mock_ark.return_value = "https://ark.intel.com/products/sku/12345"
            page.inner_text = AsyncMock(return_value="Marketing Status Launched")

            await checker._playwright_lookup("X520-DA2", "nic")

            mock_ark.assert_awaited_once()
            mock_intel.assert_not_awaited()

    async def test_ssd_calls_ark_direct_search_first(self):
        checker = IntelARKChecker()
        checker._browser = MagicMock()

        page = _make_mock_page()
        checker._browser.new_page = AsyncMock(return_value=page)

        with patch.object(
            checker, "_try_ark_direct_search", new_callable=AsyncMock
        ) as mock_ark, patch.object(
            checker, "_try_intel_search", new_callable=AsyncMock
        ) as mock_intel:
            mock_ark.return_value = "https://ark.intel.com/products/sku/99999"
            page.inner_text = AsyncMock(return_value="Marketing Status Discontinued")

            await checker._playwright_lookup("D3-S4510", "ssd")

            mock_ark.assert_awaited_once()
            mock_intel.assert_not_awaited()

    async def test_cpu_tries_google_first_then_falls_through(self):
        checker = IntelARKChecker()
        checker._browser = MagicMock()

        page = _make_mock_page()
        checker._browser.new_page = AsyncMock(return_value=page)

        with patch.object(
            checker, "_try_google_search", new_callable=AsyncMock
        ) as mock_google, patch.object(
            checker, "_try_ark_direct_search", new_callable=AsyncMock
        ) as mock_ark, patch.object(
            checker, "_try_intel_search", new_callable=AsyncMock
        ) as mock_intel:
            mock_google.return_value = None
            mock_ark.return_value = None
            mock_intel.return_value = "https://intel.com/products/sku/55555"
            page.inner_text = AsyncMock(return_value="Marketing Status Launched")

            await checker._playwright_lookup("E5-2683 v4", "cpu")

            mock_google.assert_awaited_once()
            mock_ark.assert_awaited_once()
            mock_intel.assert_awaited_once()

    async def test_nic_falls_back_to_intel_search_when_ark_direct_fails(self):
        checker = IntelARKChecker()
        checker._browser = MagicMock()

        page = _make_mock_page()
        checker._browser.new_page = AsyncMock(return_value=page)

        with patch.object(
            checker, "_try_ark_direct_search", new_callable=AsyncMock
        ) as mock_ark, patch.object(
            checker, "_try_intel_search", new_callable=AsyncMock
        ) as mock_intel:
            mock_ark.return_value = None  # ARK direct search fails
            mock_intel.return_value = "https://intel.com/products/sku/12345"
            page.inner_text = AsyncMock(return_value="Marketing Status Launched")

            await checker._playwright_lookup("X520-DA2", "nic")

            mock_ark.assert_awaited_once()
            mock_intel.assert_awaited_once()


class TestArkDirectSearchBehavior:
    """Test the _try_ark_direct_search method itself."""

    async def test_redirect_to_product_page_returns_url(self):
        """When ARK redirects directly to a product page, return that URL."""
        checker = IntelARKChecker()
        page = _make_mock_page()

        # Simulate ARK redirecting to a product page
        product_url = (
            "https://ark.intel.com/content/www/us/en/ark/products/sku/"
            "82599/intel-ethernet-x520-da2.html"
        )

        async def redirect_to_product(url, **kwargs):
            page.url = product_url

        page.goto.side_effect = redirect_to_product

        result = await checker._try_ark_direct_search(page, "Intel Ethernet X520-DA2")
        assert result == product_url

    async def test_search_results_page_finds_product_link(self):
        """When ARK shows search results, find product links in the page."""
        checker = IntelARKChecker()
        page = _make_mock_page(
            "https://ark.intel.com/content/www/us/en/ark/search.html"
        )

        # page.goto doesn't change URL (stays on search results)
        async def stay_on_search(url, **kwargs):
            pass  # URL stays as initialized

        page.goto.side_effect = stay_on_search

        # Mock _find_product_link to return a link
        with patch.object(
            checker, "_find_product_link", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = (
                "https://ark.intel.com/content/www/us/en/ark/products/"
                "82599/intel-ethernet-x520-da2.html"
            )
            result = await checker._try_ark_direct_search(
                page, "Intel Ethernet X520-DA2"
            )
            assert result is not None
            assert "82599" in result
            mock_find.assert_awaited_once()

    async def test_navigation_failure_returns_none(self):
        """When ARK navigation fails, return None gracefully."""
        checker = IntelARKChecker()
        page = _make_mock_page()

        page.goto.side_effect = Exception("net::ERR_CONNECTION_TIMED_OUT")

        result = await checker._try_ark_direct_search(page, "Intel Ethernet X520-DA2")
        assert result is None


# ===================================================================
# _extract_core_model tests
# ===================================================================


class TestExtractCoreModel:
    def test_nic_search_term(self):
        assert _extract_core_model("Intel Ethernet X520-DA2") == "X520-DA2"

    def test_ssd_search_term(self):
        assert _extract_core_model("Intel SSD S3500") == "S3500"

    def test_ssd_d3_search_term(self):
        assert _extract_core_model("Intel SSD D3-S4510") == "D3-S4510"

    def test_cpu_bare_model(self):
        assert _extract_core_model("E5-2683V4") == "E5-2683V4"

    def test_strips_generic_intel_prefix(self):
        assert _extract_core_model("Intel 660P") == "660P"


# ===================================================================
# _find_product_link relevance scoring tests
# ===================================================================


def _make_mock_link(href: str, text: str, visible: bool = True):
    """Create a mock Playwright link element."""
    link = AsyncMock()
    link.is_visible = AsyncMock(return_value=visible)
    link.get_attribute = AsyncMock(return_value=href)
    link.inner_text = AsyncMock(return_value=text)
    return link


class TestFindProductLinkScoring:
    async def test_prefers_exact_match_over_partial(self):
        """X520-DA2 should be chosen over X527-DA2."""
        checker = IntelARKChecker()
        page = AsyncMock()

        wrong_link = _make_mock_link(
            "/products/sku/11111/x527-da2.html",
            "Intel Ethernet Converged Network Adapter X527-DA2",
        )
        correct_link = _make_mock_link(
            "/products/sku/82599/x520-da2.html",
            "Intel Ethernet Server Adapter X520-DA2",
        )

        async def mock_query(selector):
            if "/products/sku/" in selector:
                return [wrong_link, correct_link]
            return []

        page.query_selector_all = AsyncMock(side_effect=mock_query)

        result = await checker._find_product_link(page, "Intel Ethernet X520-DA2")
        assert result is not None
        assert "82599" in result

    async def test_correct_link_not_first_in_dom(self):
        """The best match should win even when it appears later in the DOM."""
        checker = IntelARKChecker()
        page = AsyncMock()

        links = [
            _make_mock_link(
                "/products/sku/00001/x540-t2.html",
                "Intel Ethernet Converged Network Adapter X540-T2",
            ),
            _make_mock_link(
                "/products/sku/00002/x527-da2.html",
                "Intel Ethernet Converged Network Adapter X527-DA2",
            ),
            _make_mock_link(
                "/products/sku/00003/x520-da2.html",
                "Intel Ethernet Server Adapter X520-DA2",
            ),
        ]

        async def mock_query(selector):
            if "/products/sku/" in selector:
                return links
            return []

        page.query_selector_all = AsyncMock(side_effect=mock_query)

        result = await checker._find_product_link(page, "Intel Ethernet X520-DA2")
        assert result is not None
        assert "00003" in result

    async def test_family_match_beats_unrelated(self):
        """X520-SR1 (family X520) should score higher than I350-T4."""
        checker = IntelARKChecker()
        page = AsyncMock()

        unrelated = _make_mock_link(
            "/products/sku/00001/i350-t4.html",
            "Intel Ethernet Server Adapter I350-T4",
        )
        family_match = _make_mock_link(
            "/products/sku/00002/x520-sr1.html",
            "Intel Ethernet Server Adapter X520-SR1",
        )

        async def mock_query(selector):
            if "/products/sku/" in selector:
                return [unrelated, family_match]
            return []

        page.query_selector_all = AsyncMock(side_effect=mock_query)

        result = await checker._find_product_link(page, "Intel Ethernet X520-DA2")
        assert result is not None
        assert "00002" in result

    async def test_no_links_returns_none(self):
        """When no product links exist, return None."""
        checker = IntelARKChecker()
        page = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])

        result = await checker._find_product_link(page, "Intel Ethernet X520-DA2")
        assert result is None
