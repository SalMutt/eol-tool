"""Transcend EOL checker for industrial/embedded SSDs.

Small-capacity industrial SSDs — most are EOL half-slim form factor.
No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Model substring → (status, risk, notes)
_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("TS64GHSD452T-I", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Transcend HSD452T-I - industrial temp half-slim, still sold"),
    ("TS64GMTS400S", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Transcend MTS400S - old M.2 SATA, EOL"),
    ("TS16GHSD", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Transcend 16GB half-slim SSD - very old, EOL"),
    ("TS32GHSD", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Transcend 32GB half-slim SSD - very old, EOL"),
]


class TranscendChecker(BaseChecker):
    """Transcend EOL checker for industrial/embedded SSDs."""

    manufacturer_name = "Transcend"
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
                    source_name="transcend-static-lookup",
                    confidence=65,
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
            source_name="transcend-static-lookup",
            confidence=50,
            notes="transcend-model-not-classified",
        )
