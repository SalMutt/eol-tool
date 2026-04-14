"""Mushkin EOL checker.

Mushkin is a smaller memory/SSD brand. Older product lines (Chronos,
Reactor, Pilot) are discontinued. No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_MUSHKIN_RE = re.compile(r"^MUSHKIN\s+", re.IGNORECASE)

# (pattern, status, confidence, notes)
# Order matters: Pilot-E must come before Pilot.
_RULES: list[tuple[str, EOLStatus, int, str]] = [
    ("CHRONOS", EOLStatus.EOL, 70, "Mushkin Chronos SSD - discontinued"),
    ("REACTOR", EOLStatus.EOL, 70, "Mushkin Reactor SSD - discontinued"),
    ("PILOT-E", EOLStatus.ACTIVE, 70, "Mushkin Pilot-E NVMe SSD - current"),
    ("PILOT", EOLStatus.EOL, 70, "Mushkin Pilot NVMe SSD - discontinued"),
    ("SOURCE", EOLStatus.ACTIVE, 70, "Mushkin Source SATA SSD - current"),
    ("DDR3", EOLStatus.EOL, 85, "Mushkin DDR3 memory - EOL technology"),
    ("DDR5", EOLStatus.ACTIVE, 85, "Mushkin DDR5 memory - current"),
    ("DDR4", EOLStatus.ACTIVE, 85, "Mushkin DDR4 memory - current"),
]


class MushkinChecker(BaseChecker):
    """Mushkin EOL checker — legacy brand, most products discontinued."""

    manufacturer_name = "Mushkin"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = _MUSHKIN_RE.sub("", model.model.strip()).upper()

        for pattern, status, confidence, notes in _RULES:
            if pattern in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="mushkin-static-lookup",
                    confidence=confidence,
                    notes=notes,
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED
                    if status == EOLStatus.EOL
                    else EOLReason.NONE,
                    risk_category=RiskCategory.PROCUREMENT,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="mushkin-static-lookup",
            confidence=40,
            notes="Mushkin product - legacy brand, likely discontinued",
            eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            risk_category=RiskCategory.PROCUREMENT,
        )
