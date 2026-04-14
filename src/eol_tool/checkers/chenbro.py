"""Chenbro EOL checker for server chassis.

Chenbro makes server chassis — passive hardware with no firmware lifecycle.
All products classified as active/informational.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLResult, EOLStatus, HardwareModel, RiskCategory


class ChenbroChecker(BaseChecker):
    """Chenbro EOL checker — chassis are passive hardware."""

    manufacturer_name = "Chenbro"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()
        if normalized.startswith("CHENBRO "):
            normalized = normalized[8:]

        if normalized.startswith(("RB", "RM")):
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="chenbro-generation",
                confidence=70,
                notes="Server chassis - passive hardware, no firmware lifecycle",
                risk_category=RiskCategory.INFORMATIONAL,
                date_source="none",
            )

        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="chenbro-generation",
            confidence=60,
            notes="Chenbro product, passive hardware",
            risk_category=RiskCategory.INFORMATIONAL,
            date_source="none",
        )
