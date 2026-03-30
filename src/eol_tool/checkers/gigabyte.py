"""Gigabyte EOL checker for server boards and SSDs.

Only 3 models in the dataset.  No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("MC13-LE0", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Gigabyte MC13-LE0 - AMD EPYC embedded board, current"),
    ("MC12-LE0", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Gigabyte MC12-LE0 - AMD EPYC embedded board, current"),
]


class GigabyteChecker(BaseChecker):
    """Gigabyte EOL checker for server boards."""

    manufacturer_name = "Gigabyte"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for key, status, risk, notes in _PRODUCTS:
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="gigabyte-static-lookup",
                    confidence=65,
                    notes=notes,
                    eol_reason=EOLReason.NONE,
                    risk_category=risk,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="gigabyte-static-lookup",
            confidence=50,
            notes="gigabyte-model-not-classified",
        )
