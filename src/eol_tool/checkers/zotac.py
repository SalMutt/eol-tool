"""Zotac EOL checker for GPUs and mini PCs.

Classifies GPUs by NVIDIA generation from model name or part number.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # === EOL GPU generations ===
    {
        "pattern": re.compile(
            r"GTX\s*10[5-8]0|ZT-P10[5-8]",
            re.IGNORECASE,
        ),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "Zotac GeForce GTX 10-series (Pascal) - end of life",
        "risk": RiskCategory.INFORMATIONAL,
    },
    {
        "pattern": re.compile(
            r"RTX\s*20[6-8]0|ZT-T20[6-8]|ZT-P20[6-8]",
            re.IGNORECASE,
        ),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "Zotac GeForce RTX 20-series (Turing) - end of life",
        "risk": RiskCategory.INFORMATIONAL,
    },
    {
        "pattern": re.compile(
            r"GTX\s*9[5-8]0|GTX\s*7[5-9]0",
            re.IGNORECASE,
        ),
        "status": EOLStatus.EOL,
        "confidence": 90,
        "notes": "Zotac GeForce legacy (Maxwell/Kepler) - end of life",
        "risk": RiskCategory.INFORMATIONAL,
    },
    # === Active GPU generations ===
    {
        "pattern": re.compile(
            r"RTX\s*30[5-9]0|ZT-A30[5-9]",
            re.IGNORECASE,
        ),
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "notes": "Zotac GeForce RTX 30-series (Ampere) - active",
        "risk": RiskCategory.INFORMATIONAL,
    },
    {
        "pattern": re.compile(
            r"RTX\s*40[5-9]0|ZT-D40[5-9]",
            re.IGNORECASE,
        ),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "Zotac GeForce RTX 40-series (Ada Lovelace) - active",
        "risk": RiskCategory.INFORMATIONAL,
    },
    # ZBOX mini PCs — classify broadly as active
    {
        "pattern": re.compile(r"ZBOX", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 50,
        "notes": "Zotac ZBOX mini PC",
        "risk": RiskCategory.INFORMATIONAL,
    },
]


class ZotacChecker(BaseChecker):
    """Zotac EOL checker for GPUs and mini PCs."""

    manufacturer_name = "Zotac"
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
                    source_name="zotac-gpu-generation",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: active with low confidence
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="zotac-gpu-generation",
            confidence=40,
            notes="Zotac product - not classified by generation",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
