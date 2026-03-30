"""KIOXIA EOL checker for enterprise SSDs.

KIOXIA was spun off from Toshiba Memory in 2019.  All models in the
dataset are current enterprise NVMe SSDs.  No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_KIOXIA_PRODUCTS: list[tuple[str, str]] = [
    ("CD8", "KIOXIA CD8 - current enterprise NVMe"),
    ("CD6", "KIOXIA CD6-R - current enterprise NVMe read-optimized"),
    ("EXCERIA", "KIOXIA Exceria - current consumer NVMe SSD"),
]


class KIOXIAChecker(BaseChecker):
    """KIOXIA EOL checker for enterprise SSDs."""

    manufacturer_name = "KIOXIA"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for key, notes in _KIOXIA_PRODUCTS:
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=EOLStatus.ACTIVE,
                    checked_at=datetime.now(),
                    source_name="kioxia-product-rules",
                    confidence=75,
                    notes=notes,
                    eol_reason=EOLReason.NONE,
                    risk_category=RiskCategory.NONE,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="kioxia-product-rules",
            confidence=50,
            notes="kioxia-model-not-classified",
        )
