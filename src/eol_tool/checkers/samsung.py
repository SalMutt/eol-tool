"""Samsung EOL checker for SSDs and server DRAM.

Covers PM-series enterprise SSDs, server DRAM with M393A, M391A, M386A,
M321R prefixes, and MPN ordering codes (MZ-7*, MZ-V*, MZ1L*, etc.).
No HTTP calls needed.
"""

import re
from datetime import date, datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── Memory speed-suffix → release date mapping ────────────────────────
_SAMSUNG_SPEED_DATES: dict[str, date] = {
    "CQKZJ": date(2023, 1, 1),   # DDR5-5600
    "CPB": date(2014, 9, 1),     # DDR4-2133
    "CRC": date(2016, 3, 1),     # DDR4-2400
    "CTD": date(2017, 7, 1),     # DDR4-2666
    "CVF": date(2019, 4, 1),     # DDR4-2933
    "CWE": date(2020, 3, 1),     # DDR4-3200
    "CK0": date(2011, 1, 1),     # DDR3-1600
    "YK0": date(2011, 1, 1),     # DDR3-1600
    "YH9": date(2009, 6, 1),     # DDR3-1333
    "PB": date(2011, 1, 1),      # DDR3-1600
    "CAE": date(2021, 11, 1),    # DDR5-4800
    "CWK": date(2023, 1, 1),     # DDR5-5600
    "CWM": date(2023, 1, 1),     # DDR5-5600
}
# Pre-sorted longest-first for matching priority
_SAMSUNG_SPEED_SUFFIXES = sorted(_SAMSUNG_SPEED_DATES, key=len, reverse=True)

# ── SSD ordering code rules (MPN prefix match, checked before names) ─
# (regex, status, risk, confidence, notes)
_SSD_ORDERING_RULES: list[tuple[re.Pattern, EOLStatus, RiskCategory, int, str]] = [
    # MZ-7LH* = PM883/PM893 → active
    (re.compile(r"^MZ[\-.]?7LH"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung PM883/PM893 SATA SSD (MZ-7LH ordering code)"),
    # MZ-7LM* = PM863 → EOL
    (re.compile(r"^MZ[\-.]?7LM"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung PM863 SATA SSD (MZ-7LM ordering code)"),
    # MZ-7TE* = 840 EVO → EOL
    (re.compile(r"^MZ[\-.]?7TE"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung 840 EVO SATA SSD (MZ-7TE ordering code)"),
    # MZ-76* = 860 EVO/PRO → EOL
    (re.compile(r"^MZ[\-.]?76"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung 860 EVO/PRO SATA SSD (MZ-76 ordering code)"),
    # MZ-77* = 870 EVO/PRO → active
    (re.compile(r"^MZ[\-.]?77"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung 870 EVO/PRO SATA SSD (MZ-77 ordering code)"),
    # MZ-V7S* = 970 EVO Plus → EOL
    (re.compile(r"^MZ[\-.]?V7S"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung 970 EVO Plus NVMe SSD (MZ-V7S ordering code)"),
    # MZ-V7E* = 970 EVO → EOL
    (re.compile(r"^MZ[\-.]?V7E"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung 970 EVO NVMe SSD (MZ-V7E ordering code)"),
    # MZ-V9P* = 990 PRO → active
    (re.compile(r"^MZ[\-.]?V9P"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung 990 PRO NVMe SSD (MZ-V9P ordering code)"),
    # MZ7L3* = PM893/PM897 → active
    (re.compile(r"^MZ7L3"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung PM893/PM897 SATA SSD (MZ7L3 ordering code)"),
    # MZ7KM* = SM863 → EOL
    (re.compile(r"^MZ7KM"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung SM863 SATA SSD (MZ7KM ordering code)"),
    # MZILT* = PM1643 SAS → active
    (re.compile(r"^MZILT"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung PM1643 SAS SSD (MZILT ordering code)"),
    # Catch-all MZ-7* = Samsung SATA SSD (older, likely EOL)
    (re.compile(r"^MZ[\-.]?7"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 60,
     "Samsung SATA SSD (MZ-7 ordering code)"),
    # Catch-all MZ-V* = Samsung NVMe SSD
    (re.compile(r"^MZ[\-.]?V"), EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, 55,
     "Samsung NVMe SSD (MZ-V ordering code)"),
    # MZ1L* = PM9A3 data center NVMe → active
    (re.compile(r"^MZ1L"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung PM9A3 data center NVMe SSD (MZ1L ordering code)"),
    # MZ-1LB* = PM983 → EOL
    (re.compile(r"^MZ[\-.]?1LB"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung PM983 NVMe SSD (MZ-1LB ordering code)"),
    # MZQL* = PM9A3/PM9C3 → active
    (re.compile(r"^MZQL"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung PM9A3/PM9C3 enterprise NVMe SSD (MZQL ordering code)"),
    # MZVLB* = PM981 → EOL
    (re.compile(r"^MZVLB"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Samsung PM981 NVMe SSD (MZVLB ordering code)"),
    # MZILG* = PM1743 → active
    (re.compile(r"^MZILG"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Samsung PM1743 NVMe SSD (MZILG ordering code)"),
]

# ── Memory ordering code rules (MPN prefix match) ───────────────────
# (regex, status, risk, confidence, notes)
_MEM_ORDERING_RULES: list[tuple[re.Pattern, EOLStatus, RiskCategory, int, str]] = [
    # M321* = DDR5 → active
    (re.compile(r"^M321"), EOLStatus.ACTIVE, RiskCategory.NONE, 70,
     "Samsung DDR5 memory (M321 ordering code)"),
    # M393A* = DDR4 RDIMM → active
    (re.compile(r"^M393A"), EOLStatus.ACTIVE, RiskCategory.NONE, 70,
     "Samsung DDR4 RDIMM (M393A ordering code)"),
    # M393B* = DDR3 RDIMM → EOL
    (re.compile(r"^M393B"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Samsung DDR3 RDIMM (M393B ordering code)"),
    # M391A* = DDR4 ECC UDIMM → active
    (re.compile(r"^M391A"), EOLStatus.ACTIVE, RiskCategory.NONE, 70,
     "Samsung DDR4 ECC UDIMM (M391A ordering code)"),
    # M391B* = DDR3 ECC UDIMM → EOL
    (re.compile(r"^M391B"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Samsung DDR3 ECC UDIMM (M391B ordering code)"),
    # M378A* = DDR4 UDIMM → active
    (re.compile(r"^M378A"), EOLStatus.ACTIVE, RiskCategory.NONE, 70,
     "Samsung DDR4 UDIMM (M378A ordering code)"),
    # M378B* = DDR3 UDIMM → EOL
    (re.compile(r"^M378B"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Samsung DDR3 UDIMM (M378B ordering code)"),
    # M471A* = DDR4 SO-DIMM → active
    (re.compile(r"^M471A"), EOLStatus.ACTIVE, RiskCategory.NONE, 70,
     "Samsung DDR4 SO-DIMM (M471A ordering code)"),
    # M471B* = DDR3 SO-DIMM → EOL
    (re.compile(r"^M471B"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Samsung DDR3 SO-DIMM (M471B ordering code)"),
    # M386A* = DDR4 LRDIMM → active
    (re.compile(r"^M386A"), EOLStatus.ACTIVE, RiskCategory.NONE, 70,
     "Samsung DDR4 LRDIMM (M386A ordering code)"),
    # M386B* = DDR3 LRDIMM → EOL
    (re.compile(r"^M386B"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Samsung DDR3 LRDIMM (M386B ordering code)"),
    # Catch-all M393/M391/M378/M471/M386 without A/B suffix
    (re.compile(r"^M(?:393|391|378|471|386)"), EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, 50,
     "Samsung server memory (ordering code)"),
]

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

        # Skip literal "VARIOUS" placeholder
        if normalized == "VARIOUS":
            return EOLResult(
                model=model,
                status=EOLStatus.UNKNOWN,
                checked_at=datetime.now(),
                source_name="samsung-product-rules",
                confidence=0,
                notes="samsung-VARIOUS-placeholder-skipped",
            )

        # ── Ordering code classification (before human-readable names) ──
        # SSD ordering codes (MZ-*, MZ1L*, MZQL*, etc.)
        for pattern, status, risk, confidence, notes in _SSD_ORDERING_RULES:
            if pattern.search(normalized):
                return self._make_result(model, status, risk, notes, confidence)

        # Memory ordering codes (M393*, M391*, M378*, M471*, M386*, M321*)
        for pattern, status, risk, confidence, notes in _MEM_ORDERING_RULES:
            if pattern.search(normalized):
                result = self._make_result(model, status, risk, notes, confidence)
                self._apply_speed_date(result, normalized)
                return result

        # ── Human-readable name patterns ──
        # SSD product line match
        for key, status, risk, notes in _SSD_RULES:
            if key in normalized:
                return self._make_result(model, status, risk, notes, 75)

        # DRAM prefix match
        for prefix, status, risk, notes in _DRAM_RULES:
            if normalized.startswith(prefix):
                result = self._make_result(model, status, risk, notes, 65)
                self._apply_speed_date(result, normalized)
                return result

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
    def _apply_speed_date(result: EOLResult, normalized: str) -> None:
        """Set release_date from Samsung memory speed suffix (e.g. -CWE = DDR4-3200)."""
        for suffix in _SAMSUNG_SPEED_SUFFIXES:
            if normalized.endswith(suffix) or f"-{suffix}" in normalized:
                result.release_date = _SAMSUNG_SPEED_DATES[suffix]
                result.date_source = "samsung-speed-bin"
                break

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
