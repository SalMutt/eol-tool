"""Dell EOL checker using static lookup for PowerEdge servers,
RAID controllers, NICs, drives, and optics.

The endoflife.date API no longer carries a dell-poweredge product
(the slug was removed upstream), so all classification is now static.
"""

import logging
import re
from datetime import date, datetime

import httpx

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

logger = logging.getLogger(__name__)

# Static lookup table for Dell models.
# Keys are normalized model identifiers; values carry status and notes.
_KNOWN_MODELS: dict[str, dict] = {
    # ── PowerEdge servers ───────────────────────────────────────────
    "POWEREDGE R730XD": {
        "status": EOLStatus.EOL,
        "notes": "PowerEdge R730xd - launched 2015, end of support 2023",
        "risk": RiskCategory.SUPPORT,
        "eol_date": date(2020, 8, 17),
        "eos_date": date(2023, 8, 17),
    },
    "POWEREDGE R630": {
        "status": EOLStatus.EOL,
        "notes": "PowerEdge R630 - launched 2015, end of support 2023",
        "risk": RiskCategory.SUPPORT,
        "eol_date": date(2020, 8, 17),
        "eos_date": date(2023, 8, 17),
    },
    "R630": {
        "status": EOLStatus.EOL,
        "notes": "PowerEdge R630 - launched 2015, end of support 2023",
        "risk": RiskCategory.SUPPORT,
        "eol_date": date(2020, 8, 17),
        "eos_date": date(2023, 8, 17),
    },
    "R430": {
        "status": EOLStatus.EOL,
        "notes": "PowerEdge R430 - launched 2015, end of support 2023",
        "risk": RiskCategory.SUPPORT,
        "eol_date": date(2020, 8, 17),
        "eos_date": date(2023, 8, 17),
    },
    "POWEREDGE R750": {
        "status": EOLStatus.ACTIVE,
        "notes": "PowerEdge R750 - launched 2021, current generation",
        "risk": RiskCategory.SUPPORT,
    },
    "R640": {
        "status": EOLStatus.EOL_ANNOUNCED,
        "notes": "PowerEdge R640 - launched 2017, nearing end of support",
        "risk": RiskCategory.SUPPORT,
        "eol_date": date(2023, 5, 31),
        "eos_date": date(2028, 5, 31),
    },
    "R650": {
        "status": EOLStatus.ACTIVE,
        "notes": "PowerEdge R650 - launched 2021, current generation",
        "risk": RiskCategory.SUPPORT,
    },
    # ── NICs ─────────────────────────────────────────────────────────
    "57416": {
        "status": EOLStatus.ACTIVE,
        "notes": "Broadcom 57416 10GBase-T dual port NIC",
        "risk": RiskCategory.PROCUREMENT,
    },
    "99GTM": {
        "status": EOLStatus.EOL,
        "notes": "Dell 99GTM - X540 quad port NDC, discontinued",
        "risk": RiskCategory.PROCUREMENT,
    },
    # ── Optics ───────────────────────────────────────────────────────
    "SFP-25GSR-85": {
        "status": EOLStatus.ACTIVE,
        "notes": "Dell SFP-25GSR-85 25G SR transceiver",
        "risk": RiskCategory.PROCUREMENT,
    },
    # ── PERC RAID controllers ────────────────────────────────────────
    "H330": {
        "status": EOLStatus.EOL,
        "notes": "PERC H330 - 12th gen controller, end of life",
        "risk": RiskCategory.PROCUREMENT,
        "eol_date": date(2020, 8, 17),
    },
    "H755": {
        "status": EOLStatus.ACTIVE,
        "notes": "PERC H755 - 15th gen controller, current",
        "risk": RiskCategory.PROCUREMENT,
    },
    "SAS 6/IR": {
        "status": EOLStatus.EOL,
        "notes": "SAS 6/iR - legacy 11th gen controller, end of life",
        "risk": RiskCategory.PROCUREMENT,
    },
    "H310": {
        "status": EOLStatus.EOL,
        "notes": "PERC H310 - 12th gen controller, end of life",
        "risk": RiskCategory.PROCUREMENT,
        "eol_date": date(2020, 8, 17),
    },
    "H700": {
        "status": EOLStatus.EOL,
        "notes": "PERC H700 - 11th gen controller, end of life",
        "risk": RiskCategory.PROCUREMENT,
        "eol_date": date(2018, 2, 8),
    },
    "H710": {
        "status": EOLStatus.EOL,
        "notes": "PERC H710 - 12th gen controller, end of life",
        "risk": RiskCategory.PROCUREMENT,
        "eol_date": date(2020, 8, 17),
    },
    "H730": {
        "status": EOLStatus.EOL,
        "notes": "PERC H730 - 13th gen controller, end of life",
        "risk": RiskCategory.PROCUREMENT,
        "eol_date": date(2020, 8, 17),
    },
    # ── Drives ───────────────────────────────────────────────────────
    "W345K": {
        "status": EOLStatus.EOL,
        "notes": "Dell W345K - legacy 73GB 15K SAS drive, end of life",
        "risk": RiskCategory.PROCUREMENT,
    },
    "KCT7J": {
        "status": EOLStatus.EOL_ANNOUNCED,
        "notes": "Dell KCT7J - 480GB SSD, nearing end of availability",
        "risk": RiskCategory.PROCUREMENT,
    },
    # ── Server boards ────────────────────────────────────────────────
    "2C2CP": {
        "status": EOLStatus.EOL,
        "notes": "Dell 2C2CP - R730 era motherboard, end of life",
        "risk": RiskCategory.PROCUREMENT,
    },
}

# Part numbers that identify Dell NICs but are actually Intel products.
# When the manufacturer is Dell but the NIC is Intel-branded, we defer
# to the Intel checker by returning NOT_FOUND.
_INTEL_NIC_MODELS = ["I350", "I210", "X520", "X540-T2", "X550", "X710"]


class DellChecker(BaseChecker):
    """Dell EOL checker: static lookup for all Dell products."""

    manufacturer_name = "Dell"
    rate_limit = 2
    priority = 35
    base_url = "https://www.dell.com"

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # Intel-branded NICs sold under Dell — defer to Intel checker
        if self._is_intel_nic(normalized):
            return self._not_found(model, "intel-nic-handled-by-intel-checker")

        # Static lookup: exact match first, then prefix/substring
        entry = self._find_known_model(normalized)
        if entry:
            eol_date = entry.get("eol_date")
            eos_date = entry.get("eos_date")
            return self._make_result(
                model,
                entry["status"],
                85,
                EOLReason.MANUFACTURER_DECLARED,
                entry["risk"],
                entry["notes"],
                date_source="community_database" if eol_date else "none",
                eol_date=eol_date,
                eos_date=eos_date,
            )

        # Dell M.2 SSDs — generic, can't determine EOL from description
        if self._is_generic_ssd(normalized):
            return self._make_result(
                model,
                EOLStatus.UNKNOWN,
                30,
                EOLReason.NONE,
                RiskCategory.PROCUREMENT,
                "generic-dell-ssd-no-part-number",
                date_source="none",
            )

        # Fallback: try Dell support site
        if self._client:
            result = await self._try_support_page(model, normalized)
            if result:
                return result

        return self._not_found(model, "not-found-in-dell-lookup")

    @staticmethod
    def _normalize(model_str: str) -> str:
        """Normalize model string for lookup."""
        s = model_str.strip().upper()
        # Strip capacity prefixes like "73GB " or "480GB " or "960GB "
        s = re.sub(r"^\d+GB\s+", "", s)
        # Strip "DELL " or "DELLEMC " prefix
        s = re.sub(r"^(?:DELL\s*EMC|DELL)\s+", "", s)
        # Strip capacity again (may appear after DELLEMC prefix)
        s = re.sub(r"^\d+GB\s+", "", s)
        # Strip config suffixes: W/..., DUAL ..., number BAY ...
        s = re.sub(r"\s+W/.*$", "", s)
        s = re.sub(r"\s+DUAL\s+\d.*$", "", s)
        s = re.sub(r"\s+\d+\s*BAY\b.*$", "", s)
        s = re.sub(r"\s+\d+GB\s+RAM.*$", "", s)
        s = re.sub(r"\s+128GB$", "", s)
        return s.strip()

    @staticmethod
    def _is_intel_nic(normalized: str) -> bool:
        """Check if this is an Intel-branded NIC sold by Dell."""
        return any(tag in normalized for tag in _INTEL_NIC_MODELS)

    @staticmethod
    def _is_generic_ssd(normalized: str) -> bool:
        """Check for generic Dell SSD descriptions without part numbers."""
        return bool(re.match(r"^M\.2$", normalized))

    @staticmethod
    def _find_known_model(normalized: str) -> dict | None:
        """Find matching model in static lookup table."""
        # Exact match
        if normalized in _KNOWN_MODELS:
            return _KNOWN_MODELS[normalized]
        # Try extracting known keys from the normalized string
        # Longest match first to prefer specific over generic
        for key in sorted(_KNOWN_MODELS, key=len, reverse=True):
            if key in normalized:
                return _KNOWN_MODELS[key]
        return None

    async def _try_support_page(self, model: HardwareModel, normalized: str) -> EOLResult | None:
        """Attempt to fetch Dell support page; falls back to None on failure."""
        slug = normalized.lower().replace(" ", "-")
        url = f"{self.base_url}/support/home/en-us/product-support/product/{slug}/overview"
        try:
            resp = await self._fetch(url)
            if resp.status_code == 200 and "Access Denied" not in resp.text:
                return self._make_result(
                    model,
                    EOLStatus.UNKNOWN,
                    80,
                    EOLReason.MANUFACTURER_DECLARED,
                    self._risk_for_category(model.category),
                    f"dell-support-page-found: {url}",
                    date_source="none",
                )
        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s after 10s", url)
        except httpx.HTTPStatusError as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    @staticmethod
    def _risk_for_category(category: str) -> RiskCategory:
        cat = category.lower()
        if cat in ("server", "chassis"):
            return RiskCategory.SUPPORT
        return RiskCategory.PROCUREMENT

    @staticmethod
    def _make_result(
        model: HardwareModel,
        status: EOLStatus,
        confidence: int,
        eol_reason: EOLReason,
        risk_category: RiskCategory,
        notes: str,
        *,
        date_source: str = "none",
        eol_date: date | None = None,
        eos_date: date | None = None,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="dell-static-lookup",
            confidence=confidence,
            notes=notes,
            eol_reason=eol_reason,
            risk_category=risk_category,
            date_source=date_source,
            eol_date=eol_date,
            eos_date=eos_date,
        )

    @staticmethod
    def _not_found(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="dell-static-lookup",
            confidence=0,
            notes=reason,
            date_source="none",
        )
