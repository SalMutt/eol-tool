"""Broadcom/LSI RAID checker using static lookup.

Broadcom acquired LSI Logic and Avago.  All models in the dataset are
MegaRAID or SAS HBA products.  Only 14 models — no HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Static lookup table for all known Broadcom/LSI models in the dataset.
# Keys are normalized model identifiers (uppercase, prefixes stripped).
_KNOWN_MODELS: dict[str, dict] = {
    # ── SAS2 RAID controllers (all EOL) ──────────────────────────────
    "9240-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9240-8i - SAS2 RAID, very old generation",
    },
    "9260-4I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9260-4i - SAS2 RAID",
    },
    "9260-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9260-8i - SAS2 RAID",
    },
    "9261-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9261-8i - SAS2 RAID",
    },
    "9271-4I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9271-4i - SAS2 RAID",
    },
    "9271-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9271-8i - SAS2 RAID",
    },
    "9220-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9220-8i - SAS2 RAID",
    },
    # ── SAS3 HBA / RAID controllers ─────────────────────────────────
    "9300-8I": {
        "status": EOLStatus.EOL,
        "notes": "SAS 9300-8i - SAS3 HBA, older generation",
    },
    "9305-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "SAS 9305-16i - SAS3 HBA, still current",
    },
    "9361-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9361-8i - SAS3 RAID, nearing EOL",
    },
    "9361-16I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9361-16i - SAS3 RAID, nearing EOL",
    },
    "9362-8I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID SAS 9362-8i - SAS3 RAID, current",
    },
    # ── SAS4 / NVMe tri-mode ────────────────────────────────────────
    "9500-8I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9500-8i - SAS4/NVMe tri-mode, current generation",
    },
    "9660-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9660-16i - latest generation tri-mode",
    },
}

# Intel RAID Expander that may come through as Broadcom — defer.
_INTEL_MODELS = {"RES2SV240"}

_PREFIX_RE = re.compile(r"^(?:MEGARAID\s+SAS\s+|LSI\s+)", re.IGNORECASE)


class BroadcomChecker(BaseChecker):
    """Broadcom/LSI EOL checker using static product lookup."""

    manufacturer_name = "Broadcom"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # Intel RAID Expander — not a Broadcom product
        if normalized in _INTEL_MODELS:
            return self._not_found(model, "intel-raid-expander-not-broadcom")

        entry = _KNOWN_MODELS.get(normalized)
        if entry:
            return self._make_result(model, entry["status"], entry["notes"])

        return self._not_found(model, "not-found-in-broadcom-lookup")

    @staticmethod
    def _normalize(model_str: str) -> str:
        """Normalize model string for lookup."""
        s = model_str.strip().upper()
        s = _PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _make_result(
        model: HardwareModel,
        status: EOLStatus,
        notes: str,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="broadcom-static-lookup",
            confidence=85,
            notes=notes,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SUPPORT,
        )

    @staticmethod
    def _not_found(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="broadcom-static-lookup",
            confidence=0,
            notes=reason,
        )
