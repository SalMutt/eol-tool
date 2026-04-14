"""ASUS EOL checker for server motherboards and systems.

Classifies by board chipset prefix (Z10/Z11/Z12/Z13, KRPA/KRPG)
and server system generation suffix (E8/E9/E10/E11).
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Ordered: check specific patterns before broad ones
_RULES: list[tuple[re.Pattern, EOLStatus, str]] = [
    # Server boards by chipset
    (re.compile(r"\bZ1[23]", re.IGNORECASE),
     EOLStatus.ACTIVE, "ASUS Z12/Z13 board - Ice Lake/Sapphire Rapids era, current"),
    (re.compile(r"\bZ11", re.IGNORECASE),
     EOLStatus.EOL, "ASUS Z11 board - Skylake-SP era, end of life"),
    (re.compile(r"\bZ10", re.IGNORECASE),
     EOLStatus.EOL, "ASUS Z10 board - Broadwell era, end of life"),
    # AMD server boards
    (re.compile(r"\bKRPG", re.IGNORECASE),
     EOLStatus.ACTIVE, "ASUS KRPG board - AMD EPYC 7003 Milan, current"),
    (re.compile(r"\bKRPA", re.IGNORECASE),
     EOLStatus.EOL, "ASUS KRPA board - AMD EPYC 7002 Rome, end of life"),
    # Workstation boards
    (re.compile(r"\bWRX[89]0", re.IGNORECASE),
     EOLStatus.ACTIVE, "ASUS Pro WS Threadripper Pro board, current"),
    # Server systems by generation suffix
    (re.compile(r"-E1[01]\b", re.IGNORECASE),
     EOLStatus.ACTIVE, "ASUS server system Gen10/11, current"),
    (re.compile(r"-E9\b", re.IGNORECASE),
     EOLStatus.EOL, "ASUS server system Gen9 - Skylake era, end of life"),
    (re.compile(r"-E[1-8]\b", re.IGNORECASE),
     EOLStatus.EOL, "ASUS server system Gen8 or earlier, end of life"),
]


class ASUSChecker(BaseChecker):
    """ASUS EOL checker for server boards and systems."""

    manufacturer_name = "ASUS"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for pattern, status, notes in _RULES:
            if pattern.search(normalized):
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="asus-generation",
                    confidence=65,
                    notes=notes,
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.SUPPORT,
                    date_source="none",
                )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="asus-generation",
            confidence=40,
            notes="asus-model-not-classified",
        )
