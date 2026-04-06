"""Western Digital EOL checker using model suffix classification rules.

WD model numbers encode product line in their suffix (e.g. KFBX = Gold,
FYYZ = RE enterprise).  No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── Suffix → classification map ─────────────────────────────────────
# Active product lines
_ACTIVE_SUFFIXES = {
    "KFBX": "WD Gold enterprise - current generation",
    "FBYZ": "WD Gold enterprise - current generation",
    "EFZX": "WD Red NAS - current generation",
    "EFRX": "WD Red NAS - current generation",
}

# EOL product lines: suffix -> (notes, eol_date)
_EOL_SUFFIXES: dict[str, str] = {
    "FALS": "WD Caviar Black / RE - old consumer/enterprise, EOL",
    "FAEX": "WD Caviar Black / RE - old consumer/enterprise, EOL",
    "FBYS": "WD RE - old enterprise, EOL",
    "FBYX": "WD RE - old enterprise, EOL",
    "FYPS": "WD RE2 - old enterprise, EOL",
    "FYYZ": "WD RE / Se - enterprise, EOL",
    "FYYS": "WD RE / Se - enterprise, EOL",
    "F9YZ": "WD RE / Se - enterprise, EOL",
    "FYYG": "WD RE - old enterprise, EOL",
    "FRYZ": "WD Gold older generation - replaced by KFBX, EOL",
    "KRYZ": "WD Gold older generation, EOL",
    "AZEX": "WD Blue desktop - older consumer, EOL",
    "FZEX": "WD Black Performance - older performance line, EOL",
    "EZEX": "WD Blue - old consumer, EOL",
    "EZRZ": "WD Blue - old consumer, EOL",
    "AADS": "WD Green - very old consumer, EOL",
}

# WD model regex: captures the full WD model number
_WD_MODEL_RE = re.compile(r"(WD\d{2,5}[A-Z0-9]{3,5})", re.IGNORECASE)

# Capacity prefix to strip
_CAPACITY_PREFIX_RE = re.compile(
    r"^\d+(?:\.\d+)?\s*(?:TB|GB)\s+",
    re.IGNORECASE,
)

_WD_PREFIX_RE = re.compile(r"^WD[/\s]+", re.IGNORECASE)


class WDChecker(BaseChecker):
    """Western Digital EOL checker using model suffix classification."""

    manufacturer_name = "WD"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # WD SSD by exact part number
        if "WDS200T2G0A" in normalized:
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "WD Green SSD - current budget SSD",
            )

        # WD GREEN keyword match
        if "WD GREEN" in normalized or "WD GREEN" in model.model.upper():
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "WD Green SSD - current budget SSD",
            )

        # Try to find a WD model number
        wd_model = self._extract_wd_model(normalized)
        if not wd_model:
            return self._unknown(model, "wd-model-number-not-found")

        suffix = wd_model.upper()

        # Check active suffixes
        for sfx, notes in _ACTIVE_SUFFIXES.items():
            if sfx in suffix:
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.NONE, notes
                )

        # Check EZAZ separately — capacity-dependent
        if "EZAZ" in suffix:
            return self._make_result(
                model,
                EOLStatus.ACTIVE,
                RiskCategory.INFORMATIONAL,
                "WD Blue EZAZ - consumer, still available",
            )

        # Check EOL suffixes
        for sfx, notes in _EOL_SUFFIXES.items():
            if sfx in suffix:
                return self._make_result(
                    model,
                    EOLStatus.EOL,
                    RiskCategory.PROCUREMENT,
                    notes,
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                )

        return self._unknown(model, "wd-suffix-not-classified")

    @staticmethod
    def _normalize(model_str: str) -> str:
        """Strip capacity and WD prefixes."""
        s = model_str.strip().upper()
        s = _CAPACITY_PREFIX_RE.sub("", s)
        s = _WD_PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _extract_wd_model(normalized: str) -> str | None:
        """Extract WD model number from the normalized string."""
        # If the string starts with WD already, try the full regex
        full = "WD" + normalized if not normalized.startswith("WD") else normalized
        m = _WD_MODEL_RE.search(full)
        if m:
            return m.group(1).upper()
        # Fallback: use the raw normalized string as suffix check
        if len(normalized) >= 4:
            return normalized
        return None

    @staticmethod
    def _make_result(
        model: HardwareModel,
        status: EOLStatus,
        risk: RiskCategory,
        notes: str,
        eol_reason: EOLReason = EOLReason.NONE,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="wd-suffix-rules",
            confidence=70,
            notes=notes,
            eol_reason=eol_reason,
            risk_category=risk,
            date_source="none",
        )

    @staticmethod
    def _unknown(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="wd-suffix-rules",
            confidence=50,
            notes=reason,
        )
