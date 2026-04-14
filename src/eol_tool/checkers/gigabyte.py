"""Gigabyte EOL checker for server boards and SSDs.

Only a few models in the dataset.  No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("MC13-LE0", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Gigabyte MC13-LE0 - AMD EPYC embedded board, current"),
    ("MC12-LE0", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Gigabyte MC12-LE0 - AMD EPYC embedded board, current"),
]


class GigabyteChecker(BaseChecker):
    """Gigabyte EOL checker for server boards."""

    manufacturer_name = "Gigabyte"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()
        # Strip capacity prefix like "240GB "
        normalized = re.sub(r"^\d+(?:\.\d+)?(?:TB|GB)\s+", "", normalized)
        # Strip "GIGABYTE " prefix
        normalized = re.sub(r"^GIGABYTE\s+", "", normalized)

        for key, status, risk, notes in _PRODUCTS:
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="gigabyte-static-lookup",
                    confidence=65,
                    notes=notes,
                    eol_reason=EOLReason.NONE,
                    risk_category=risk,
                )

        # Generic Gigabyte SSD (capacity-only description)
        cat = model.category.lower()
        if cat in ("ssd", "drive") or not normalized:
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="gigabyte-static-lookup",
                confidence=30,
                notes="generic-gigabyte-ssd",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.INFORMATIONAL,
            )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="gigabyte-static-lookup",
            confidence=50,
            notes="gigabyte-model-not-classified",
        )
