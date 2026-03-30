"""PNY EOL checker for GPUs and SSDs.

Covers Quadro/RTX GPUs and consumer SSDs.  No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("VCQRTX5000", EOLStatus.ACTIVE, RiskCategory.NONE,
     "PNY RTX 5000 - professional GPU, current"),
    ("VCQRTX4000", EOLStatus.ACTIVE, RiskCategory.NONE,
     "PNY RTX 4000 - professional GPU, still sold"),
    ("VCQP1000", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "PNY Quadro P1000 - older Pascal GPU, EOL"),
    ("VCQK1200", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "PNY Quadro K1200 - very old Maxwell GPU, EOL"),
    ("P2200", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "PNY Quadro P2200 - older Turing GPU, EOL"),
    ("CS900", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     "PNY CS900 - consumer SSD, still available"),
    ("CS1311", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "PNY CS1311 - consumer SSD, EOL"),
]


class PNYChecker(BaseChecker):
    """PNY EOL checker for GPUs and SSDs."""

    manufacturer_name = "PNY"
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
                    source_name="pny-static-lookup",
                    confidence=70,
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
            source_name="pny-static-lookup",
            confidence=50,
            notes="pny-model-not-classified",
        )
