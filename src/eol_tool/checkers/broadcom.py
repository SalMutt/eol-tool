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
    # ── SAS3 RAID controllers ──────────────────────────────────────
    "9380-4I4E": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9380-4i4e - SAS3 RAID, EOL",
    },
    "9380-8E": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9380-8e - SAS3 RAID, EOL",
    },
    "9341-8I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9341-8i - SAS3 RAID, EOL",
    },
    "9341-4I": {
        "status": EOLStatus.EOL,
        "notes": "MegaRAID SAS 9341-4i - SAS3 RAID, EOL",
    },
    # ── SAS4 / NVMe tri-mode ────────────────────────────────────────
    "9400-8I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9400-8i - SAS3 tri-mode, current",
    },
    "9400-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9400-16i - SAS3 tri-mode, current",
    },
    "9460-8I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9460-8i - SAS3 tri-mode RAID, current",
    },
    "9460-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9460-16i - SAS3 tri-mode RAID, current",
    },
    "9500-8I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9500-8i - SAS4/NVMe tri-mode, current generation",
    },
    "9500-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9500-16i - SAS4/NVMe tri-mode, current generation",
    },
    "9560-8I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9560-8i - SAS4 RAID, current",
    },
    "9560-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9560-16i - SAS4 RAID, current",
    },
    "9600-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9600-16i - SAS4 HBA, latest generation",
    },
    "9660-16I": {
        "status": EOLStatus.ACTIVE,
        "notes": "MegaRAID 9660-16i - latest generation tri-mode",
    },
    # ── Broadcom NICs ───────────────────────────────────────────────
    "57416": {
        "status": EOLStatus.ACTIVE,
        "notes": "Broadcom 57416 - 10GBase-T dual port NIC, current",
    },
    "57412": {
        "status": EOLStatus.ACTIVE,
        "notes": "Broadcom 57412 - 10GbE SFP+ dual port NIC, current",
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

        result = self._lookup(model, normalized)
        if result:
            return result

        # Fallback: try original_item (e.g. "RAID CARDS:NEW:LSI 9260-8i")
        if model.original_item and model.original_item != model.model:
            item_cleaned = re.sub(
                r"^[A-Z /]+:(NEW|USED|REFURBISHED):",
                "",
                model.original_item.strip().upper(),
            )
            item_normalized = self._normalize(item_cleaned)
            result = self._lookup(model, item_normalized)
            if result:
                return result

        return self._not_found(model, "not-found-in-broadcom-lookup")

    @staticmethod
    def _lookup(
        model: HardwareModel, normalized: str,
    ) -> EOLResult | None:
        entry = _KNOWN_MODELS.get(normalized)
        if entry:
            return BroadcomChecker._make_result(
                model, entry["status"], entry["notes"],
            )
        # Try substring match (longest key first) for partial model strings
        for key in sorted(_KNOWN_MODELS, key=len, reverse=True):
            if key in normalized:
                return BroadcomChecker._make_result(
                    model, _KNOWN_MODELS[key]["status"],
                    _KNOWN_MODELS[key]["notes"],
                )
        return None

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
            eol_reason=EOLReason.VENDOR_ACQUIRED,
            risk_category=RiskCategory.SUPPORT,
            date_source="none",
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
