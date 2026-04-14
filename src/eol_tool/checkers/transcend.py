"""Transcend EOL checker for SSDs and memory.

Classifies Transcend products by series name and memory generation.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_TRANSCEND_RE = re.compile(r"^TRANSCEND\s+", re.IGNORECASE)

# (pattern, status, confidence, notes)
_RULES: list[tuple[str, EOLStatus, int, str]] = [
    # EOL SSD series
    ("SSD370", EOLStatus.EOL, 70, "Transcend SSD370 - older SATA SSD, EOL"),
    ("MSA370", EOLStatus.EOL, 70, "Transcend MSA370 - older mSATA SSD, EOL"),
    # Active SSD series
    ("SSD230", EOLStatus.ACTIVE, 70, "Transcend SSD230S - current SATA SSD"),
    ("MTE220", EOLStatus.ACTIVE, 70, "Transcend MTE220S - current NVMe SSD"),
    # Specific part numbers (legacy)
    ("TS64GHSD452T-I", EOLStatus.ACTIVE, 65,
     "Transcend HSD452T-I - industrial temp half-slim, still sold"),
    ("TS64GMTS400S", EOLStatus.EOL, 65,
     "Transcend MTS400S - old M.2 SATA, EOL"),
    ("TS16GHSD", EOLStatus.EOL, 65,
     "Transcend 16GB half-slim SSD - very old, EOL"),
    ("TS32GHSD", EOLStatus.EOL, 65,
     "Transcend 32GB half-slim SSD - very old, EOL"),
    # Server memory series
    ("DSTMM", EOLStatus.EOL, 75, "Transcend DSTMM DDR3-1600 server memory - EOL technology"),
    # Memory generations
    ("DDR3", EOLStatus.EOL, 85, "Transcend DDR3 memory - EOL technology"),
    ("DDR5", EOLStatus.ACTIVE, 85, "Transcend DDR5 memory - current"),
    ("DDR4", EOLStatus.ACTIVE, 85, "Transcend DDR4 memory - current"),
]


class TranscendChecker(BaseChecker):
    """Transcend EOL checker for SSDs and memory."""

    manufacturer_name = "Transcend"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = _TRANSCEND_RE.sub("", model.model.strip()).upper()

        for pattern, status, confidence, notes in _RULES:
            if pattern.upper() in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="transcend-static-lookup",
                    confidence=confidence,
                    notes=notes,
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED
                    if status == EOLStatus.EOL
                    else EOLReason.NONE,
                    risk_category=RiskCategory.PROCUREMENT,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="transcend-static-lookup",
            confidence=50,
            notes="Transcend model not specifically classified",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
        )
