"""Intel EOL checker using static lookup for NICs, SSDs, and RAID products.

Replaces the old ARK scraper that hung on live runs.  CPUs are handled by
tech_generation.py, so this checker returns NOT_FOUND for CPU models.
"""

import re
from datetime import date, datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── NIC lookup (prefix-matched against normalized model string) ──────
_NIC_MODELS: dict[str, dict] = {
    "X520-DA2": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel Ethernet X520 - 10GbE SFP+ dual port, discontinued",
        "eol_date": date(2021, 7, 1),
    },
    "X540-T2": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel Ethernet X540 - 10GBASE-T dual port, discontinued",
        "eol_date": date(2021, 7, 1),
    },
    "I350-T4": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.INFORMATIONAL,
        "notes": "Intel Ethernet I350 - 1GbE quad port, still widely available",
    },
    "X550-T2": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X550 - 10GBASE-T dual port, current",
    },
    "X710-BM2": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X710 - 10GbE SFP+ dual port, current",
    },
    "X710-T4L": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X710 - 10GBASE-T quad port, current",
    },
    "X722-DA4": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X722 - 10GbE SFP+ quad port, current",
    },
}

# ── SSD lookup (matched only when category is ssd) ──────────────────
_SSD_MODELS: dict[str, dict] = {
    "540": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 540s - consumer SATA, discontinued",
    },
    "520": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 520 - consumer SATA, discontinued",
    },
    "660P": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 660p - QLC NVMe, discontinued",
    },
    "760P": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 760p - consumer NVMe, discontinued",
    },
    "DC P4511": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD DC P4511 - datacenter NVMe M.2, Solidigm transition",
    },
}

# ── RAID lookup ──────────────────────────────────────────────────────
_RAID_MODELS: dict[str, dict] = {
    "RES2SV240": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel RAID Expander RES2SV240 - very old SAS expander",
    },
}

_INTEL_PREFIX_RE = re.compile(r"^INTEL\s+", re.IGNORECASE)


class IntelChecker(BaseChecker):
    """Intel EOL checker using static product lookup."""

    manufacturer_name = "Intel"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        # CPUs handled by tech_generation checker
        if model.category.lower() == "cpu":
            return self._not_found(model, "cpu-handled-by-tech-generation")

        normalized = self._normalize(model.model)
        is_ssd = model.category.lower() == "ssd"

        # Try RAID lookup first (exact match)
        entry = self._match_raid(normalized)
        if entry:
            return self._make_result(model, entry)

        # Try NIC lookup (prefix match)
        entry = self._match_nic(normalized)
        if entry:
            return self._make_result(model, entry)

        # Try SSD lookup (only for SSD category to avoid 520/540 collisions)
        if is_ssd:
            entry = self._match_ssd(normalized)
            if entry:
                return self._make_result(model, entry)

        return self._not_found(model, "not-found-in-intel-lookup")

    @staticmethod
    def _normalize(model_str: str) -> str:
        """Normalize model string for lookup."""
        s = model_str.strip().upper()
        s = _INTEL_PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _match_nic(normalized: str) -> dict | None:
        """Match NIC models by checking if normalized string contains the key."""
        for key in sorted(_NIC_MODELS, key=len, reverse=True):
            if key in normalized:
                return _NIC_MODELS[key]
        return None

    @staticmethod
    def _match_ssd(normalized: str) -> dict | None:
        """Match SSD models — careful with short keys like 520/540."""
        for key in sorted(_SSD_MODELS, key=len, reverse=True):
            if key in normalized:
                return _SSD_MODELS[key]
        return None

    @staticmethod
    def _match_raid(normalized: str) -> dict | None:
        """Match RAID models by exact key match."""
        for key in _RAID_MODELS:
            if key in normalized:
                return _RAID_MODELS[key]
        return None

    @staticmethod
    def _make_result(model: HardwareModel, entry: dict) -> EOLResult:
        eol_date = entry.get("eol_date")
        return EOLResult(
            model=model,
            status=entry["status"],
            checked_at=datetime.now(),
            source_name="intel-static-lookup",
            confidence=80,
            notes=entry["notes"],
            eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            risk_category=entry["risk"],
            eol_date=eol_date,
            date_source="community_database" if eol_date else "none",
        )

    @staticmethod
    def _not_found(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="intel-static-lookup",
            confidence=0,
            notes=reason,
        )
