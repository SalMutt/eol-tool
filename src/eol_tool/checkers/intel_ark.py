"""Intel ARK scraper for CPU lifecycle data.

Fetches real lifecycle data from ark.intel.com product pages including
Marketing Status, Launch Date, and End of Servicing Updates Date.
Only uses Playwright for scraping. Only processes CPU category models -
NICs, SSDs, and optics are left to the static intel.py checker.
"""

import logging
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

_CACHE_DB = Path.home() / ".cache" / "eol-tool" / "intel_ark.db"
_CACHE_TTL_DAYS = 30
_NOT_FOUND_TTL_DAYS = 1

_ARK_BASE_URL = "https://ark.intel.com"
_ARK_SEARCH_URL = "https://ark.intel.com/content/www/us/en/ark.html"
_INTEL_SEARCH_URL = "https://www.intel.com/content/www/us/en/search.html"


# ── SQLite cache helpers ─────────────────────────────────────────────


def _init_cache_db() -> sqlite3.Connection:
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_CACHE_DB))
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
    conn.commit()
    return conn


def _get_cached(conn: sqlite3.Connection, key: str) -> dict | None:
    row = conn.execute(
        "SELECT result_status, marketing_status, launch_date, eol_date, "
        "servicing_status, cached_at FROM ark_cache WHERE model_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    cached_at = datetime.fromisoformat(row[5])
    ttl = _NOT_FOUND_TTL_DAYS if row[0] == "not_found" else _CACHE_TTL_DAYS
    if datetime.now() - cached_at > timedelta(days=ttl):
        return None
    return {
        "result_status": row[0],
        "marketing_status": row[1] or "",
        "launch_date": row[2] or "",
        "eol_date": row[3] or "",
        "servicing_status": row[4] or "",
    }


def _set_cached(conn: sqlite3.Connection, key: str, data: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO ark_cache
           (model_key, result_status, marketing_status, launch_date,
            eol_date, servicing_status, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            key,
            data.get("result_status", ""),
            data.get("marketing_status", ""),
            data.get("launch_date", ""),
            data.get("eol_date", ""),
            data.get("servicing_status", ""),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


# ── Date parsing ─────────────────────────────────────────────────────


def _parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    date_str = date_str.strip().rstrip(".")
    for fmt in (
        "%B %d, %Y",
        "%B %d %Y",
        "%A %B %d %Y",
        "%A %B %d, %Y",
        "%A, %B %d, %Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    q_match = re.match(r"Q(\d)\s*'?(\d{2,4})", date_str)
    if q_match:
        q = int(q_match.group(1))
        yr = q_match.group(2)
        year = int(yr) if len(yr) == 4 else 2000 + int(yr)
        month = q * 3
        if month == 12:
            return date(year, 12, 31)
        return date(year, month + 1, 1) - timedelta(days=1)
    return None


# ── Checker ──────────────────────────────────────────────────────────


class IntelARKChecker(BaseChecker):
    """Intel ARK scraper for CPU lifecycle data."""

    manufacturer_name = "Intel"
    priority = 25
    rate_limit = 5
    base_url = "https://ark.intel.com"

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
                logger.error("Failed to launch Chromium for Intel ARK: %s", exc)
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

    # ── Public API ────────────────────────────────────────────────

    async def check(self, model: HardwareModel) -> EOLResult:
        if model.category.lower() != "cpu":
            return self._make_not_found(model, "non-cpu-deferred-to-static-checker")

        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("playwright not installed - Intel ARK scraper unavailable")
            return self._make_not_found(model, "playwright-not-installed")

        if self._checker_disabled:
            return self._make_not_found(model, "checker-disabled-chromium-missing")

        model_key = _normalize_key(model.model)
        conn = _init_cache_db()
        try:
            cached = _get_cached(conn, model_key)
            if cached is not None:
                logger.info("ARK cache hit: %s", model_key)
                return _to_result(model, cached)

            data = await self._playwright_lookup(model_key)

            if data is None:
                _set_cached(conn, model_key, {"result_status": "not_found"})
                return self._make_not_found(model, "not-found-on-intel-ark")

            if data.get("result_status") == "timeout":
                _set_cached(conn, model_key, {"result_status": "not_found"})
                return self._make_not_found(model, "page-timeout")

            _set_cached(conn, model_key, data)
            return _to_result(model, data)
        finally:
            conn.close()

    # ── Playwright lookup ────────────────────────────────────────

    async def _playwright_lookup(self, model_key: str) -> dict | None:
        if not self._browser:
            return None
        page = None
        try:
            page = await self._browser.new_page()
            page.set_default_timeout(20000)

            search_term = _prepare_search_term(model_key)
            logger.info("ARK: searching for '%s' (from key '%s')", search_term, model_key)

            # Step 1: Navigate to Intel search page with product filter
            encoded = search_term.replace(" ", "%20")
            search_url = f"{_INTEL_SEARCH_URL}#q={encoded}&sort=relevancy"
            logger.info("ARK: navigating to Intel search: %s", search_url)
            await page.goto(search_url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(5000)

            title = await page.title()
            logger.info("ARK: search page loaded, title='%s', URL=%s", title, page.url)

            # Step 2: Find product specification links in results
            spec_url = await self._find_product_link(page, search_term)

            if not spec_url:
                logger.warning("ARK: no product links in Intel search, trying ARK search page")
                spec_url = await self._try_ark_search(page, search_term)

            if not spec_url:
                logger.warning("ARK: no product page found for '%s'", model_key)
                return None

            # Step 3: Navigate to product specifications page
            if not spec_url.startswith("http"):
                spec_url = f"https://www.intel.com{spec_url}"
            logger.info("ARK: navigating to product page: %s", spec_url)
            await page.goto(spec_url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(2000)

            logger.info("ARK: on product page: %s", page.url)
            body = await page.inner_text("body")
            data = _extract_from_text(body)

            if data:
                logger.info(
                    "ARK: extracted - marketing_status=%s, launch_date=%s, "
                    "eol_date=%s, servicing_status=%s",
                    data.get("marketing_status"),
                    data.get("launch_date"),
                    data.get("eol_date"),
                    data.get("servicing_status"),
                )
            else:
                logger.warning("ARK: no lifecycle data on product page")

            return data

        except Exception as exc:
            if "timeout" in str(exc).lower() or "Timeout" in type(exc).__name__:
                logger.warning("ARK timeout for %s: %s", model_key, exc)
                return {"result_status": "timeout"}
            logger.warning("ARK Playwright error for %s: %s", model_key, exc)
            return None
        finally:
            if page:
                await page.close()

    async def _find_product_link(self, page, search_term: str) -> str | None:
        """Find a product specifications URL from Intel search results."""
        # Look for /products/sku/ links (new Intel.com format)
        links = await page.query_selector_all("a[href*='/products/sku/']")
        for link in links:
            if not await link.is_visible():
                continue
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()
            logger.info("ARK: found product link: '%s' -> %s", text[:60], href[:100])
            if "/specifications" in href:
                return href
            # Rewrite to specifications URL
            base = href.rsplit("/", 1)[0]
            return f"{base}/specifications.html"

        # Also check for ARK-format links
        links = await page.query_selector_all("a[href*='/ark/products/']")
        for link in links:
            if not await link.is_visible():
                continue
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()
            logger.info("ARK: found ARK product link: '%s' -> %s", text[:60], href[:100])
            return href

        return None

    async def _try_ark_search(self, page, search_term: str) -> str | None:
        """Try Intel ARK search page as fallback."""
        try:
            logger.info("ARK: trying ARK search page at %s", _ARK_SEARCH_URL)
            await page.goto(_ARK_SEARCH_URL, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

            title = await page.title()
            logger.info("ARK: ARK page loaded, title='%s'", title)

            # Find search input
            search = None
            for selector in [
                "input#FormSearchValue",
                "input[type=search]",
                "input[type=text]",
            ]:
                search = await page.query_selector(selector)
                if search:
                    logger.info("ARK: found search input with selector '%s'", selector)
                    break

            if not search:
                logger.warning("ARK: search input not found on ARK page")
                return None

            await search.click()
            await search.fill(search_term)
            logger.info("ARK: typed search term '%s'", search_term)
            await search.press("Enter")
            await page.wait_for_load_state("networkidle", timeout=15000)
            await page.wait_for_timeout(3000)

            logger.info("ARK: after ARK search, URL: %s", page.url)

            # Look for product links in the redirected search results
            return await self._find_product_link(page, search_term)
        except Exception as exc:
            logger.warning("ARK: ARK search fallback failed: %s", exc)
            return None

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _make_not_found(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="intel-ark",
            confidence=0,
            notes=reason,
        )


# ── Module-level helpers ─────────────────────────────────────────────


def _normalize_key(model_str: str) -> str:
    s = re.sub(r"^(?:INTEL\s+)?(?:XEON\s+)?", "", model_str.strip(), flags=re.IGNORECASE)
    return s.strip()


def _prepare_search_term(model_key: str) -> str:
    """Convert a normalized model key to a searchable term for Intel ARK."""
    s = model_key.strip()

    # Strip residual XEON/INTEL prefix
    s = re.sub(r"^(?:INTEL\s+)?(?:XEON\s+)?", "", s, flags=re.IGNORECASE).strip()

    # Scalable Xeons: "6132 GOLD" -> "Xeon Gold 6132"
    scalable = re.match(r"^(\d{4,5})\s+(GOLD|SILVER|BRONZE|PLATINUM)$", s, re.IGNORECASE)
    if scalable:
        return f"Xeon {scalable.group(2).capitalize()} {scalable.group(1)}"

    # E-2xxx series: "E-2136" -> "Xeon E-2136"
    if re.match(r"^E-2\d{3}", s, re.IGNORECASE):
        return f"Xeon {s}"

    # Add space before version suffix: "E5-2683V4" -> "E5-2683 v4"
    s = re.sub(r"([A-Za-z0-9-])V(\d+)$", r"\1 v\2", s, flags=re.IGNORECASE)

    return s


def _extract_from_html(html: str) -> dict | None:
    data: dict[str, str] = {}
    ms = re.search(
        r"Marketing\s+Status.*?(Discontinued|Launched|End\s+of\s+Life)",
        html,
        re.I | re.S,
    )
    if ms:
        data["marketing_status"] = ms.group(1).strip()
    eos = re.search(
        r"End\s+of\s+Servicing\s+Updates?\s+Date.*?"
        r"(\w+\s+\w+\s+\d{1,2},?\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})",
        html,
        re.I | re.S,
    )
    if eos:
        data["eol_date"] = eos.group(1).strip()
    ld = re.search(
        r"Launch\s+Date.*?(Q\d\s*'?\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})",
        html,
        re.I | re.S,
    )
    if ld:
        data["launch_date"] = ld.group(1).strip()
    return data if data.get("marketing_status") else None


def _extract_from_text(text: str) -> dict | None:
    data: dict[str, str] = {}
    if re.search(r"Marketing\s+Status\s*Discontinued", text, re.I):
        data["marketing_status"] = "Discontinued"
    elif re.search(r"Marketing\s+Status\s*Launched", text, re.I):
        data["marketing_status"] = "Launched"
    elif re.search(r"Marketing\s+Status\s*End\s+of\s+Life", text, re.I):
        data["marketing_status"] = "End of Life"

    eos = re.search(
        r"End\s+of\s+Servicing\s+Updates?\s+Date\s*"
        r"(\w+,?\s+\w+\s+\d{1,2},?\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})",
        text,
        re.I,
    )
    if eos:
        data["eol_date"] = eos.group(1).strip()

    ld = re.search(r"Launch\s+Date\s*(Q\d\s*'?\d{2,4})", text, re.I)
    if ld:
        data["launch_date"] = ld.group(1).strip()

    sv = re.search(r"Servicing\s+Status\s*(\w[\w\s]*?)(?:\n|$)", text, re.I)
    if sv:
        data["servicing_status"] = sv.group(1).strip()

    return data if data.get("marketing_status") else None


def _to_result(model: HardwareModel, data: dict) -> EOLResult:
    if data.get("result_status") in ("not_found", "timeout"):
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="intel-ark",
            confidence=0,
            notes=f"cached-{data.get('result_status', 'not_found')}",
        )

    ms = data.get("marketing_status", "").lower()
    if "discontinued" in ms or "end of life" in ms:
        status = EOLStatus.EOL
    elif "launched" in ms:
        status = EOLStatus.ACTIVE
    else:
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="intel-ark",
            confidence=0,
            notes="unrecognised-marketing-status",
        )

    eol_date = _parse_date(data.get("eol_date", ""))
    notes_parts = []
    if data.get("marketing_status"):
        notes_parts.append(f"Marketing Status: {data['marketing_status']}")
    if data.get("launch_date"):
        notes_parts.append(f"Launch: {data['launch_date']}")
    if data.get("servicing_status"):
        notes_parts.append(f"Servicing: {data['servicing_status']}")

    return EOLResult(
        model=model,
        status=status,
        eol_date=eol_date,
        checked_at=datetime.now(),
        source_name="intel-ark",
        confidence=90,
        notes="; ".join(notes_parts),
        date_source="manufacturer_confirmed",
        eol_reason=EOLReason.MANUFACTURER_DECLARED,
        risk_category=(RiskCategory.SUPPORT if status == EOLStatus.EOL else RiskCategory.NONE),
    )
