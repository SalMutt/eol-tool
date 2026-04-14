"""Corsair EOL checker for memory, SSDs, PSUs, and peripherals.

Classifies by DDR generation for memory and product line for SSDs.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # === EOL product lines ===
    {
        "pattern": re.compile(r"DDR3|PC3-", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "Corsair DDR3 memory - technology generation obsolete",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"CSSD-F|FORCE\s*(LE|LS|GT|GS|3)", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "Corsair Force series SATA SSD - discontinued",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"MP400|MP500|MP510", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "Corsair MP400/500/510 NVMe - older generation, discontinued",
        "risk": RiskCategory.PROCUREMENT,
    },
    # === Active product lines ===
    {
        "pattern": re.compile(r"DDR5|PC5-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "Corsair DDR5 memory - current generation",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"DDR4|PC4-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "Corsair DDR4 memory - still widely available",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"MP600|MP700", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 85,
        "notes": "Corsair MP600/MP700 NVMe - current generation",
        "risk": RiskCategory.PROCUREMENT,
    },
]


class CorsairChecker(BaseChecker):
    """Corsair EOL checker for memory, SSDs, PSUs, peripherals."""

    manufacturer_name = "Corsair"
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
                    source_name="corsair-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: Corsair products are mostly current
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="corsair-product-line",
            confidence=50,
            notes="Corsair product - assumed active",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
