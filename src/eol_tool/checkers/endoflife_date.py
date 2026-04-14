"""Fallback EOL checker using the endoflife.date public API."""

import json
import logging
import re
from datetime import date, datetime
from typing import ClassVar

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
    # ── Verified slugs (return HTTP 200) ────────────────────────────────
    ("intel", "cpu"): "intel-processors",
    ("nvidia", "gpu"): "nvidia-gpu",
    # ── No matching slug on endoflife.date ──────────────────────────────
    ("intel", "nic"): None,  # no intel-nic product
    ("intel", "ssd"): None,  # no intel-ssd product (Solidigm transition)
    ("intel", "optic"): None,  # no intel optics product
    ("dell", "server"): None,  # dell-poweredge removed upstream
    ("dell", "raid-controller"): None,  # no dell PERC product
    ("dell", "ssd"): None,  # no dell storage product
    ("cisco", "firewall"): None,  # cisco-asa never existed
    ("cisco", "switch"): None,  # no cisco-switch product
    ("cisco", "router"): None,  # no cisco-router product
    ("amd", "cpu"): None,  # no amd-processors or amd-epyc product
    ("juniper", "switch"): None,  # no juniper product
    ("juniper", "firewall"): None,
    ("juniper", "router"): None,
    ("samsung", "ssd"): None,  # samsung-mobile is phones, not SSDs
    ("seagate", "hdd"): None,  # no seagate or hard-drive product
    ("wd", "hdd"): None,  # no western-digital product
    ("micron", "ssd"): None,  # no micron or crucial product
    ("kingston", "ssd"): None,  # no kingston product
    ("kingston", "memory"): None,  # no kingston or ddr product
    ("sk hynix", "memory"): None,  # no sk-hynix or ddr product
    ("toshiba", "hdd"): None,  # no toshiba product
    ("broadcom", "raid-controller"): None,  # no megaraid or broadcom product
    ("supermicro", "server-board"): None,  # no supermicro product
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
    _all_products: ClassVar[list[str] | None] = None

    async def _get_all_products(self) -> list[str]:
        """Fetch and cache the list of all product slugs (class-level cache)."""
        if EndOfLifeDateChecker._all_products is None:
            resp = await self._fetch(f"{self.base_url}/all.json")
            EndOfLifeDateChecker._all_products = resp.json()
        return EndOfLifeDateChecker._all_products

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

        # Strategy 1c: Xeon Scalable number-series matching.
        # "XEON SILVER 4110" → 1st gen (41xx) → skylake-xeon
        # "XEON GOLD 6248" → 2nd gen (62xx) → cascade-lake-xeon
        xeon_scalable = re.search(
            r"(?:SILVER|GOLD|PLATINUM|BRONZE)\s*(\d{4,5})", model_upper,
        )
        if xeon_scalable:
            model_num = xeon_scalable.group(1)
            prefix = model_num[:2]
            _SCALABLE_GEN_MAP = {
                "31": "skylake-xeon", "41": "skylake-xeon",
                "51": "skylake-xeon", "61": "skylake-xeon",
                "81": "skylake-xeon",
                "32": "cascade-lake-xeon", "42": "cascade-lake-xeon",
                "52": "cascade-lake-xeon", "62": "cascade-lake-xeon",
                "82": "cascade-lake-xeon",
                "43": "ice-lake-xeon", "53": "ice-lake-xeon",
                "63": "ice-lake-xeon", "83": "ice-lake-xeon",
                "44": "sapphire-rapids-xeon", "45": "sapphire-rapids-xeon",
                "54": "sapphire-rapids-xeon", "64": "sapphire-rapids-xeon",
                "84": "sapphire-rapids-xeon",
            }
            target_cycle = _SCALABLE_GEN_MAP.get(prefix)
            if target_cycle:
                for cycle in cycles:
                    if str(cycle.get("cycle", "")).lower() == target_cycle:
                        return cycle
            return None

        # Strategy 1d: NVIDIA VCQ part-number extraction.
        # VCQP1000-PB → P1000 (Pascal), VCQRTX4000-PB → RTX4000 (Turing)
        vcq_match = re.search(r"VCQ(RTX\s*A?\d+|GP\d+|[A-Z]\d+)", model_upper)
        if vcq_match:
            gpu_id = vcq_match.group(1)
            # Direct label match with extracted GPU identifier
            for cycle in cycles:
                label = str(cycle.get("releaseLabel", "")).upper()
                if gpu_id in label:
                    return cycle
            # Map GPU prefix to architecture cycle name
            if gpu_id.startswith("RTXA") or gpu_id.startswith("RTX A"):
                target_arch = "ampere"
            elif gpu_id.startswith("RTX"):
                target_arch = "turing"
            elif gpu_id.startswith("GP") or gpu_id.startswith("P"):
                target_arch = "pascal"
            elif gpu_id.startswith("K"):
                target_arch = "maxwell"
            elif gpu_id.startswith("T"):
                target_arch = "turing"
            elif gpu_id.startswith("A"):
                target_arch = "ampere"
            elif gpu_id.startswith("M"):
                target_arch = "maxwell"
            else:
                target_arch = None
            if target_arch:
                for cycle in cycles:
                    if str(cycle.get("cycle", "")).lower() == target_arch:
                        return cycle
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

                release_date = None
                release_val = matched_cycle.get("releaseDate")
                if isinstance(release_val, str):
                    try:
                        release_date = date.fromisoformat(release_val)
                    except ValueError:
                        pass

                best_result = EOLResult(
                    model=model,
                    status=status,
                    eol_date=eol_date,
                    eos_date=eos_date,
                    release_date=release_date,
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


async def supplement_missing_dates(results: list[EOLResult]) -> list[EOLResult]:
    """Add dates from endoflife.date to EOL/EOL_ANNOUNCED results that lack them.

    Scans *results* for entries whose status is EOL or EOL_ANNOUNCED but whose
    ``eol_date`` is ``None``.  For each, attempts to match against
    endoflife.date cycles.  If a match with a concrete date is found the
    result's ``eol_date`` (and optionally ``eos_date``) are filled in and
    ``date_source`` is set to ``"community_database"``.  Status, source_name,
    and other fields are **not** changed.
    """
    needs_date = [
        r for r in results
        if r.status in (EOLStatus.EOL, EOLStatus.EOL_ANNOUNCED)
        and r.eol_date is None
    ]
    if not needs_date:
        return results

    try:
        checker = EndOfLifeDateChecker()
        async with checker:
            products = await checker._get_all_products()

            slug_set: set[str] = set()
            for r in needs_date:
                slugs = checker._find_matching_slugs(
                    r.model.manufacturer, r.model.category, products,
                )
                slug_set.update(slugs)

            if not slug_set:
                return results

            slug_cycles: dict[str, list[dict]] = {}
            for slug in sorted(slug_set):
                try:
                    resp = await checker._fetch(f"{checker.base_url}/{slug}.json")
                    slug_cycles[slug] = resp.json()
                except Exception:
                    logger.warning("supplement: failed to fetch cycles for %s", slug)

            for r in needs_date:
                slugs = checker._find_matching_slugs(
                    r.model.manufacturer, r.model.category, products,
                )
                for slug in slugs:
                    cycles = slug_cycles.get(slug)
                    if not cycles:
                        continue
                    matched = checker._match_cycle(r.model.model, cycles)
                    if not matched:
                        continue
                    _, eol_date = checker._determine_status(matched)
                    if eol_date is None:
                        continue
                    r.eol_date = eol_date
                    r.date_source = "community_database"
                    support_val = matched.get("support")
                    if isinstance(support_val, str):
                        try:
                            r.eos_date = date.fromisoformat(support_val)
                        except ValueError:
                            pass
                    release_val = matched.get("releaseDate")
                    if r.release_date is None and isinstance(release_val, str):
                        try:
                            r.release_date = date.fromisoformat(release_val)
                        except ValueError:
                            pass
                    supplement_note = "eol-date-supplemented-from-endoflife.date"
                    if r.notes:
                        r.notes = f"{r.notes}; {supplement_note}"
                    else:
                        r.notes = supplement_note
                    break
    except Exception:
        logger.warning("supplement_missing_dates failed", exc_info=True)

    return results
