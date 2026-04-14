"""Solidigm EOL checker for enterprise SSDs.

Solidigm was formed from Intel's NAND business in 2021.
No HTTP calls needed.
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# (pattern, status, confidence, notes)
# Order matters: more specific patterns before broader ones.
_RULES: list[tuple[str, EOLStatus, int, str]] = [
    # EOL products (older Intel-era)
    ("D5-P4320", EOLStatus.EOL, 80, "Solidigm D5-P4320 - older QLC NVMe, EOL"),
    ("D5P4320", EOLStatus.EOL, 80, "Solidigm D5-P4320 - older QLC NVMe, EOL"),
    # Active D5-P5xxx products
    ("D5-P5", EOLStatus.ACTIVE, 80, "Solidigm D5-P5 series - current QLC NVMe"),
    # Active D7 products
    ("D7", EOLStatus.ACTIVE, 80, "Solidigm D7 series - current enterprise NVMe"),
    # Consumer lines
    ("P41", EOLStatus.ACTIVE, 80, "Solidigm P41 - current consumer NVMe"),
    ("P44", EOLStatus.ACTIVE, 80, "Solidigm P44 - current consumer NVMe"),
    # SSDPF part numbers (current enterprise)
    ("SSDPF", EOLStatus.ACTIVE, 70, "Solidigm SSDPF - current enterprise NVMe"),
    # Synergy line
    ("SYNERGY", EOLStatus.ACTIVE, 80, "Solidigm Synergy - current enterprise NVMe"),
]


class SolidigmChecker(BaseChecker):
    """Solidigm EOL checker for enterprise SSDs."""

    manufacturer_name = "Solidigm"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)
        upper = normalized.upper()

        for pattern, status, confidence, notes in _RULES:
            if pattern.upper() in upper:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="solidigm-product-rules",
                    confidence=confidence,
                    notes=notes,
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION
                    if status == EOLStatus.EOL
                    else EOLReason.NONE,
                    risk_category=RiskCategory.PROCUREMENT,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="solidigm-product-rules",
            confidence=50,
            notes="Solidigm model not specifically classified",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.PROCUREMENT,
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip()
        upper = s.upper()
        for prefix in ("SOLIDIGM ", "INTEL "):
            if upper.startswith(prefix):
                s = s[len(prefix):].strip()
                break
        return s
