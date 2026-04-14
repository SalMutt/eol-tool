"""A-Tech EOL checker for aftermarket memory.

Classifies by DDR generation from model or description.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    {
        "pattern": re.compile(r"DDR3|PC3-", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "A-Tech DDR3 memory - technology generation obsolete",
        "risk": RiskCategory.INFORMATIONAL,
    },
    {
        "pattern": re.compile(r"DDR5|PC5-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "A-Tech DDR5 memory - current generation",
        "risk": RiskCategory.INFORMATIONAL,
    },
    {
        "pattern": re.compile(r"DDR4|PC4-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "notes": "A-Tech DDR4 memory - still widely available",
        "risk": RiskCategory.INFORMATIONAL,
    },
]


class ATechChecker(BaseChecker):
    """A-Tech EOL checker for aftermarket memory."""

    manufacturer_name = "A-Tech"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for rule in _RULES:
            if rule["pattern"].search(normalized):
                return EOLResult(
                    model=model,
                    status=rule["status"],
                    checked_at=datetime.now(),
                    source_name="atech-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: aftermarket memory, low confidence
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="atech-product-line",
            confidence=40,
            notes="A-Tech memory product - assumed active",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
