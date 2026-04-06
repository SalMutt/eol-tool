"""Samsung EOL checker for SSDs and server DRAM.

Covers PM-series enterprise SSDs and server DRAM with M393A, M391A,
M386A, M321R prefixes.  No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── SSD product line rules (substring match) ─────────────────────────
# Tuples: (key, status, risk, notes, eol_date_or_None)
_SSD_RULES: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("PM9A3", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM9A3 - current enterprise NVMe"),
    ("PM983", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM983 - enterprise NVMe, replaced by PM9A3, EOL"),
    ("PM981", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM981 - enterprise NVMe, EOL"),
    ("PM963", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM963 - very old enterprise NVMe, EOL"),
    ("PM897", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM897 - current enterprise SATA"),
    ("PM893", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM893 - current enterprise SATA"),
    ("PM883", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM883 - replaced by PM893, EOL"),
    ("PM863A", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM863a - old enterprise SATA, EOL"),
    ("PM863", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM863 - old enterprise SATA, EOL"),
    ("PM1725", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM1725 - old enterprise NVMe, EOL"),
    ("PM1733", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM1733 - current enterprise NVMe"),
    ("PM1735", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM1735 - current enterprise NVMe"),
    ("PM1653", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM1653 - current enterprise SAS SSD"),
    ("PM1643", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM1643 - enterprise SAS, nearing EOL"),
    ("PM9C1A", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM9C1a - current enterprise NVMe"),
    ("883 DCT", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 883 DCT - enterprise SATA, EOL"),
    ("970 EVO PLUS", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung 970 EVO Plus - consumer NVMe, current"),
    ("970 EVO", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 970 EVO - consumer NVMe, discontinued"),
    ("870 QVO", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung 870 QVO - consumer SATA QLC, current"),
    ("860 EVO", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 860 EVO - consumer SATA, EOL"),
    ("870 EVO", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     "Samsung 870 EVO - consumer SATA, still current"),
    ("860 PRO", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 860 PRO - consumer SATA, EOL"),
    ("850 EVO", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 850 EVO - consumer SATA, EOL"),
    ("840 EVO", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 840 EVO - consumer SATA, EOL"),
    ("840 SSD", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung 840 SSD - consumer SATA, EOL"),
    ("980 PRO", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung 980 PRO - consumer NVMe, current"),
    ("990 PRO", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung 990 PRO - consumer NVMe, current"),
    ("SM863", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung SM863 - old enterprise SATA, EOL"),
    ("SM883", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung SM883 - enterprise SATA, replaced by PM893"),
    ("MZ7L3", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM893/PM897 (MZ7L3) - current enterprise SATA"),
    ("MZ7LM", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM863 (MZ7LM) - old enterprise SATA, EOL"),
    ("MZ7KM", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung SM863 (MZ7KM) - old enterprise SATA, EOL"),
    ("MZILT", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM1643 (MZILT) - enterprise SAS"),
    ("MZQLB", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung PM983 (MZQLB) - enterprise NVMe, EOL"),
    ("MZQL2", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung PM9A3 (MZQL2) - current enterprise NVMe"),
]

# ── DRAM prefix rules ────────────────────────────────────────────────
# Tuples: (prefix, status, risk, notes, eol_date_or_None)
_DRAM_RULES: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("M321R", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung DDR5 RDIMM - current generation"),
    ("M393A", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung DDR4 RDIMM - current"),
    ("M391A", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung DDR4 ECC UDIMM - current"),
    ("M386A", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Samsung DDR4 LRDIMM - current"),
    ("M393B", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung DDR3 RDIMM - end of life"),
    ("M391B", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Samsung DDR3 ECC UDIMM - end of life"),
]

_SAMSUNG_PREFIX_RE = re.compile(
    r"^(?:SAMSUNG\s+|SAM\s+)", re.IGNORECASE,
)


class SamsungChecker(BaseChecker):
    """Samsung EOL checker for SSDs and server DRAM."""

    manufacturer_name = "Samsung"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # SSD product line match
        for key, status, risk, notes in _SSD_RULES:
            if key in normalized:
                return self._make_result(model, status, risk, notes, 75)

        # DRAM prefix match
        for prefix, status, risk, notes in _DRAM_RULES:
            if normalized.startswith(prefix):
                return self._make_result(model, status, risk, notes, 65)

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="samsung-product-rules",
            confidence=50,
            notes="samsung-model-not-classified",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        s = _SAMSUNG_PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _make_result(
        model: HardwareModel,
        status: EOLStatus,
        risk: RiskCategory,
        notes: str,
        confidence: int,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="samsung-product-rules",
            confidence=confidence,
            notes=notes,
            eol_reason=EOLReason.PRODUCT_DISCONTINUED
            if status == EOLStatus.EOL
            else EOLReason.NONE,
            risk_category=risk,
            date_source="none",
        )
