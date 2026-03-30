"""Toshiba EOL checker using MG series generation classification.

Toshiba enterprise HDDs are classified by MG generation number.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# MG generation → (status, risk, notes)
_MG_GENERATIONS: dict[str, tuple[EOLStatus, RiskCategory, str]] = {
    "MG04": (
        EOLStatus.EOL, RiskCategory.PROCUREMENT,
        "Toshiba MG04 - 4th gen enterprise, EOL",
    ),
    "MG06": (
        EOLStatus.EOL, RiskCategory.PROCUREMENT,
        "Toshiba MG06 - 6th gen, replaced by MG08+, EOL",
    ),
    "MG07": (
        EOLStatus.EOL, RiskCategory.PROCUREMENT,
        "Toshiba MG07 - 7th gen helium, replaced by MG09+, EOL",
    ),
    "MG08": (
        EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
        "Toshiba MG08 - 8th gen, active but aging",
    ),
    "MG09": (
        EOLStatus.ACTIVE, RiskCategory.NONE,
        "Toshiba MG09 - 9th gen, current",
    ),
    "MG10": (
        EOLStatus.ACTIVE, RiskCategory.NONE,
        "Toshiba MG10 - 10th gen, current",
    ),
    "MD06": (
        EOLStatus.EOL, RiskCategory.PROCUREMENT,
        "Toshiba MD06 - older desktop line, EOL",
    ),
}

_TOS_PREFIX_RE = re.compile(r"^TOS\s+", re.IGNORECASE)
_CAPACITY_PREFIX_RE = re.compile(
    r"^\d+(?:\.\d+)?\s*(?:TB|GB)\s+", re.IGNORECASE
)


class ToshibaChecker(BaseChecker):
    """Toshiba EOL checker using MG series generation rules."""

    manufacturer_name = "Toshiba"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # Check for Toshiba SSD models
        if "THNSNH" in normalized:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Toshiba THNSNH SSD - EOL",
            )

        # Match MG/MD generation
        for prefix, (status, risk, notes) in _MG_GENERATIONS.items():
            if prefix in normalized:
                return self._make_result(model, status, risk, notes)

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="toshiba-generation-rules",
            confidence=50,
            notes="toshiba-model-not-classified",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        s = _TOS_PREFIX_RE.sub("", s)
        s = _CAPACITY_PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _make_result(
        model: HardwareModel,
        status: EOLStatus,
        risk: RiskCategory,
        notes: str,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="toshiba-generation-rules",
            confidence=70,
            notes=notes,
            eol_reason=EOLReason.PRODUCT_DISCONTINUED
            if status == EOLStatus.EOL
            else EOLReason.NONE,
            risk_category=risk,
        )
