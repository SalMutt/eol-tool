"""Micron EOL checker using product line and part number rules.

Covers enterprise SSDs, server DRAM, and Crucial-branded products.
Classification by SSD series number, DRAM prefix, or Crucial part pattern.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

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
    r"(?:DFD|RFD|XFD|WFD|WFS|SFD)(8\d{3})",
)

_MICRON_PREFIX_RE = re.compile(
    r"^(?:MICRON\s+|CRUCIAL\s+|CRU\s+)",
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

        # SSD product line match
        for key, status, notes in _SSD_RULES:
            if key in normalized:
                return self._make_ssd_result(model, status, notes)

        # DRAM prefix match — DDR3 EOL
        for prefix in _DRAM_EOL_PREFIXES:
            if normalized.startswith(prefix):
                return self._make_dram_result(
                    model, EOLStatus.EOL,
                    RiskCategory.PROCUREMENT,
                    f"Micron DDR3 {prefix} - end of life",
                )

        # DRAM prefix match — DDR4/DDR5 ACTIVE
        for prefix in _DRAM_ACTIVE_PREFIXES:
            if normalized.startswith(prefix):
                return self._make_dram_result(
                    model, EOLStatus.ACTIVE,
                    RiskCategory.NONE,
                    f"Micron DDR4/DDR5 {prefix} - current",
                )

        # Crucial-branded models (CT part number or MX/BX/T prefix)
        if normalized.startswith("CT"):
            return self._check_crucial(model, normalized)

        # Crucial SSD by product name (after CRU prefix stripped)
        crucial_result = self._check_crucial_ssd_name(model, normalized)
        if crucial_result:
            return crucial_result

        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="micron-product-rules",
            confidence=50,
            notes="micron-model-not-classified",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        s = _MICRON_PREFIX_RE.sub("", s)
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
            if speed_code.startswith("821") or speed_code.startswith("824"):
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="micron-product-rules",
                    confidence=65,
                    notes=f"Crucial DDR4 (speed code {speed_code}) - older generation, EOL",
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.PROCUREMENT,
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
