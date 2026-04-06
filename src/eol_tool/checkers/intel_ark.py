"""Intel ARK scraper for CPU, NIC, SSD, and optic lifecycle data.

Fetches real lifecycle data from ark.intel.com product pages including
Marketing Status, Launch Date, and End of Servicing Updates Date.
Uses Playwright for scraping. Falls back to the static intel.py checker
for models not found on ARK.
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

_SUPPORTED_CATEGORIES = frozenset({"cpu", "nic", "ssd", "optic"})


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


def _parse_launch_date(date_str: str) -> date | None:
    """Parse a launch/release date string, using quarter-start for Qn'YY."""
    if not date_str:
        return None
    date_str = date_str.strip().rstrip(".")
    q_match = re.match(r"Q(\d)\s*'?(\d{2,4})", date_str)
    if q_match:
        q = int(q_match.group(1))
        yr = q_match.group(2)
        year = int(yr) if len(yr) == 4 else 2000 + int(yr)
        month = {1: 1, 2: 4, 3: 7, 4: 10}.get(q, 1)
        return date(year, month, 1)
    return _parse_date(date_str)


# ── Checker ──────────────────────────────────────────────────────────


class IntelARKChecker(BaseChecker):
    """Intel ARK scraper for CPU, NIC, SSD, and optic lifecycle data."""

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
        category = model.category.lower()
        if category not in _SUPPORTED_CATEGORIES:
            return self._make_not_found(model, "unsupported-category")

        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("playwright not installed - Intel ARK scraper unavailable")
            return self._make_not_found(model, "playwright-not-installed")

        if self._checker_disabled:
            return self._make_not_found(model, "checker-disabled-chromium-missing")

        model_key = _normalize_key(model.model, category)
        cache_key = f"{category}:{model_key}"
        conn = _init_cache_db()
        try:
            cached = _get_cached(conn, cache_key)
            if cached is not None:
                logger.info("ARK cache hit: %s", cache_key)
                return _to_result(model, cached)

            data = await self._playwright_lookup(model_key, category)

            if data is None:
                _set_cached(conn, cache_key, {"result_status": "not_found"})
                return self._make_not_found(model, "not-found-on-intel-ark")

            if data.get("result_status") == "timeout":
                _set_cached(conn, cache_key, {"result_status": "not_found"})
                return self._make_not_found(model, "page-timeout")

            _set_cached(conn, cache_key, data)
            return _to_result(model, data)
        finally:
            conn.close()

    # ── Playwright lookup ────────────────────────────────────────

    async def _playwright_lookup(self, model_key: str, category: str = "cpu") -> dict | None:
        if not self._browser:
            return None
        page = None
        try:
            page = await self._browser.new_page()
            page.set_default_timeout(20000)

            search_term = _prepare_search_term(model_key, category)
            logger.info("ARK: searching for '%s' (from key '%s')", search_term, model_key)

            spec_url = None

            if category in ("nic", "ssd"):
                # NICs and SSDs: try ARK direct search first
                spec_url = await self._try_ark_direct_search(page, search_term)
                if not spec_url:
                    logger.info("ARK: direct search miss, falling back to intel.com search")
                    spec_url = await self._try_intel_search(page, search_term)
            else:
                # CPUs and optics: use intel.com search
                spec_url = await self._try_intel_search(page, search_term)

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

    async def _try_ark_direct_search(self, page, search_term: str) -> str | None:
        """Search ARK directly for a product (preferred for NICs/SSDs)."""
        encoded = search_term.replace(" ", "+")
        url = (
            "https://ark.intel.com/content/www/us/en/ark/search.html"
            f"?_charset_=UTF-8&q={encoded}"
        )
        logger.info("ARK: direct ARK search: %s", url)
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(3000)
        except Exception as exc:
            logger.warning("ARK: direct ARK search navigation failed: %s", exc)
            return None

        current_url = page.url
        logger.info("ARK: after direct search, URL: %s", current_url)

        # ARK may redirect directly to a product page on exact match
        if "/products/sku/" in current_url or "/ark/products/" in current_url:
            logger.info("ARK: direct search redirected to product page")
            return current_url

        # Otherwise look for product links in search results
        return await self._find_product_link(page, search_term)

    async def _try_intel_search(self, page, search_term: str) -> str | None:
        """Search via intel.com search page (original strategy)."""
        encoded = search_term.replace(" ", "%20")
        search_url = f"{_INTEL_SEARCH_URL}#q={encoded}&sort=relevancy"
        logger.info("ARK: navigating to Intel search: %s", search_url)
        await page.goto(search_url, wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(5000)

        title = await page.title()
        logger.info("ARK: search page loaded, title='%s', URL=%s", title, page.url)

        spec_url = await self._find_product_link(page, search_term)

        if not spec_url:
            logger.warning("ARK: no product links in Intel search, trying ARK search page")
            spec_url = await self._try_ark_search(page, search_term)

        return spec_url

    async def _find_product_link(self, page, search_term: str) -> str | None:
        """Find the best-matching product specifications URL from search results."""
        selectors = [
            "a[href*='/products/sku/']",
            "a[href*='/ark/products/']",
            "a[href*='ark.intel.com/content/www/us/en/ark/products']",
            "a.ark-accessible-color",
            "a.result-title[href*='ark']",
            ".search-result a[href*='ark']",
        ]

        # Collect all visible product links
        seen_hrefs: set[str] = set()
        candidates: list[tuple[str, str]] = []  # (href, text)
        for selector in selectors:
            links = await page.query_selector_all(selector)
            for link in links:
                if not await link.is_visible():
                    continue
                href = await link.get_attribute("href") or ""
                if not href or href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                text = (await link.inner_text()).strip()
                candidates.append((href, text))

        if not candidates:
            # Debug: log visible links to help diagnose search failures
            all_links = await page.query_selector_all("a[href]")
            visible_count = 0
            for link in all_links[:50]:
                if await link.is_visible():
                    href = await link.get_attribute("href") or ""
                    if visible_count < 5:
                        logger.debug("ARK: visible link on page: %s", href[:120])
                    visible_count += 1
            logger.info(
                "ARK: %d visible links found, none matched product selectors",
                visible_count,
            )
            return None

        # Score candidates by relevance to search term
        core = _extract_core_model(search_term)
        core_lower = core.lower()
        family = core.split("-")[0].lower() if "-" in core else ""
        term_words = {w.lower() for w in search_term.split() if len(w) > 2}

        scored: list[tuple[int, str, str]] = []
        for href, text in candidates:
            text_lower = text.lower()
            if core_lower in text_lower:
                score = 100
            elif family and family in text_lower:
                score = 50
            elif term_words & {w.lower() for w in text.split()}:
                score = 10
            else:
                score = 1
            scored.append((score, href, text))

        scored.sort(key=lambda t: t[0], reverse=True)

        # Log top candidates for diagnostics
        for score, href, text in scored[:3]:
            logger.info(
                "ARK: candidate (score=%d): '%s' -> %s", score, text[:60], href[:100]
            )

        best_score, best_href, best_text = scored[0]
        if best_score < 50:
            logger.info("ARK: best match score %d too low (need >=50), rejecting", best_score)
            return None
        if "/products/sku/" in best_href:
            if "/specifications" in best_href:
                return best_href
            base = best_href.rsplit("/", 1)[0]
            return f"{base}/specifications.html"
        return best_href

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


def _extract_core_model(search_term: str) -> str:
    """Extract the core model identifier from an ARK search term.

    'Intel Ethernet X520-DA2' -> 'X520-DA2'
    'Intel SSD S3500' -> 'S3500'
    'Intel SSD D3-S4510' -> 'D3-S4510'
    'E5-2683V4' -> 'E5-2683V4'
    """
    s = search_term.strip()
    for prefix in ("Intel Ethernet ", "Intel SSD ", "Intel "):
        if s.upper().startswith(prefix.upper()):
            s = s[len(prefix) :]
            break
    return s.strip()


def _normalize_key(model_str: str, category: str = "cpu") -> str:
    cat = category.lower()
    s = model_str.strip()

    if cat == "nic":
        s = re.sub(r"^INTEL\s+", "", s, flags=re.IGNORECASE).strip()
        m = re.match(r"([A-Z]\d{3,4}(?:-[A-Z0-9]+)?)", s, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return s.split()[0].upper() if s else s

    if cat == "ssd":
        s = re.sub(r"^(?:INTEL|INT)\s+", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"^SSD\s+", "", s, flags=re.IGNORECASE).strip()
        return s.upper()

    # CPU / optic: strip INTEL/XEON prefix
    s = re.sub(r"^(?:INTEL\s+)?(?:XEON\s+)?", "", s, flags=re.IGNORECASE)
    return s.strip()


def _build_ark_query(model: str, category: str) -> str:
    """Normalize a raw model string into an ARK-friendly search query.

    Handles NIC speed/port suffixes and SSD 'INT' prefixes so that Intel
    ARK search returns relevant product pages.
    """
    cat = category.lower()
    s = model.strip().upper()

    if cat == "nic":
        # Strip INTEL prefix
        s = re.sub(r"^INTEL\s+", "", s).strip()
        # Extract adapter family: X520-DA2, X540-T2, X710-BM2, I350-T4, etc.
        m = re.match(r"([A-Z]\d{3,4}(?:-[A-Z0-9]+)?)", s)
        if m:
            family = m.group(1)
            return f"Intel Ethernet {family}"
        return f"Intel Ethernet {s.split()[0]}"

    if cat == "ssd":
        # Strip INT/INTEL prefix
        s = re.sub(r"^(?:INTEL|INT)\s+", "", s).strip()
        # Strip form factor suffixes: U.2, M.2
        s = re.sub(r"\s+(?:U\.2|M\.2|2\.5|NVME|SATA|PCIE).*$", "", s).strip()
        return f"Intel SSD {s}"

    # For CPU/optic, fall through to _prepare_search_term
    return _prepare_search_term(s, cat)


def _prepare_search_term(model_key: str, category: str = "cpu") -> str:
    """Convert a normalized model key to a searchable term for Intel ARK."""
    cat = category.lower()
    s = model_key.strip()

    if cat == "nic":
        return _build_ark_query(s, cat)

    if cat == "ssd":
        return _build_ark_query(s, cat)

    if cat == "optic":
        return s

    # CPU: strip residual XEON/INTEL prefix
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
    release_date = _parse_launch_date(data.get("launch_date", ""))
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
        release_date=release_date,
        checked_at=datetime.now(),
        source_name="intel-ark",
        confidence=90,
        notes="; ".join(notes_parts),
        date_source="manufacturer_confirmed",
        eol_reason=EOLReason.MANUFACTURER_DECLARED,
        risk_category=(RiskCategory.SUPPORT if status == EOLStatus.EOL else RiskCategory.NONE),
    )
