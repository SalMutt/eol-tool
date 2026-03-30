"""Solidigm EOL checker for enterprise SSDs.

Solidigm was formed from Intel's NAND business in 2021.
Only 3 models in the dataset.  No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_PRODUCTS: dict[str, tuple[EOLStatus, RiskCategory, str]] = {
    "D5-P4320": (
        EOLStatus.EOL, RiskCategory.PROCUREMENT,
        "Solidigm D5-P4320 - older QLC NVMe, EOL",
    ),
    "D5-P5316": (
        EOLStatus.ACTIVE, RiskCategory.NONE,
        "Solidigm D5-P5316 - current QLC NVMe",
    ),
    "D5-P5430": (
        EOLStatus.ACTIVE, RiskCategory.NONE,
        "Solidigm D5-P5430 - current NVMe",
    ),
}


class SolidigmChecker(BaseChecker):
    """Solidigm EOL checker for enterprise SSDs."""

    manufacturer_name = "Solidigm"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for key, (status, risk, notes) in _PRODUCTS.items():
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="solidigm-static-lookup",
                    confidence=80,
                    notes=notes,
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED
                    if status == EOLStatus.EOL
                    else EOLReason.NONE,
                    risk_category=risk,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="solidigm-static-lookup",
            confidence=50,
            notes="solidigm-model-not-classified",
        )
