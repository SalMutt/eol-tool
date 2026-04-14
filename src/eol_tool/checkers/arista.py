"""Arista EOL checker for switches and optics.

Static lookup, no HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Model substring → (status, risk, eol_reason, notes)
# Order matters: more specific patterns before broader ones.
_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, EOLReason, str]] = [
    # EOL switches
    ("7010", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.PRODUCT_DISCONTINUED,
     "Arista-7010-series-switch-discontinued"),
    ("7050QX-32", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.PRODUCT_DISCONTINUED,
     "Arista-7050QX-32-fixed-config-switch-discontinued"),
    ("7050S-64", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.PRODUCT_DISCONTINUED,
     "Arista-7050S-64-fixed-config-switch-discontinued"),
    # Active switches (specific variants before broad families)
    ("7050CX3", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-7050CX3-switch-current"),
    ("7060", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-7060-switch-current"),
    ("7800", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-7800-switch-current"),
    ("7300", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-7300-switch-current"),
    # Optics
    ("QSFP-100G-SR4", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-100G-SR4-optic-current"),
    ("QSFP-40G", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-40G-optic-current"),
    ("40G QSFP+", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-40G-optic-current"),
    ("SFP-10GLR-31", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-10G-LR-optic-current"),
    ("SFP-25GSR-85", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-25G-SR-optic-current"),
    # Generic optic form factors
    ("SFP+", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-SFP+-optic-current"),
    ("QSFP+", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Arista-QSFP+-optic-current"),
    # EOL switches
    ("7050S", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.PRODUCT_DISCONTINUED,
     "Arista-7050S-switch-discontinued"),
]


class AristaChecker(BaseChecker):
    """Arista EOL checker for switches and optics."""

    manufacturer_name = "Arista"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()
        result = self._match(model, normalized)
        if result:
            return result

        # Fallback: try original_item
        if model.original_item and model.original_item != model.model:
            item_cleaned = re.sub(
                r"^[A-Z /]+:(NEW|USED|REFURBISHED):",
                "",
                model.original_item.strip().upper(),
            )
            result = self._match(model, item_cleaned)
            if result:
                return result

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="arista-static-lookup",
            confidence=50,
            notes="arista-model-not-classified",
        )

    @staticmethod
    def _match(model: HardwareModel, text: str) -> EOLResult | None:
        for key, status, risk, reason, notes in _PRODUCTS:
            if key.upper() in text:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="arista-static-lookup",
                    confidence=80,
                    notes=notes,
                    eol_reason=reason,
                    risk_category=risk,
                )
        return None
