"""HPE EOL checker for ProLiant and other server products.

Classifies by ProLiant generation (Gen7 through Gen11).
Gen10 Plus and Gen11 are active; Gen10 and earlier are EOL.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Ordered list of (pattern, status, notes)
_GENERATION_RULES: list[tuple[re.Pattern, EOLStatus, str]] = [
    (re.compile(r"GEN\s*11\b", re.IGNORECASE),
     EOLStatus.ACTIVE, "ProLiant Gen11 - Sapphire Rapids era, current"),
    (re.compile(r"GEN\s*10\s*P(?:LUS)?\b|GEN10P", re.IGNORECASE),
     EOLStatus.ACTIVE, "ProLiant Gen10 Plus - Ice Lake era, current"),
    (re.compile(r"GEN\s*10\b", re.IGNORECASE),
     EOLStatus.EOL, "ProLiant Gen10 - Skylake era, end of life"),
    (re.compile(r"GEN\s*9\b", re.IGNORECASE),
     EOLStatus.EOL, "ProLiant Gen9 - Haswell/Broadwell era, end of life"),
    (re.compile(r"GEN\s*8\b", re.IGNORECASE),
     EOLStatus.EOL, "ProLiant Gen8 - Sandy Bridge/Ivy Bridge era, end of life"),
    (re.compile(r"G[1-7]\b", re.IGNORECASE),
     EOLStatus.EOL, "ProLiant Gen7 or earlier, end of life"),
]


class HPEChecker(BaseChecker):
    """HPE EOL checker for ProLiant servers."""

    manufacturer_name = "HPE"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for pattern, status, notes in _GENERATION_RULES:
            if pattern.search(normalized):
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="hpe-generation",
                    confidence=70,
                    notes=notes,
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.SUPPORT,
                    date_source="none",
                )

        # ProLiant without generation info
        if "PROLIANT" in normalized:
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="hpe-generation",
                confidence=40,
                notes="ProLiant without generation indicator, assumed EOL",
                eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                risk_category=RiskCategory.SUPPORT,
                date_source="none",
            )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="hpe-generation",
            confidence=30,
            notes="hpe-model-not-classified",
        )
