"""ASRock EOL checker for server motherboards and chassis.

All ASRock models in the dataset are current-generation server boards.
No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Model substring → (status, risk, notes)
_PRODUCTS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("B650D4U-2L2T", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock B650D4U-2L2T/BCM - AM5 DDR4 server board, current"),
    ("B650D4U", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock B650D4U - AM5 DDR4 server board, current"),
    ("AM5D4ID-2T", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock AM5D4ID-2T - AM5 board, current"),
    ("E3C252D4U", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock E3C252D4U - Intel Xeon E server board, current"),
    ("E3C246D4U", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock E3C246D4U - Intel Xeon E server board, current"),
    ("E3C242D4U", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock E3C242D4U - Intel Xeon E server board, current"),
    ("1U4LW-B650", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock 1U4LW-B650 - AM5 chassis, current"),
    ("1U2LW-X570", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock 1U2LW-X570 - AM4 chassis, current"),
    ("SPC621D8", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock SPC621D8-2L2T - Intel W680 board, current"),
    ("X570D4U-2L2T", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     "ASRock X570D4U-2L2T - AM4 server board, aging"),
    ("X570D4U", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     "ASRock X570D4U - AM4 server board, aging"),
    ("X470D4U", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     "ASRock X470D4U - AM4 server board, still supported"),
    ("WRX90E", EOLStatus.ACTIVE, RiskCategory.NONE,
     "ASRock WRX90E-SAGE SE - Threadripper PRO board, current"),
]


class ASRockChecker(BaseChecker):
    """ASRock EOL checker for server motherboards and chassis."""

    manufacturer_name = "ASRock"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = model.model.strip().upper()

        for key, status, risk, notes in _PRODUCTS:
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="asrock-static-lookup",
                    confidence=70,
                    notes=notes,
                    eol_reason=EOLReason.NONE,
                    risk_category=risk,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="asrock-static-lookup",
            confidence=50,
            notes="asrock-model-not-classified",
        )
