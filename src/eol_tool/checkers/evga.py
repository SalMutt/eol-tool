"""EVGA EOL checker.

EVGA exited the GPU business in September 2022 and is winding down.
All GPUs are EOL; PSUs and peripherals remain active.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_GPU_RE = re.compile(
    r"GEFORCE|GTX\s*\d|RTX\s*\d|TITAN|GT\s*\d{3}",
    re.IGNORECASE,
)
_PSU_RE = re.compile(
    r"PSU|SUPERNOVA|[PG]\d\+?\s*\d+W|\d+\s*W\b|POWER\s*SUPPLY",
    re.IGNORECASE,
)
_PERIPHERAL_RE = re.compile(
    r"MOUSE|KEYBOARD|HEADSET|TORQ|Z\d{2}",
    re.IGNORECASE,
)


class EVGAChecker(BaseChecker):
    """EVGA EOL checker — GPUs discontinued, PSUs/peripherals active."""

    manufacturer_name = "EVGA"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        if _GPU_RE.search(normalized):
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="evga-product-line",
                confidence=90,
                notes="EVGA exited GPU market September 2022",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                risk_category=RiskCategory.PROCUREMENT,
                date_source="none",
            )

        if _PSU_RE.search(normalized):
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="evga-product-line",
                confidence=70,
                notes="EVGA power supply - still sold",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.INFORMATIONAL,
                date_source="none",
            )

        if _PERIPHERAL_RE.search(normalized):
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="evga-product-line",
                confidence=70,
                notes="EVGA peripheral - still sold",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.INFORMATIONAL,
                date_source="none",
            )

        # Default: EVGA is winding down, moderate confidence EOL
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="evga-product-line",
            confidence=60,
            notes="EVGA product - company winding down GPU business",
            eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
