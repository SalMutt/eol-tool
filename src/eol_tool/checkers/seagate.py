"""Seagate EOL checker using capacity-based classification rules.

Seagate does not publish formal EOL pages.  Classification is based on
drive capacity and product era — enterprise performance 10K/15K SAS drives
and older Exos models are considered EOL.  No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Regex to extract capacity from model strings like "1.2TB SEAGATE ENT - M0009"
_CAPACITY_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(TB|GB)",
    re.IGNORECASE,
)

_SEAGATE_PREFIX_RE = re.compile(
    r"^(?:SEAGATE\s+ENT(?:ERPRISE)?|SEAGATE)\s*[-–]?\s*",
    re.IGNORECASE,
)


def _extract_capacity_tb(model_str: str) -> float | None:
    """Extract drive capacity in TB from a model string."""
    m = _CAPACITY_RE.search(model_str)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "GB":
        value /= 1000
    return value


def _classify_by_capacity(
    capacity_tb: float,
) -> tuple[EOLStatus, RiskCategory, str]:
    """Classify a Seagate enterprise HDD by capacity."""
    if capacity_tb < 4.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            f"Seagate enterprise {capacity_tb:.1f}TB - legacy small capacity, EOL",
        )
    if capacity_tb < 8.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            f"Seagate enterprise {capacity_tb:.1f}TB - older generation, EOL",
        )
    if capacity_tb < 10.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Exos X10 10TB - EOL",
        )
    if capacity_tb < 12.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Exos X12 12TB - EOL",
        )
    if capacity_tb < 14.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Exos X14 14TB - EOL, replaced by X16+",
        )
    if capacity_tb < 16.1:
        return (
            EOLStatus.ACTIVE,
            RiskCategory.INFORMATIONAL,
            "Seagate Exos X16 16TB - active but aging",
        )
    return (
        EOLStatus.ACTIVE,
        RiskCategory.NONE,
        f"Seagate Exos {capacity_tb:.0f}TB - current generation",
    )


class SeagateChecker(BaseChecker):
    """Seagate EOL checker using capacity-based classification."""

    manufacturer_name = "Seagate"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        # Capacity may be in original_item (before normalization strips it)
        raw = model.original_item or model.model
        capacity_tb = _extract_capacity_tb(raw)

        if capacity_tb is not None:
            status, risk, notes = _classify_by_capacity(capacity_tb)
            return EOLResult(
                model=model,
                status=status,
                checked_at=datetime.now(),
                source_name="seagate-capacity-rules",
                confidence=65,
                notes=notes,
                eol_reason=EOLReason.PRODUCT_DISCONTINUED
                if status == EOLStatus.EOL
                else EOLReason.NONE,
                risk_category=risk,
                date_source="none",
            )

        # Cannot determine capacity — return UNKNOWN
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="seagate-capacity-rules",
            confidence=50,
            notes="seagate-model-not-classified",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.PROCUREMENT,
        )
