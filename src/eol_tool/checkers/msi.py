"""MSI EOL checker.

MSI's server presence is minimal. Most products are relatively recent.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLResult, EOLStatus, HardwareModel, RiskCategory


class MSIChecker(BaseChecker):
    """MSI EOL checker — minimal server presence, default active."""

    manufacturer_name = "MSI"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="msi-generation",
            confidence=50,
            notes="MSI server product, assumed active",
            risk_category=RiskCategory.INFORMATIONAL,
        )
