"""Cisco EOL checker with Playwright bulletin scraping and static fallback.

Uses Playwright to search for Cisco EOL bulletins via Cisco search and
Google fallback, then extracts dates from the bulletin page. Falls back
to static classification when Playwright is unavailable or scraping fails.
"""

import asyncio
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory
from ..retry import RetryConfig, RetryExhausted, with_retry

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

_CISCO_PREFIX_RE = re.compile(r"^CISCO\s+", re.IGNORECASE)

# -- Hard timeout for the entire Playwright lookup per model
_SCRAPE_TIMEOUT_SECONDS = 30

# -- SQLite cache --------------------------------------------------------

_CACHE_DB = Path.home() / ".cache" / "eol-tool" / "cisco_eol.db"
_CACHE_TTL_DAYS = 30


def _init_cache_db() -> sqlite3.Connection:
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_CACHE_DB))
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
    conn.commit()
    return conn


def _get_cached(conn: sqlite3.Connection, key: str) -> dict | None:
    row = conn.execute(
        "SELECT result_status, eol_date, eos_date, eo_sw_maint, "
        "eo_vuln_support, cached_at FROM cisco_cache WHERE model_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    cached_at = datetime.fromisoformat(row[5])
    if datetime.now() - cached_at > timedelta(days=_CACHE_TTL_DAYS):
        return None
    return {
        "result_status": row[0] or "",
        "eol_date": row[1] or "",
        "eos_date": row[2] or "",
        "eo_sw_maint": row[3] or "",
        "eo_vuln_support": row[4] or "",
    }


def _set_cached(conn: sqlite3.Connection, key: str, data: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO cisco_cache
           (model_key, result_status, eol_date, eos_date,
            eo_sw_maint, eo_vuln_support, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            key,
            data.get("result_status", ""),
            data.get("eol_date", ""),
            data.get("eos_date", ""),
            data.get("eo_sw_maint", ""),
            data.get("eo_vuln_support", ""),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


# -- Date parsing --------------------------------------------------------


def _parse_cisco_date(date_str: str) -> date | None:
    if not date_str:
        return None
    date_str = date_str.strip().rstrip(".")
    for fmt in ("%B %d, %Y", "%B %d %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


# -- Static fallback rules -----------------------------------------------

_PRODUCT_RULES: list[tuple[str, EOLStatus, RiskCategory, str, EOLReason]] = [
    ("ASA5516-FPWR-K9", EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco ASA 5516-X with FirePOWER - EOL firewall",
     EOLReason.PRODUCT_DISCONTINUED),
    ("ASA5506", EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco ASA 5506-X - EOL firewall",
     EOLReason.PRODUCT_DISCONTINUED),
    ("ASA5525", EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco ASA 5525-X - EOL firewall",
     EOLReason.PRODUCT_DISCONTINUED),
    ("ASA5515", EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco ASA 5515-X - EOL firewall",
     EOLReason.PRODUCT_DISCONTINUED),
    ("ASA5505", EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco ASA 5505 - EOL firewall",
     EOLReason.PRODUCT_DISCONTINUED),
    ("QSFP+-UNIV", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Cisco 40G QSFP+ Universal optic - active",
     EOLReason.NONE),
    ("40G QSFP", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Cisco 40G QSFP optic - active",
     EOLReason.NONE),
]

_REGEX_RULES: list[tuple[re.Pattern, EOLStatus, RiskCategory, str, EOLReason]] = [
    (re.compile(r"AIRONET\s*3700|3700\s*ACCESS\s*POINT", re.IGNORECASE),
     EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco Aironet 3700 wireless AP - EOL",
     EOLReason.PRODUCT_DISCONTINUED),
    (re.compile(r"2500\s*WIRELESS\s*CONTROLLER", re.IGNORECASE),
     EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco 2500 Wireless Controller - EOL",
     EOLReason.PRODUCT_DISCONTINUED),
    (re.compile(r"ASA\s*\d{4}", re.IGNORECASE),
     EOLStatus.EOL, RiskCategory.SECURITY,
     "Cisco ASA series firewall - EOL (all ASA hardware is end of sale)",
     EOLReason.PRODUCT_DISCONTINUED),
]


# -- Async cache wrappers ------------------------------------------------


async def _async_cache_get(key: str) -> dict | None:
    def _sync():
        conn = _init_cache_db()
        try:
            return _get_cached(conn, key)
        finally:
            conn.close()
    return await asyncio.to_thread(_sync)


async def _async_cache_set(key: str, data: dict) -> None:
    def _sync():
        conn = _init_cache_db()
        try:
            _set_cached(conn, key, data)
        finally:
            conn.close()
    await asyncio.to_thread(_sync)


# -- Checker -------------------------------------------------------------


class CiscoChecker(BaseChecker):
    """Cisco EOL checker with Playwright scraping and static fallback."""

    manufacturer_name = "Cisco"
    rate_limit = 5
    priority = 25
    base_url = ""

    source_name = "cisco-eol"

    def __init__(self) -> None:
        super().__init__()
        self._browser = None
        self._pw_context = None
        self._checker_disabled = False

    async def __aenter__(self):
        self = await super().__aenter__()
        if PLAYWRIGHT_AVAILABLE and not self._checker_disabled:
            try:
                self._pw_context = await async_playwright().start()
                self._browser = await self._pw_context.chromium.launch(headless=True)
            except Exception as exc:
                logger.error("Failed to launch Chromium for Cisco EOL: %s", exc)
                self._checker_disabled = True
                if self._pw_context:
                    await self._pw_context.stop()
                    self._pw_context = None
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw_context:
            await self._pw_context.stop()
            self._pw_context = None
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # Try SQLite cache first
        cached = await _async_cache_get(normalized)
        if cached is not None:
            if cached.get("eol_date") or cached.get("eos_date"):
                logger.info("Cisco cache hit with dates: %s", normalized)
                return _cached_to_result(model, cached)
            # Cached but no dates -- fall through to static

        # Try Playwright scraping with hard timeout
        if PLAYWRIGHT_AVAILABLE and self._browser and not self._checker_disabled:
            playwright_config = RetryConfig.from_env(
                max_retries=2, base_delay=5.0,
            )

            async def _do_scrape():
                return await asyncio.wait_for(
                    self._scrape_bulletin(normalized),
                    timeout=_SCRAPE_TIMEOUT_SECONDS,
                )

            try:
                bulletin_data = await with_retry(
                    _do_scrape, config=playwright_config, log=logger,
                )
                if bulletin_data and (
                    bulletin_data.get("eol_date") or bulletin_data.get("eos_date")
                ):
                    await _async_cache_set(normalized, bulletin_data)
                    return _cached_to_result(model, bulletin_data)
            except (RetryExhausted, asyncio.TimeoutError):
                logger.warning(
                    "Cisco lookup for %s failed after retries, using static rules",
                    normalized,
                )

        # Fall back to static classification
        return self._static_classify(model, normalized)

    async def _scrape_bulletin(self, normalized: str) -> dict | None:
        """Search for and scrape a Cisco EOL bulletin.

        Strategy:
        1. Cisco search: search.cisco.com for "<model> end of life bulletin"
        2. If no bulletin found, Google fallback: site:cisco.com search
        3. Navigate to bulletin page and extract dates table
        """
        page = None
        try:
            page = await self._browser.new_page()
            page.set_default_timeout(20000)

            # Step 1: Cisco search
            search_terms = self._build_search_terms(normalized)
            cisco_search_url = (
                "https://search.cisco.com/search?query="
                + quote_plus(search_terms + " end of life bulletin")
            )
            logger.info("[cisco-scrape] Step 1: Cisco search: %s", cisco_search_url)

            await page.goto(
                cisco_search_url, wait_until="networkidle", timeout=20000,
            )
            logger.info("[cisco-scrape] Step 1: search page loaded (networkidle)")

            # Look for EOL bulletin link in Cisco search results
            bulletin_url = await self._find_bulletin_link(page)
            if bulletin_url:
                logger.info(
                    "[cisco-scrape] Step 1: found bulletin URL: %s", bulletin_url,
                )
                dates = await self._extract_dates_from_url(page, bulletin_url)
                if dates:
                    logger.info(
                        "[cisco-scrape] Step 1: extracted dates: %s", dates,
                    )
                    return dates
                logger.info("[cisco-scrape] Step 1: no dates on bulletin page")
            else:
                logger.info("[cisco-scrape] Step 1: no bulletin link in Cisco search")

            # Step 2: Google fallback
            google_query = (
                f"site:cisco.com {search_terms} end-of-sale end-of-life bulletin"
            )
            google_url = (
                "https://www.google.com/search?q=" + quote_plus(google_query)
            )
            logger.info("[cisco-scrape] Step 2: Google fallback: %s", google_url)

            await page.goto(
                google_url, wait_until="domcontentloaded", timeout=15000,
            )
            logger.info("[cisco-scrape] Step 2: Google page loaded")

            # Find cisco.com EOL bulletin link in Google results
            bulletin_url = await self._find_google_bulletin_link(page)
            if bulletin_url:
                logger.info(
                    "[cisco-scrape] Step 2: Google found bulletin: %s", bulletin_url,
                )
                dates = await self._extract_dates_from_url(page, bulletin_url)
                if dates:
                    logger.info(
                        "[cisco-scrape] Step 2: extracted dates: %s", dates,
                    )
                    return dates
                logger.info("[cisco-scrape] Step 2: no dates on Google-found page")
            else:
                logger.info("[cisco-scrape] Step 2: no bulletin link in Google results")

            logger.warning(
                "[cisco-scrape] No EOL bulletin found for %s", normalized,
            )
            return None

        except Exception as exc:
            logger.warning(
                "[cisco-scrape] Scrape failed for %s: %s", normalized, exc,
            )
            return None
        finally:
            if page:
                await page.close()

    async def _find_bulletin_link(self, page) -> str | None:
        """Find an EOL bulletin link in Cisco search results."""
        links = await page.query_selector_all("a[href]")
        logger.info(
            "[cisco-scrape] Scanning %d links for bulletin URL", len(links),
        )

        # Priority 1: links with eos-eol in URL (direct bulletin links)
        for link in links:
            href = await link.get_attribute("href") or ""
            if "eos-eol" in href.lower() and "cisco.com" in href.lower():
                if not href.startswith("http"):
                    href = "https://www.cisco.com" + href
                return href

        # Priority 2: links mentioning end-of-life/end-of-sale in text
        for link in links:
            href = await link.get_attribute("href") or ""
            if "cisco.com" not in href.lower():
                continue
            try:
                text = (await link.inner_text()).lower()
            except Exception:
                continue
            if "end-of-sale" in text or "end-of-life" in text or "end of sale" in text:
                if not href.startswith("http"):
                    href = "https://www.cisco.com" + href
                return href

        return None

    async def _find_google_bulletin_link(self, page) -> str | None:
        """Find a Cisco EOL bulletin link in Google search results."""
        links = await page.query_selector_all("a[href]")
        logger.info(
            "[cisco-scrape] Scanning %d Google result links", len(links),
        )

        for link in links:
            href = await link.get_attribute("href") or ""
            href_lower = href.lower()
            # Look for direct cisco.com links with EOL indicators
            if "cisco.com" in href_lower and (
                "eos-eol" in href_lower
                or "end-of-life" in href_lower
                or "eol-notice" in href_lower
            ):
                # Extract actual URL from Google redirect wrapper
                if "/url?" in href:
                    from urllib.parse import parse_qs, urlparse

                    parsed = parse_qs(urlparse(href).query)
                    href = parsed.get("q", [href])[0]
                if not href.startswith("http"):
                    href = "https://www.cisco.com" + href
                return href

        # Broader fallback: any cisco.com/c/en link (product collateral)
        for link in links:
            href = await link.get_attribute("href") or ""
            if "cisco.com/c/en" in href.lower() and "collateral" in href.lower():
                if "/url?" in href:
                    from urllib.parse import parse_qs, urlparse

                    parsed = parse_qs(urlparse(href).query)
                    href = parsed.get("q", [href])[0]
                if not href.startswith("http"):
                    href = "https://www.cisco.com" + href
                return href

        return None

    async def _extract_dates_from_url(self, page, url: str) -> dict | None:
        """Navigate to a bulletin URL and extract dates."""
        logger.info("[cisco-scrape] Navigating to bulletin: %s", url)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            body = await page.inner_text("body")
            logger.info(
                "[cisco-scrape] Bulletin page loaded, body length: %d chars",
                len(body),
            )
            dates = _extract_bulletin_dates(body)
            return dates
        except Exception as exc:
            logger.warning(
                "[cisco-scrape] Failed to load bulletin %s: %s", url, exc,
            )
            return None

    @staticmethod
    def _build_search_terms(normalized: str) -> str:
        """Build search-friendly terms from a normalized model string."""
        # Strip common Cisco suffixes (-K9, -FPWR, -SEC-BUN, etc.)
        s = re.sub(r"-(K\d|FPWR|SEC|BUN|BDL).*$", "", normalized)
        # Insert space between letter/number boundaries for search
        s = re.sub(r"([A-Z])(\d)", r"\1 \2", s)
        return s

    def _static_classify(
        self, model: HardwareModel, normalized: str,
    ) -> EOLResult:
        """Classify using static rules only (no dates, date_source='none')."""
        for key, status, risk, notes, reason in _PRODUCT_RULES:
            if key.upper() in normalized:
                return self._make_static_result(model, status, risk, notes, reason)

        for pattern, status, risk, notes, reason in _REGEX_RULES:
            if pattern.search(normalized):
                return self._make_static_result(model, status, risk, notes, reason)

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="cisco-product-rules",
            confidence=50,
            notes="cisco-model-not-classified",
            date_source="none",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        s = _CISCO_PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _make_static_result(
        model: HardwareModel,
        status: EOLStatus,
        risk: RiskCategory,
        notes: str,
        eol_reason: EOLReason,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="cisco-product-rules",
            confidence=70,
            notes=notes,
            eol_reason=eol_reason,
            risk_category=risk,
            date_source="none",
        )


# -- Module helpers -------------------------------------------------------


def _extract_bulletin_dates(text: str) -> dict | None:
    """Extract EOL dates from Cisco bulletin page text.

    Cisco bulletin pages have dates in table cells separated from labels
    by description text and whitespace, so we use re.DOTALL for cross-line
    matching with non-greedy quantifiers.
    """
    data: dict[str, str] = {"result_status": "found"}
    _DATE_RE = r"(\w+\s+\d{1,2},?\s+\d{4})"
    _flags = re.I | re.DOTALL

    # End-of-Sale Date (date appears after label + description text)
    eos_sale = re.search(
        r"End.of.Sale\s+Date.*?" + _DATE_RE, text, _flags,
    )
    if eos_sale:
        data["eol_date"] = eos_sale.group(1).strip()

    # Last Date of Support
    lds = re.search(
        r"Last\s+Date\s+of\s+Support.*?" + _DATE_RE, text, _flags,
    )
    if lds:
        data["eos_date"] = lds.group(1).strip()

    # End-of-SW-Maintenance
    sw_maint = re.search(
        r"End.of.(?:SW|Software).Maintenance.*?" + _DATE_RE, text, _flags,
    )
    if sw_maint:
        data["eo_sw_maint"] = sw_maint.group(1).strip()

    # End of Security/Vulnerability Support
    vuln = re.search(
        r"End.of.(?:Security|Vulnerability).*?Support.*?" + _DATE_RE, text, _flags,
    )
    if vuln:
        data["eo_vuln_support"] = vuln.group(1).strip()

    if data.get("eol_date") or data.get("eos_date"):
        return data
    return None


def _cached_to_result(model: HardwareModel, data: dict) -> EOLResult:
    """Convert cached bulletin data to EOLResult."""
    eol_date = _parse_cisco_date(data.get("eol_date", ""))
    eos_date = _parse_cisco_date(data.get("eos_date", ""))

    notes_parts = []
    if data.get("eol_date"):
        notes_parts.append(f"End-of-Sale: {data['eol_date']}")
    if data.get("eos_date"):
        notes_parts.append(f"Last Date of Support: {data['eos_date']}")
    if data.get("eo_sw_maint"):
        notes_parts.append(f"End-of-SW-Maintenance: {data['eo_sw_maint']}")
    if data.get("eo_vuln_support"):
        notes_parts.append(f"End-of-Vuln-Support: {data['eo_vuln_support']}")

    return EOLResult(
        model=model,
        status=EOLStatus.EOL,
        eol_date=eol_date,
        eos_date=eos_date,
        checked_at=datetime.now(),
        source_name="cisco-eol-bulletin",
        confidence=95,
        notes="; ".join(notes_parts),
        date_source="manufacturer_confirmed",
        eol_reason=EOLReason.MANUFACTURER_DECLARED,
        risk_category=RiskCategory.SECURITY,
    )
