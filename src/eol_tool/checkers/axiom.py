"""Axiom EOL checker for third-party compatible memory and optics.

Axiom mirrors OEM specs. Classify by DDR generation and optic speed.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # DDR3 — EOL
    {
        "pattern": re.compile(r"DDR3|PC3-", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "Axiom DDR3 compatible module - technology generation obsolete",
        "risk": RiskCategory.INFORMATIONAL,
    },
    # DDR4 — active
    {
        "pattern": re.compile(r"DDR4|PC4-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "notes": "Axiom DDR4 compatible module - still available",
        "risk": RiskCategory.INFORMATIONAL,
    },
    # DDR5 — active
    {
        "pattern": re.compile(r"DDR5|PC5-", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "Axiom DDR5 compatible module - current generation",
        "risk": RiskCategory.INFORMATIONAL,
    },
    # 1G optics — EOL
    {
        "pattern": re.compile(
            r"\b1G[\s-]*(?:BASE|SR|LR|SX|LX|SFP)|SFP-1G|\b1000BASE",
            re.IGNORECASE,
        ),
        "status": EOLStatus.EOL,
        "confidence": 75,
        "notes": "Axiom 1G optic - legacy speed, EOL",
        "risk": RiskCategory.INFORMATIONAL,
    },
    # 10G+ optics — active
    {
        "pattern": re.compile(
            r"\b(?:10G|25G|40G|100G|QSFP|SFP\+|SFP28)",
            re.IGNORECASE,
        ),
        "status": EOLStatus.ACTIVE,
        "confidence": 70,
        "notes": "Axiom 10G+ optic - current speed tier",
        "risk": RiskCategory.INFORMATIONAL,
    },
]


class AxiomChecker(BaseChecker):
    """Axiom EOL checker for compatible memory and optics."""

    manufacturer_name = "Axiom"
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
                    source_name="axiom-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: third-party compatibility products, low confidence
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="axiom-product-line",
            confidence=40,
            notes="Axiom product - third-party compatible, assumed active",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
