"""IBM EOL checker for servers, switches, and Power systems.

IBM sold its x86 server business to Lenovo in 2014.
Most IBM hardware in a datacenter is legacy.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # Power10 — active
    {
        "pattern": re.compile(r"POWER\s*10|POWER10|P10\b", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "IBM Power10 - current generation",
        "eol_reason": EOLReason.NONE,
        "risk": RiskCategory.SUPPORT,
    },
    # Power9 — active (still supported)
    {
        "pattern": re.compile(r"POWER\s*9|POWER9|P9\b", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 70,
        "notes": "IBM Power9 - still supported",
        "eol_reason": EOLReason.NONE,
        "risk": RiskCategory.SUPPORT,
    },
    # Power8 — EOL
    {
        "pattern": re.compile(r"POWER\s*[5-8]|POWER[5-8]|P[5-8]\b", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "IBM Power8 or earlier - end of life",
        "eol_reason": EOLReason.TECHNOLOGY_GENERATION,
        "risk": RiskCategory.SUPPORT,
    },
    # System x servers — sold to Lenovo
    {
        "pattern": re.compile(r"X3[0-9]{3}", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "IBM System x - sold to Lenovo in 2014, end of life",
        "eol_reason": EOLReason.VENDOR_ACQUIRED,
        "risk": RiskCategory.SUPPORT,
    },
    # BladeCenter — EOL
    {
        "pattern": re.compile(r"BLADECENTER|BLADE\s*CENTER", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "IBM BladeCenter - discontinued, end of life",
        "eol_reason": EOLReason.VENDOR_ACQUIRED,
        "risk": RiskCategory.SUPPORT,
    },
    # IBM switch part numbers (e.g. 4273-E48)
    {
        "pattern": re.compile(r"\d{4}-[A-Z]\d{2}", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 75,
        "notes": "IBM switch/appliance - legacy part number, end of life",
        "eol_reason": EOLReason.VENDOR_ACQUIRED,
        "risk": RiskCategory.SECURITY,
    },
]


class IBMChecker(BaseChecker):
    """IBM EOL checker for x86 servers, switches, and Power systems."""

    manufacturer_name = "IBM"
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
                    source_name="ibm-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=rule["eol_reason"],
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: most IBM datacenter hardware is legacy
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="ibm-product-line",
            confidence=60,
            notes="IBM product - assumed EOL (most IBM datacenter hardware is legacy)",
            eol_reason=EOLReason.VENDOR_ACQUIRED,
            risk_category=RiskCategory.SUPPORT,
            date_source="none",
        )
