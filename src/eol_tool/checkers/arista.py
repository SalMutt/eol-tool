"""Arista EOL checker for switches and optics.

Static lookup, no HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Model substring → (status, risk, eol_reason, notes)
_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, EOLReason, str]] = [
    ("7050QX-32", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.PRODUCT_DISCONTINUED,
     "Arista-7050QX-32-fixed-config-switch-discontinued"),
    ("7050S-64", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.PRODUCT_DISCONTINUED,
     "Arista-7050S-64-fixed-config-switch-discontinued"),
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
]


class AristaChecker(BaseChecker):
    """Arista EOL checker for switches and optics."""

    manufacturer_name = "Arista"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for key, status, risk, reason, notes in _PRODUCTS:
            if key.upper() in normalized:
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

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="arista-static-lookup",
            confidence=50,
            notes="arista-model-not-classified",
        )
