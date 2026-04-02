"""Generic optics checker for white-label SFP/QSFP/XFP/CFP transceivers.

Commodity optics with no manufacturer are always available from multiple
vendors and never go EOL in any meaningful sense. This checker classifies
them as ACTIVE with risk_category NONE.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Manufacturer values treated as "no manufacturer"
_GENERIC_MANUFACTURERS = {"", "unknown", "generic"}

# Form-factor keywords
_FORM_FACTOR_RE = re.compile(
    r"\bSFP(?:\b|\+|\d)|\bSFPP\b|\bQSFP\b|\bQSFPP\b|\bQSFP28\b|\bXFP\b|\bCFP\b",
    re.IGNORECASE,
)

# Speed indicators (e.g. 1G, 10G, 25G, 40G, 50G, 100G, 400G)
_SPEED_RE = re.compile(r"(?<!\d)(?:1|10|25|40|50|100|400)G\b", re.IGNORECASE)

# Fiber/copper reach indicators
_REACH_RE = re.compile(
    r"\b(?:SR4|LR4|PLR4|SR|LR|ER|ZR|UNIV|BASE-T|COPPER)\b",
    re.IGNORECASE,
)

# Converter modules (e.g. CVR-QSFP-SFP10G)
_CONVERTER_RE = re.compile(r"\bCVR-", re.IGNORECASE)

# DWDM channel indicators: "DW" + digits, or "C" + 1-2 digits + space/end
_DWDM_RE = re.compile(r"\bDW\d+|^C\d{1,2}\s", re.IGNORECASE)


def _is_generic_manufacturer(manufacturer: str) -> bool:
    return manufacturer.strip().lower() in _GENERIC_MANUFACTURERS


def _is_optic(model: str) -> bool:
    """Return True if the model string looks like an optics transceiver."""
    if _FORM_FACTOR_RE.search(model):
        return True
    if _CONVERTER_RE.search(model):
        return True
    # Speed + reach combo without form factor (e.g. "100GBASE-SR4 QSFP28" already caught above)
    if _SPEED_RE.search(model) and _REACH_RE.search(model):
        return True
    return False


def _is_dwdm(model: str) -> bool:
    return bool(_DWDM_RE.search(model))


class GenericOpticsChecker(BaseChecker):
    """Classifies white-label optics transceivers as ACTIVE commodities."""

    manufacturer_name = "__generic_optics__"
    rate_limit = 100
    priority = 55
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        # Only handle items with no real manufacturer
        if not _is_generic_manufacturer(model.manufacturer):
            return self._not_found(model, "has-known-manufacturer")

        upper = model.model.strip().upper()
        is_dwdm = _is_dwdm(upper)
        is_optic = _is_optic(upper) or is_dwdm

        if not is_optic:
            return self._not_found(model, "not-an-optic")

        notes = "dwdm-optic-commodity" if is_dwdm else "commodity-transceiver-always-available"

        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="generic-optics-classifier",
            confidence=80,
            notes=notes,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
        )

    @staticmethod
    def _not_found(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="generic-optics-classifier",
            confidence=0,
            notes=reason,
        )
