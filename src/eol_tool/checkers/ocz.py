"""OCZ EOL checker.

OCZ was acquired by Toshiba in 2014 and the brand discontinued.
All models are EOL.  No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_PRODUCTS: dict[str, str] = {
    "AGILITY 3": "OCZ Agility 3 - brand discontinued (Toshiba acquisition)",
    "TRION 100": "OCZ Trion 100 - brand discontinued (Toshiba acquisition)",
}


class OCZChecker(BaseChecker):
    """OCZ EOL checker — all products EOL after Toshiba acquisition."""

    manufacturer_name = "OCZ"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for key, notes in _PRODUCTS.items():
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="ocz-static-lookup",
                    confidence=90,
                    notes=notes,
                    eol_reason=EOLReason.VENDOR_ACQUIRED,
                    risk_category=RiskCategory.PROCUREMENT,
                )

        # All OCZ products are EOL regardless of model
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="ocz-static-lookup",
            confidence=90,
            notes="OCZ brand discontinued - acquired by Toshiba 2014",
            eol_reason=EOLReason.VENDOR_ACQUIRED,
            risk_category=RiskCategory.PROCUREMENT,
        )
