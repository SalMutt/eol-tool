"""Adaptec EOL checker for RAID controllers.

Adaptec is now part of Microchip (formerly PMC-Sierra).
Older series (5-8) are EOL; SmartRAID/SmartHBA are current.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # SmartRAID — active (current Microchip line)
    {
        "pattern": re.compile(r"SMARTRAID|SMART\s*RAID|SR3[12]\d{2}", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "Adaptec SmartRAID - current Microchip product line",
        "risk": RiskCategory.SUPPORT,
    },
    # SmartHBA — active
    {
        "pattern": re.compile(r"SMARTHBA|SMART\s*HBA|SH2\d{3}", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "Adaptec SmartHBA - current Microchip product line",
        "risk": RiskCategory.SUPPORT,
    },
    # Series 8 — EOL (PMC-Sierra era)
    {
        "pattern": re.compile(r"\b8[018]\d{2}", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 75,
        "notes": "Adaptec Series 8 RAID controller - PMC-Sierra era, EOL",
        "risk": RiskCategory.SUPPORT,
    },
    # Series 7 — EOL
    {
        "pattern": re.compile(r"\b7[018]\d{2}|71605", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "Adaptec Series 7 RAID controller - end of life",
        "risk": RiskCategory.SUPPORT,
    },
    # Series 6 — EOL
    {
        "pattern": re.compile(r"\b6[048]\d{2}", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "Adaptec Series 6 RAID controller - end of life",
        "risk": RiskCategory.SUPPORT,
    },
    # Series 5 — EOL
    {
        "pattern": re.compile(r"\b5[048]\d{2}", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "Adaptec Series 5 RAID controller - end of life",
        "risk": RiskCategory.SUPPORT,
    },
]


class AdaptecChecker(BaseChecker):
    """Adaptec EOL checker for RAID controllers."""

    manufacturer_name = "Adaptec"
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
                    source_name="adaptec-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: most Adaptec controllers in datacenters are old
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="adaptec-product-line",
            confidence=60,
            notes="Adaptec controller - assumed EOL (most datacenter units are legacy)",
            eol_reason=EOLReason.TECHNOLOGY_GENERATION,
            risk_category=RiskCategory.SUPPORT,
            date_source="none",
        )
