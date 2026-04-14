"""Micron EOL checker using product line and part number rules.

Covers enterprise SSDs, server DRAM, Crucial-branded products, and MPN
ordering codes (MTFDDAK*, MTFDKC*, etc.).
Classification by SSD series number, DRAM prefix, or Crucial part pattern.
No HTTP calls needed.
"""

import re
from datetime import date, datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── Memory speed-code → release date mapping ──────────────────────────
_MICRON_SPEED_DATES: dict[str, date] = {
    "1G4": date(2009, 6, 1),     # DDR3-1333
    "1G6": date(2011, 1, 1),     # DDR3-1600
    "2G1": date(2014, 9, 1),     # DDR4-2133
    "2G3": date(2016, 3, 1),     # DDR4-2400
    "2G6": date(2017, 7, 1),     # DDR4-2666
    "2G9": date(2019, 4, 1),     # DDR4-2933
    "3G2": date(2020, 3, 1),     # DDR4-3200
    "3G3": date(2020, 6, 1),     # DDR4-3200 (higher bin)
}
_MICRON_SPEED_RE = re.compile(r"-(\dG\d)")

# ── SSD ordering code rules (MPN prefix, checked before series names) ─
# (regex, status, confidence, notes)
_SSD_ORDERING_RULES: list[tuple[re.Pattern, EOLStatus, int, str]] = [
    # MTFDDAK*TDC* = 5100 series → EOL
    (re.compile(r"^MTFDDAK.*TDC"), EOLStatus.EOL, 75,
     "Micron 5100 series SATA SSD (MTFDDAK/TDC ordering code)"),
    # MTFDDAK*TDS* = 5200 series → EOL
    (re.compile(r"^MTFDDAK.*TDS"), EOLStatus.EOL, 75,
     "Micron 5200 series SATA SSD (MTFDDAK/TDS ordering code)"),
    # MTFDDAK*TGA* = 5300 series → active
    (re.compile(r"^MTFDDAK.*TGA"), EOLStatus.ACTIVE, 75,
     "Micron 5300 series SATA SSD (MTFDDAK/TGA ordering code)"),
    # MTFDDAK*QDE* = 5300 QLC → active
    (re.compile(r"^MTFDDAK.*QDE"), EOLStatus.ACTIVE, 75,
     "Micron 5300 QLC SATA SSD (MTFDDAK/QDE ordering code)"),
    # MTFDDAK*MBP* = M500/M600 → EOL
    (re.compile(r"^MTFDDAK.*MBP"), EOLStatus.EOL, 75,
     "Micron M500/M600 SATA SSD (MTFDDAK/MBP ordering code)"),
    # MTFDDAK catch-all → active (newer 5400 series likely)
    (re.compile(r"^MTFDDAK"), EOLStatus.ACTIVE, 55,
     "Micron SATA SSD (MTFDDAK ordering code)"),
    # MTFDKC*TFR/TFC = 7300/7450 → active
    (re.compile(r"^MTFDKC.*TF[RC]"), EOLStatus.ACTIVE, 75,
     "Micron 7300/7450 NVMe SSD (MTFDKC ordering code)"),
    # MTFDKC*TGP/TGR/TGH = 7450 → active
    (re.compile(r"^MTFDKC.*TG[PRH]"), EOLStatus.ACTIVE, 75,
     "Micron 7450 NVMe SSD (MTFDKC ordering code)"),
    # MTFDKC catch-all → active
    (re.compile(r"^MTFDKC"), EOLStatus.ACTIVE, 60,
     "Micron enterprise NVMe SSD (MTFDKC ordering code)"),
    # MTFDHB* = enterprise NVMe → active
    (re.compile(r"^MTFDHB"), EOLStatus.ACTIVE, 70,
     "Micron enterprise NVMe SSD (MTFDHB ordering code)"),
    # MTFDHAL/MTFDLAL = 9400 series → active
    (re.compile(r"^MTFD[HL]AL"), EOLStatus.ACTIVE, 75,
     "Micron 9400 series NVMe SSD (ordering code)"),
    # MTFDKBA* = consumer NVMe → active
    (re.compile(r"^MTFDKBA"), EOLStatus.ACTIVE, 70,
     "Micron consumer NVMe SSD (MTFDKBA ordering code)"),
    # MTFDDAV* = consumer SATA M.2 → active
    (re.compile(r"^MTFDDAV"), EOLStatus.ACTIVE, 70,
     "Micron consumer SATA M.2 SSD (MTFDDAV ordering code)"),
    # MTFDKBG* = 7300/7400 M.2 → active
    (re.compile(r"^MTFDKBG"), EOLStatus.ACTIVE, 70,
     "Micron 7300/7400 M.2 NVMe SSD (MTFDKBG ordering code)"),
]

# ── SSD product line lookup (substring match) ────────────────────────
# Longer keys first to avoid partial matches (e.g. "5210" before "52")
# Tuples: (key, status, notes, eol_date_or_None)
_SSD_RULES: list[tuple[str, EOLStatus, str]] = [
    ("M510DC", EOLStatus.EOL, "Micron M510DC - very old enterprise SATA, EOL"),
    ("P4MU312", EOLStatus.EOL, "Micron P4MU312 - OEM model, EOL"),
    ("5100", EOLStatus.EOL, "Micron 5100 - old enterprise SATA, EOL"),
    ("5210", EOLStatus.EOL, "Micron 5210 ION - QLC SATA, EOL"),
    ("5200", EOLStatus.EOL, "Micron 5200 - old enterprise SATA, EOL"),
    ("5300", EOLStatus.EOL, "Micron 5300 - replaced by 5400, EOL"),
    ("5400", EOLStatus.ACTIVE, "Micron 5400 PRO - current enterprise SATA"),
    ("7300", EOLStatus.EOL, "Micron 7300 - replaced by 7450, EOL"),
    ("7400", EOLStatus.ACTIVE, "Micron 7400 - current enterprise NVMe"),
    ("7450", EOLStatus.ACTIVE, "Micron 7450 PRO - current enterprise NVMe"),
    ("7500", EOLStatus.ACTIVE, "Micron 7500 PRO - current enterprise NVMe"),
    ("9300", EOLStatus.EOL, "Micron 9300 - replaced by 9400, EOL"),
    ("9400", EOLStatus.ACTIVE, "Micron 9400 PRO - current enterprise NVMe"),
    ("9550", EOLStatus.ACTIVE, "Micron 9550 PRO - current enterprise NVMe"),
    ("6500", EOLStatus.ACTIVE, "Micron 6500 ION - current QLC NVMe"),
    ("6550", EOLStatus.ACTIVE, "Micron 6550 ION - current QLC NVMe"),
    ("2300", EOLStatus.EOL, "Micron 2300 - older client NVMe, EOL"),
]

# ── DRAM prefix rules ────────────────────────────────────────────────
_DRAM_EOL_PREFIXES = ["MT36KSF", "MT18KSF"]
_DRAM_ACTIVE_PREFIXES = [
    "MTA36ASF", "MTA18ADF", "MTA18ASF", "MTA72ASS",
    "MTA8ATF", "MTA9ASF", "MTA16ATF",
    "MEM-DR516", "MEM-DR512", "MEM-DR416", "MEM-VR416",
]

# ── Crucial DDR4 substring patterns (ACTIVE) ────────────────────────
_CRUCIAL_DDR4_CODES = ["RFD4", "WFD8", "WFS8", "XFD8", "DFD8"]

# Crucial DDR4 speed code pattern: type code (3 letters) followed by 4-digit speed
# e.g. CT16G4DFD8213 → DFD + 8213 (DDR4-2133)
_CRUCIAL_SPEED_RE = re.compile(
    r"(?:DFD|RFD|XFD|WFD|WFS|SFD)(8\d{2,3})",
)

_MICRON_PREFIX_RE = re.compile(
    r"^(?:MICRON\s+|MIC\s+|CRUCIAL\s+|CRU\s+)",
    re.IGNORECASE,
)


class MicronChecker(BaseChecker):
    """Micron EOL checker using product line and part number rules."""

    manufacturer_name = "Micron"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)
        result = self._classify(model, normalized)
        if result:
            return result

        # Fallback: try original_item
        if model.original_item and model.original_item != model.model:
            item_cleaned = re.sub(
                r"^[A-Z /]+:(NEW|USED|REFURBISHED):",
                "",
                model.original_item.strip().upper(),
            )
            item_normalized = self._normalize(item_cleaned)
            if item_normalized != normalized:
                result = self._classify(model, item_normalized)
                if result:
                    return result

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="micron-product-rules",
            confidence=50,
            notes="micron-model-not-classified",
        )

    def _classify(
        self, model: HardwareModel, normalized: str,
    ) -> EOLResult | None:
        """Try to classify a normalized model string. Returns None if no match."""
        # ── SSD ordering code classification (before series names) ──
        for pattern, status, confidence, notes in _SSD_ORDERING_RULES:
            if pattern.search(normalized):
                return self._make_ssd_result(model, status, notes)

        # SSD product line match
        for key, status, notes in _SSD_RULES:
            if key in normalized:
                return self._make_ssd_result(model, status, notes)

        # DRAM prefix match — DDR3 EOL
        for prefix in _DRAM_EOL_PREFIXES:
            if normalized.startswith(prefix):
                result = self._make_dram_result(
                    model, EOLStatus.EOL,
                    RiskCategory.PROCUREMENT,
                    f"Micron DDR3 {prefix} - end of life",
                )
                self._apply_speed_date(result, normalized)
                return result

        # DRAM prefix match — DDR4/DDR5 ACTIVE
        for prefix in _DRAM_ACTIVE_PREFIXES:
            if normalized.startswith(prefix):
                result = self._make_dram_result(
                    model, EOLStatus.ACTIVE,
                    RiskCategory.NONE,
                    f"Micron DDR4/DDR5 {prefix} - current",
                )
                self._apply_speed_date(result, normalized)
                return result

        # Crucial-branded models (CT part number or MX/BX/T prefix)
        if normalized.startswith("CT"):
            return self._check_crucial(model, normalized)

        # Crucial SSD by product name (after CRU prefix stripped)
        crucial_result = self._check_crucial_ssd_name(model, normalized)
        if crucial_result:
            return crucial_result

        return None

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        # Strip leading capacity like "15.36TB " or "960GB "
        s = re.sub(r"^\d+(?:\.\d+)?(?:TB|GB)\s+", "", s)
        s = _MICRON_PREFIX_RE.sub("", s)
        # Strip capacity again (may appear after manufacturer prefix)
        s = re.sub(r"^\d+(?:\.\d+)?(?:TB|GB)\s+", "", s)
        return s.strip()

    @staticmethod
    def _check_crucial(
        model: HardwareModel, normalized: str
    ) -> EOLResult:
        # Crucial P1 SSD
        if "P1SSD" in normalized:
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="micron-product-rules",
                confidence=75,
                notes="Crucial P1 NVMe SSD - EOL",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                risk_category=RiskCategory.PROCUREMENT,
                date_source="none",
            )
        # Crucial T705 Gen5 NVMe
        if "T705" in normalized:
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="micron-product-rules",
                confidence=75,
                notes="Crucial T705 Gen5 NVMe SSD - current",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.NONE,
            )
        # Crucial DDR4 speed-based classification
        # Part numbers encode speed after 3-letter type code:
        #   8213=DDR4-2133, 824x=DDR4-2400 → EOL (old speeds)
        #   8266+=DDR4-2666+ → current
        speed_match = _CRUCIAL_SPEED_RE.search(normalized)
        if speed_match:
            speed_code = speed_match.group(1)
            if speed_code.startswith("821"):
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="micron-product-rules",
                    confidence=65,
                    notes=f"Crucial DDR4-2133 (speed code {speed_code}) - older generation, EOL",
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.PROCUREMENT,
                    date_source="none",
                )
            if speed_code.startswith("824"):
                return EOLResult(
                    model=model,
                    status=EOLStatus.ACTIVE,
                    checked_at=datetime.now(),
                    source_name="micron-product-rules",
                    confidence=65,
                    notes=f"Crucial DDR4-2400 RDIMM (speed code {speed_code}) - still available",
                    eol_reason=EOLReason.NONE,
                    risk_category=RiskCategory.INFORMATIONAL,
                    date_source="none",
                )
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="micron-product-rules",
                confidence=65,
                notes="Crucial DDR4 memory - current",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.NONE,
            )
        # Crucial DDR4 by type code substring (fallback for non-standard formats)
        for code in _CRUCIAL_DDR4_CODES:
            if code in normalized:
                return EOLResult(
                    model=model,
                    status=EOLStatus.ACTIVE,
                    checked_at=datetime.now(),
                    source_name="micron-product-rules",
                    confidence=65,
                    notes="Crucial DDR4 memory - current",
                    eol_reason=EOLReason.NONE,
                    risk_category=RiskCategory.NONE,
                )
        # Any CT-prefix model: classify as Crucial memory/SSD, low confidence
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="micron-product-rules",
            confidence=40,
            notes="Crucial product - CT-prefix recognized but specific model not classified",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.INFORMATIONAL,
        )

    @staticmethod
    def _check_crucial_ssd_name(
        model: HardwareModel, normalized: str
    ) -> EOLResult | None:
        """Match Crucial SSDs by product name (e.g. 'CRU MX500')."""
        _CRUCIAL_SSD_RULES: list[tuple[str, EOLStatus, str]] = [
            ("MX500", EOLStatus.ACTIVE, "Crucial MX500 - current consumer SATA SSD"),
            ("MX300", EOLStatus.EOL, "Crucial MX300 - consumer SATA SSD, EOL"),
            ("MX200", EOLStatus.EOL, "Crucial MX200 - consumer SATA SSD, EOL"),
            ("BX500", EOLStatus.ACTIVE, "Crucial BX500 - current budget consumer SSD"),
            ("T705", EOLStatus.ACTIVE, "Crucial T705 Gen5 NVMe SSD - current"),
            ("P1", EOLStatus.EOL, "Crucial P1 NVMe SSD - EOL"),
        ]
        for key, status, notes in _CRUCIAL_SSD_RULES:
            if key in normalized:
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="micron-product-rules",
                    confidence=75,
                    notes=notes,
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED
                    if status == EOLStatus.EOL
                    else EOLReason.NONE,
                    risk_category=RiskCategory.PROCUREMENT
                    if status == EOLStatus.EOL
                    else RiskCategory.NONE,
                    date_source="none",
                )
        return None

    @staticmethod
    def _apply_speed_date(result: EOLResult, normalized: str) -> None:
        """Set release_date from Micron memory speed code (e.g. -2G6 = DDR4-2666)."""
        match = _MICRON_SPEED_RE.search(normalized)
        if match:
            speed_code = match.group(1)
            rel_date = _MICRON_SPEED_DATES.get(speed_code)
            if rel_date:
                result.release_date = rel_date
                result.date_source = "micron-speed-bin"

    @staticmethod
    def _make_ssd_result(
        model: HardwareModel, status: EOLStatus, notes: str,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="micron-product-rules",
            confidence=75,
            notes=notes,
            eol_reason=EOLReason.PRODUCT_DISCONTINUED
            if status == EOLStatus.EOL
            else EOLReason.NONE,
            risk_category=RiskCategory.PROCUREMENT
            if status == EOLStatus.EOL
            else RiskCategory.NONE,
            date_source="none",
        )

    @staticmethod
    def _make_dram_result(
        model: HardwareModel,
        status: EOLStatus,
        risk: RiskCategory,
        notes: str,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="micron-product-rules",
            confidence=65,
            notes=notes,
            eol_reason=EOLReason.PRODUCT_DISCONTINUED
            if status == EOLStatus.EOL
            else EOLReason.NONE,
            risk_category=risk,
            date_source="none",
        )
