"""SanDisk EOL checker.

SanDisk was acquired by Western Digital in 2016.
Most SanDisk enterprise SSDs are discontinued in favor of WD-branded products.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # CloudSpeed enterprise SATA — discontinued
    {
        "pattern": re.compile(r"SDLF|SDLL|CLOUDSPEED", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "SanDisk CloudSpeed enterprise SATA SSD - discontinued",
        "eol_reason": EOLReason.VENDOR_ACQUIRED,
        "risk": RiskCategory.PROCUREMENT,
    },
    # Lightning enterprise SAS — discontinued
    {
        "pattern": re.compile(r"^LB|SDLB|LIGHTNING", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "SanDisk Lightning enterprise SAS SSD - discontinued",
        "eol_reason": EOLReason.VENDOR_ACQUIRED,
        "risk": RiskCategory.PROCUREMENT,
    },
    # X400, X600 — previous gen OEM
    {
        "pattern": re.compile(r"\bX[46]00\b", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "SanDisk X400/X600 OEM SSD - previous generation, EOL",
        "eol_reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
    },
    # Ultra II, Extreme Pro SATA consumer — EOL for datacenter
    {
        "pattern": re.compile(r"ULTRA\s*II|EXTREME\s*PRO", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 75,
        "notes": "SanDisk consumer SATA SSD - EOL for datacenter use",
        "eol_reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
    },
    # Half-Slim form factor — discontinued
    {
        "pattern": re.compile(r"HALF.?SLIM|SDSA5", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "SanDisk half-slim SSD - discontinued form factor",
        "eol_reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
    },
]


class SanDiskChecker(BaseChecker):
    """SanDisk EOL checker — most enterprise products discontinued (WD acquisition)."""

    manufacturer_name = "SanDisk"
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
                    source_name="sandisk-product-line",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=rule["eol_reason"],
                    risk_category=rule["risk"],
                    date_source="none",
                )

        # Default: most SanDisk-branded enterprise products are discontinued
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="sandisk-product-line",
            confidence=60,
            notes="SanDisk product - most enterprise lines discontinued in favor of WD-branded",
            eol_reason=EOLReason.VENDOR_ACQUIRED,
            risk_category=RiskCategory.PROCUREMENT,
            date_source="none",
        )
