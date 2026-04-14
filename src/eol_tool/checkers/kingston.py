"""Kingston EOL checker using part number pattern rules.

Covers enterprise SSDs and server/desktop memory DIMMs.  Classification
is based on DDR generation speed codes and SSD product line prefixes.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── Enterprise SSD patterns ─────────────────���────────────────────────
# Tuples: (key, status, risk, notes, eol_date_or_None)
_SSD_PATTERNS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    ("DC600", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston DC600M - current enterprise SATA mixed-use"),
    ("DC500", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston DC500R - current enterprise SATA read-intensive"),
    ("DC450R", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston DC450R - enterprise SATA, replaced by DC500R, EOL"),
    ("DC400", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston DC400 - enterprise SATA, replaced by DC500, EOL"),
    ("DC3000", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston DC3000ME - current enterprise NVMe"),
    ("DC2000B", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston DC2000B - current enterprise NVMe"),
    ("SKC3000", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston KC3000 - current consumer NVMe"),
    ("KC3000", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston KC3000 - current consumer NVMe"),
    ("KC600", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston KC600 - current consumer SATA"),
    ("KC400", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston KC400 - consumer SATA, EOL"),
    ("SKC2500", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston KC2500 - older consumer NVMe, EOL"),
    ("SA2000", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston SA2000 - consumer NVMe, EOL"),
    ("SNV2S", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston NV2 - current consumer NVMe"),
    ("A400", EOLStatus.ACTIVE, RiskCategory.NONE,
     "Kingston A400 - current consumer SATA"),
    ("SSDNOW", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston SSDNow V300 - very old consumer SATA, EOL"),
    ("V300", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     "Kingston SSDNow V300 - very old consumer SATA, EOL"),
]

# ── Memory DIMM speed-code patterns ─────────────────────────────────
# Tuples: (prefix, status, risk, notes, eol_date_or_None)
_MEMORY_PATTERNS: list[tuple[str, EOLStatus, RiskCategory, str]] = [
    # DDR5
    ("KSM64", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Server DDR5-6400"),
    ("KSM56", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Server DDR5-5600"),
    ("KSM48", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Server DDR5-4800"),
    ("KVR56", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Value DDR5-5600"),
    ("KVR48", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Value DDR5-4800"),
    # DDR4
    ("KSM32", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Server DDR4-3200"),
    ("KSM29", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Server DDR4-2933"),
    ("KSM26", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Server DDR4-2666"),
    ("KSM24", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, "Kingston Server DDR4-2400"),
    ("KVR32", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Value DDR4-3200"),
    ("KVR29", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Value DDR4-2933"),
    ("KVR26", EOLStatus.ACTIVE, RiskCategory.NONE, "Kingston Value DDR4-2666"),
    ("KVR24", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, "Kingston Value DDR4-2400"),
    ("KVR21", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, "Kingston Value DDR4-2133"),
    # DDR3 — EOL
    ("KVR16", EOLStatus.EOL, RiskCategory.PROCUREMENT, "Kingston Value DDR3-1600, EOL"),
    ("KVR13", EOLStatus.EOL, RiskCategory.PROCUREMENT, "Kingston Value DDR3-1333, EOL"),
    # Dell-specific
    ("KTD-PE424", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, "Kingston Dell DDR4-2400"),
]

_KINGSTON_PREFIX_RE = re.compile(
    r"^(?:KINGSTON\s+|KNG\s+)",
    re.IGNORECASE,
)


class KingstonChecker(BaseChecker):
    """Kingston EOL checker using part number pattern rules."""

    manufacturer_name = "Kingston"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # Try SSD patterns
        for prefix, status, risk, notes in _SSD_PATTERNS:
            if prefix in normalized:
                return self._make_result(model, status, risk, notes)

        # Try memory DIMM patterns
        for prefix, status, risk, notes in _MEMORY_PATTERNS:
            if normalized.startswith(prefix):
                return self._make_result(model, status, risk, notes)

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="kingston-pattern-rules",
            confidence=50,
            notes="kingston-model-not-classified",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        """Strip Kingston branding prefix and normalize."""
        s = model_str.strip().upper()
        s = _KINGSTON_PREFIX_RE.sub("", s)
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
            source_name="kingston-pattern-rules",
            confidence=70,
            notes=notes,
            eol_reason=EOLReason.PRODUCT_DISCONTINUED
            if status == EOLStatus.EOL
            else EOLReason.NONE,
            risk_category=risk,
            date_source="none",
        )
