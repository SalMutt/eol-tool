"""Dynatron EOL checker for server heatsinks.

Static lookup by model number, no HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# (model_number, status, risk, eol_reason, notes)
_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, EOLReason, str]] = [
    # AMD SP3/SP5 — current EPYC sockets
    ("A42", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A42-AMD-SP3/SP5-heatsink-current"),
    ("A43", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A43-AMD-SP3/SP5-heatsink-current"),
    ("A45", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A45-AMD-SP3/SP5-heatsink-current"),
    ("A46", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A46-AMD-SP3/SP5-heatsink-current"),
    ("A47", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A47-AMD-SP3/SP5-heatsink-current"),
    ("A54", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A54-AMD-SP3/SP5-heatsink-current"),
    # AMD AM4 — still available
    ("A18", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A18-AMD-AM4-heatsink-current"),
    ("A24", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A24-AMD-AM4-heatsink-current"),
    ("A37", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-A37-AMD-AM4-heatsink-current"),
    # Intel LGA4189
    ("B12", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, "Dynatron-B12-Intel-LGA4189-heatsink-current"),
    # Intel LGA4677 — current
    ("S2", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, "Dynatron-S2-Intel-LGA4677-heatsink-current"),
    # Intel LGA2011/2066 — legacy
    ("J13", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.TECHNOLOGY_GENERATION,
     "Dynatron-J13-Intel-LGA2011/2066-heatsink-legacy"),
    ("J2", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.TECHNOLOGY_GENERATION,
     "Dynatron-J2-Intel-LGA2011/2066-heatsink-legacy"),
    ("J7", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.TECHNOLOGY_GENERATION,
     "Dynatron-J7-Intel-LGA2011/2066-heatsink-legacy"),
    # Intel LGA1151/1200 — legacy
    ("K129", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.TECHNOLOGY_GENERATION,
     "Dynatron-K129-Intel-LGA1151/1200-heatsink-legacy"),
    ("K199", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.TECHNOLOGY_GENERATION,
     "Dynatron-K199-Intel-LGA1151/1200-heatsink-legacy"),
    # Intel LGA2011 — legacy
    ("Q8", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.TECHNOLOGY_GENERATION,
     "Dynatron-Q8-Intel-LGA2011-heatsink-legacy"),
]

_DYNATRON_RE = re.compile(r"^DYNATRON\s+", re.IGNORECASE)


class DynatronChecker(BaseChecker):
    """Dynatron EOL checker for server heatsinks."""

    manufacturer_name = "Dynatron"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = _DYNATRON_RE.sub("", model.model.strip().upper())

        for key, status, risk, reason, notes in _PRODUCTS:
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="dynatron-static-lookup",
                    confidence=75,
                    notes=notes,
                    eol_reason=reason,
                    risk_category=risk,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="dynatron-static-lookup",
            confidence=50,
            notes="dynatron-model-not-classified",
        )
