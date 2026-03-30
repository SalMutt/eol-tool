"""Mushkin EOL checker.

Mushkin Chronos SSD line is discontinued.  No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory


class MushkinChecker(BaseChecker):
    """Mushkin EOL checker — Chronos line discontinued."""

    manufacturer_name = "Mushkin"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        if "CHRONOS" in normalized:
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="mushkin-static-lookup",
                confidence=70,
                notes="Mushkin Chronos SSD - discontinued",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                risk_category=RiskCategory.PROCUREMENT,
            )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="mushkin-static-lookup",
            confidence=50,
            notes="mushkin-model-not-classified",
        )
