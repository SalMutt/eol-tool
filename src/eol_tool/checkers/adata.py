"""ADATA EOL checker for SSDs and memory.

Classifies by product line and DDR generation.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # === EOL product lines ===
    {
        "pattern": re.compile(r"SU800|SU900|SP900|SP920", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "ADATA SU800/SU900 SATA SSD - previous generation, EOL",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"SX8200|SX8100|SX6000", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "ADATA XPG SX8200/SX8100 NVMe - older generation, EOL",
        "risk": RiskCategory.PROCUREMENT,
    },
    # === Active product lines ===
    {
        "pattern": re.compile(r"SU6[35][05]|SU630|SU650|SU655", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "ADATA SU630/SU650/SU655 - current budget SATA SSD",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"GAMMIX\s*S[57]0|S70\b|S50\b", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 85,
        "notes": "ADATA XPG GAMMIX S50/S70 NVMe - current generation",
        "risk": RiskCategory.PROCUREMENT,
    },
    {
        "pattern": re.compile(r"DDR5|PC5-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 85,
        "notes": "ADATA DDR5 memory - current generation",
        "risk": RiskCategory.INFORMATIONAL,
    },
    {
        "pattern": re.compile(r"DDR4|PC4-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "ADATA DDR4 memory - still widely available",
        "risk": RiskCategory.INFORMATIONAL,
    },
]


class ADATAChecker(BaseChecker):
    """ADATA EOL checker for SSDs and memory."""

    manufacturer_name = "ADATA"
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
                    source_name="adata-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: ADATA products are mostly current
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="adata-product-line",
            confidence=50,
            notes="ADATA product - assumed active",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
