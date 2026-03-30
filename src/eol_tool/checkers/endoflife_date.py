"""Fallback EOL checker using the endoflife.date public API."""

import json
import logging
import re
from datetime import date, datetime

import httpx

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

logger = logging.getLogger(__name__)

# Exact mapping from (manufacturer_lower, category_lower) to an endoflife.date
# product slug.  A value of ``None`` means no suitable product exists on the API
# for that combination — the checker returns NOT_FOUND immediately instead of
# accidentally matching an unrelated product (e.g. Intel NICs ≠ intel-processors).
#
# Verified slugs (return HTTP 200 as of 2026-03-27):
#   intel-processors, nvidia-gpu
#
# Slugs confirmed NOT to exist on endoflife.date:
#   dell-poweredge (removed upstream), cisco-asa (never existed),
#   no products for: amd, supermicro, mellanox, arista, broadcom
SLUG_MAP: dict[tuple[str, str], str | None] = {
    ("intel", "cpu"): "intel-processors",
    ("intel", "nic"): None,
    ("intel", "ssd"): None,
    ("intel", "optic"): None,
    ("dell", "server"): None,
    ("dell", "raid-controller"): None,
    ("dell", "ssd"): None,
    ("cisco", "firewall"): None,
    ("cisco", "switch"): None,
    ("cisco", "router"): None,
    ("nvidia", "gpu"): "nvidia-gpu",
    ("amd", "cpu"): None,
    ("juniper", "switch"): None,
    ("juniper", "firewall"): None,
    ("juniper", "router"): None,
    ("samsung", "ssd"): None,
}


class EndOfLifeDateChecker(BaseChecker):
    """Fallback checker using the endoflife.date public API.

    Runs for any manufacturer as a first-pass sweep. Vendor-specific
    checkers with higher confidence scores override these results.
    """

    manufacturer_name = "__fallback__"
    rate_limit = 10
    priority = 30
    base_url = "https://endoflife.date/api"

    def __init__(self) -> None:
        super().__init__()
        self._all_products: list[str] | None = None

    async def _get_all_products(self) -> list[str]:
        """Fetch and cache the list of all product slugs."""
        if self._all_products is None:
            resp = await self._fetch(f"{self.base_url}/all.json")
            self._all_products = resp.json()
        return self._all_products

    def _find_matching_slugs(
        self, manufacturer: str, category: str, products: list[str]
    ) -> list[str]:
        """Find product slugs matching a manufacturer/category pair."""
        key = (manufacturer.lower(), category.lower())
        if key not in SLUG_MAP:
            return []
        slug = SLUG_MAP[key]
        if slug is None or slug not in products:
            return []
        return [slug]

    # Words too generic to use as cycle-label matches in strategy 2.
    _LABEL_STOP_WORDS = frozenset({
        "XEON", "INTEL", "AMD", "NVIDIA", "CPU", "GPU", "NIC", "SSD",
        "GOLD", "SILVER", "BRONZE", "PLATINUM", "REFURBISHED",
        "INT", "NEW", "USED",
    })

    def _match_cycle(self, model_name: str, cycles: list[dict]) -> dict | None:
        """Try to find the best matching cycle for a model string."""
        model_upper = model_name.upper()

        # Strategy 1: Direct cycle name match (e.g., "R740" in model matches cycle "R740")
        for cycle in cycles:
            cycle_name = str(cycle.get("cycle", "")).upper()
            if cycle_name and cycle_name in model_upper:
                return cycle

        # Strategy 1b: Intel Xeon E-series family+version match.
        # "XEON E5-2683V4" → extract E5 + V4, find cycle whose releaseLabel
        # contains "E5V4" or at least "XEON" + "V4".
        xeon_fv = re.search(r"(E[357])\D*\d{3,4}\s*(V\d+)", model_upper)
        if xeon_fv:
            family_version = f"{xeon_fv.group(1)}{xeon_fv.group(2)}"  # e.g. "E5V4"
            version_tag = xeon_fv.group(2)  # e.g. "V4"
            # Prefer exact family+version in label
            for cycle in cycles:
                label = str(cycle.get("releaseLabel", "")).upper()
                if family_version in label:
                    return cycle
            # Fallback: version in a Xeon-related label
            for cycle in cycles:
                label = str(cycle.get("releaseLabel", "")).upper()
                if "XEON" in label and version_tag in label:
                    return cycle
            # E-series model with version but no cycle found — don't let
            # strategy 2 produce a false match via generic "XEON" token.
            return None

        # Strategy 2: Check releaseLabel for model substrings
        for cycle in cycles:
            label = str(cycle.get("releaseLabel", "")).upper()
            if label:
                model_parts = re.split(r"[\s\-_/]+", model_upper)
                for part in model_parts:
                    if len(part) >= 2 and part not in self._LABEL_STOP_WORDS and part in label:
                        return cycle

        # Strategy 3: Extract version number (e.g., V4 -> v4)
        version_match = re.search(r"[Vv](\d+)", model_name)
        if version_match:
            version_key = f"v{version_match.group(1)}"
            for cycle in cycles:
                cycle_name = str(cycle.get("cycle", "")).lower()
                if cycle_name == version_key:
                    return cycle

        return None

    def _determine_status(self, cycle: dict) -> tuple[EOLStatus, date | None]:
        """Determine EOL status from a cycle's eol field."""
        eol_val = cycle.get("eol")

        if eol_val is False:
            return EOLStatus.ACTIVE, None

        if isinstance(eol_val, str):
            try:
                eol_date = date.fromisoformat(eol_val)
            except ValueError:
                return EOLStatus.UNKNOWN, None

            if eol_date <= date.today():
                return EOLStatus.EOL, eol_date
            else:
                return EOLStatus.EOL_ANNOUNCED, eol_date

        if eol_val is True:
            return EOLStatus.EOL, None

        return EOLStatus.UNKNOWN, None

    @staticmethod
    def _risk_for_category(category: str) -> RiskCategory:
        """Determine risk category based on the model's hardware category."""
        cat = category.lower()
        if cat in ("switch", "firewall", "network-device"):
            return RiskCategory.SECURITY
        if cat in ("cpu", "server-board", "server"):
            return RiskCategory.SUPPORT
        if cat in ("memory", "ssd", "hdd", "drive"):
            return RiskCategory.PROCUREMENT
        return RiskCategory.INFORMATIONAL

    def _match_model_to_result(
        self,
        model: HardwareModel,
        slugs: list[str],
        slug_cycles: dict[str, list[dict]],
    ) -> EOLResult:
        """Match a model against pre-fetched slug cycle data (no HTTP)."""
        risk = self._risk_for_category(model.category)

        if not slugs:
            return EOLResult(
                model=model,
                status=EOLStatus.NOT_FOUND,
                checked_at=datetime.now(),
                source_name="endoflife.date",
                confidence=0,
                notes="No matching product found on endoflife.date",
                eol_reason=EOLReason.COMMUNITY_DATA,
                risk_category=risk,
            )

        best_result: EOLResult | None = None

        for slug in slugs:
            cycles = slug_cycles.get(slug)
            if cycles is None:
                continue

            matched_cycle = self._match_cycle(model.model, cycles)

            if matched_cycle:
                status, eol_date = self._determine_status(matched_cycle)
                support_val = matched_cycle.get("support")
                eos_date = None
                if isinstance(support_val, str):
                    try:
                        eos_date = date.fromisoformat(support_val)
                    except ValueError:
                        pass

                best_result = EOLResult(
                    model=model,
                    status=status,
                    eol_date=eol_date,
                    eos_date=eos_date,
                    source_url=f"https://endoflife.date/{slug}",
                    source_name="endoflife.date",
                    checked_at=datetime.now(),
                    confidence=70,
                    notes=f"Matched {slug} cycle {matched_cycle.get('cycle', '')}",
                    eol_reason=EOLReason.COMMUNITY_DATA,
                    risk_category=risk,
                    date_source=("community_database" if eol_date or eos_date else "none"),
                )
                break  # 70 is the max confidence, no need to continue
            else:
                if best_result is None or best_result.confidence < 40:
                    best_result = EOLResult(
                        model=model,
                        status=EOLStatus.UNKNOWN,
                        source_url=f"https://endoflife.date/{slug}",
                        source_name="endoflife.date",
                        checked_at=datetime.now(),
                        confidence=40,
                        notes=f"Product {slug} found but no specific cycle match",
                        eol_reason=EOLReason.COMMUNITY_DATA,
                        risk_category=risk,
                        date_source="none",
                    )

        if best_result:
            return best_result

        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="endoflife.date",
            confidence=0,
            notes="No matching product found on endoflife.date",
            eol_reason=EOLReason.COMMUNITY_DATA,
            risk_category=risk,
        )

    source_name = "endoflife.date"

    @classmethod
    async def refresh_cache(cls, cache) -> int:
        """Re-fetch the product list from endoflife.date and store in cache.

        Returns the number of products cached.
        """
        url = f"{cls.base_url}/all.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                logger.info("Fetching %s...", url)
                resp = await client.get(url)
                resp.raise_for_status()
                logger.info("Fetched %s (%s)", url, resp.status_code)
                products = resp.json()
            except httpx.TimeoutException:
                logger.warning("Timeout fetching %s after 10s", url)
                return 0
            except httpx.HTTPStatusError as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                return 0
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                return 0
        await cache.set_source(
            cls.source_name, json.dumps(products), len(products),
        )
        return len(products)

    async def check(self, model: HardwareModel) -> EOLResult:
        """Check EOL status for a single model (fetches slug data on demand)."""
        products = await self._get_all_products()
        slugs = self._find_matching_slugs(model.manufacturer, model.category, products)

        slug_cycles: dict[str, list[dict]] = {}
        for slug in slugs:
            try:
                resp = await self._fetch(f"{self.base_url}/{slug}.json")
                slug_cycles[slug] = resp.json()
            except Exception:
                pass

        return self._match_model_to_result(model, slugs, slug_cycles)

    async def check_batch(self, models: list[HardwareModel]) -> list[EOLResult]:
        """Bulk check: fetch product list and slug cycles once, match in-memory.

        Makes exactly 1 request for the product list plus 1 request per unique
        slug needed across all models. A run of 1028 models typically needs
        only 30-40 HTTP requests total.
        """
        products = await self._get_all_products()

        # Collect slugs needed per model and the unique set across all models
        per_model_slugs: list[list[str]] = []
        unique_slugs: set[str] = set()
        for model in models:
            slugs = self._find_matching_slugs(model.manufacturer, model.category, products)
            per_model_slugs.append(slugs)
            unique_slugs.update(slugs)

        # Fetch each unique slug's cycle data exactly once
        slug_cycles: dict[str, list[dict]] = {}
        for slug in sorted(unique_slugs):
            try:
                resp = await self._fetch(f"{self.base_url}/{slug}.json")
                slug_cycles[slug] = resp.json()
            except Exception:
                logger.warning("Failed to fetch cycles for slug %s", slug)

        # Match all models against the in-memory data with zero additional HTTP
        results: list[EOLResult] = []
        for model, slugs in zip(models, per_model_slugs):
            try:
                results.append(self._match_model_to_result(model, slugs, slug_cycles))
            except Exception as exc:
                logger.warning("Match failed for %s %s: %s", model.manufacturer, model.model, exc)
                results.append(
                    EOLResult(
                        model=model,
                        status=EOLStatus.UNKNOWN,
                        checked_at=datetime.now(),
                        source_name="endoflife.date",
                        notes=f"match-error: {exc}",
                    )
                )
        return results
