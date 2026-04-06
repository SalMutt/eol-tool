"""Supermicro EOL checker using generation-based classification rules.

Supermicro does not publish specific EOL dates on their website.
The archive page (supermicro.com/products/motherboard/archive/) only
indicates discontinued status, not a date. Individual product pages
(e.g. X10DRI) show "Discontinued SKU (EOL)" but no date.
Dates can only come from Supermicro's direct customer communications
or third-party databases (e.g. last-time-buy notices sent to partners).

This checker returns EOL status based on board generation
(X9/X10/X11/X12/X13/X14/H11/H12/H13/H14) but eol_date will be None
for all Supermicro products.
"""

import logging
import re
from datetime import date, datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

logger = logging.getLogger(__name__)

# Board generation mapping: prefix -> (status, notes)
_BOARD_GENERATIONS: dict[str, dict] = {
    "X9": {
        "status": EOLStatus.EOL,
        "notes": "X9 generation - Ivy Bridge era, end of life",
    },
    "X10": {
        "status": EOLStatus.EOL,
        "notes": "X10 generation - Haswell/Broadwell era, end of life",
    },
    "X11": {
        "status": EOLStatus.EOL_ANNOUNCED,
        "notes": "X11 generation - Skylake era, nearing end of life",
    },
    "X12": {
        "status": EOLStatus.ACTIVE,
        "notes": "X12 generation - Ice Lake era, current",
    },
    "X13": {
        "status": EOLStatus.ACTIVE,
        "notes": "X13 generation - Sapphire Rapids era, current",
    },
    "X14": {
        "status": EOLStatus.ACTIVE,
        "notes": "X14 generation - current generation",
    },
    "H11": {
        "status": EOLStatus.EOL,
        "notes": "H11 generation - AMD EPYC 7001 Naples era, end of life",
    },
    "H12": {
        "status": EOLStatus.EOL_ANNOUNCED,
        "notes": "H12 generation - AMD EPYC 7002/7003 Rome/Milan era, nearing end of life",
    },
    "H13": {
        "status": EOLStatus.ACTIVE,
        "notes": "H13 generation - AMD EPYC 9004 Genoa era, current generation",
    },
    "H14": {
        "status": EOLStatus.ACTIVE,
        "notes": "H14 generation - current generation",
    },
}

# Heatsink SNK-P00xx number range -> board generation
_HEATSINK_GENERATIONS = [
    (40, 49, "X10"),  # LGA1150/LGA2011 - Haswell/Broadwell
    (60, 69, "X11"),  # LGA3647 - Skylake
    (70, 79, "X12"),  # LGA4189 - Ice Lake
    (80, 89, "X13"),  # LGA4677 - Sapphire Rapids
]

# SYS-XXYZ: last digit of the 4-digit number encodes the era
_SYSTEM_ERA_DIGIT = {
    "7": "X9",
    "8": "X10",
    "9": "X11",
}

# Known non-Supermicro model prefixes that appear in Supermicro inventory
_NON_SUPERMICRO_PREFIXES = ("MX", "MIC3", "JNP-", "VCG", "TOS")
_NON_SUPERMICRO_EXACT = frozenset({"S8016AGM2NR"})

# Static chassis classification: prefix -> properties
_STATIC_CHASSIS: dict[str, dict] = {
    "CSE-113": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "1U chassis, product discontinued",
    },
    "CSE-213": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "2U chassis, product discontinued",
    },
    "CSE-512": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "chassis, product discontinued",
    },
    "CSE-813": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "1U chassis, product discontinued",
    },
    "CSE-815": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "1U chassis, product discontinued",
    },
    "CSE-825": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "2U chassis, product discontinued",
    },
    "CSE-826": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "2U chassis, product discontinued",
    },
    "CSE-LA26": {
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "reason": EOLReason.NONE,
        "risk": RiskCategory.NONE,
        "notes": "current generation chassis",
    },
}

# Static addon card/riser classification: prefix -> properties
_STATIC_ADDONS: dict[str, dict] = {
    "AOC-SAS2LP-H8IR": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "SAS2 controller, product discontinued",
    },
    "AOC-STGN-I2S": {
        "status": EOLStatus.EOL,
        "confidence": 75,
        "reason": EOLReason.PRODUCT_DISCONTINUED,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "10G SFP+ NIC, product discontinued",
    },
    "AOC-S40G-I2Q": {
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "reason": EOLReason.NONE,
        "risk": RiskCategory.NONE,
        "notes": "40G NIC, current product",
    },
    "AOC-CGP-I2M": {
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "reason": EOLReason.NONE,
        "risk": RiskCategory.NONE,
        "notes": "management NIC, current product",
    },
    "RSC-W-66G4": {
        "status": EOLStatus.UNKNOWN,
        "confidence": 40,
        "reason": EOLReason.NONE,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "riser-card-follows-board-lifecycle",
    },
}

# Static memory classification: substring match -> properties
_STATIC_MEMORY: dict[str, dict] = {
    "MEM-VR416LD-EU26": {
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "reason": EOLReason.NONE,
        "risk": RiskCategory.NONE,
        "notes": "Supermicro VLP DDR4 memory, current product",
    },
}


def _match_prefix(table: dict[str, dict], normalized: str) -> dict | None:
    """Return the first entry whose key is a prefix of normalized."""
    for key in sorted(table, key=len, reverse=True):
        if normalized.startswith(key):
            return table[key]
    return None


def _match_substring(table: dict[str, dict], normalized: str) -> dict | None:
    """Return the first entry whose key appears in normalized."""
    for key in table:
        if key in normalized:
            return table[key]
    return None


class SupermicroChecker(BaseChecker):
    """Supermicro EOL checker using generation-based classification rules."""

    manufacturer_name = "Supermicro"
    rate_limit = 3
    priority = 20

    source_name = "supermicro-eol"

    def __init__(self) -> None:
        super().__init__()
        logger.info(
            "Supermicro does not publish EOL dates; using generation rules only"
        )

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # Reject known non-Supermicro models misclassified in inventory
        if (
            normalized.startswith(_NON_SUPERMICRO_PREFIXES)
            or normalized in _NON_SUPERMICRO_EXACT
        ):
            return self._make_generation_result(
                model,
                EOLStatus.NOT_FOUND,
                40,
                EOLReason.NONE,
                RiskCategory.NONE,
                "not-supermicro-product",
            )

        return self._static_classify(model, normalized)

    # -- Static generation fallback -----------------------------------

    def _static_classify(
        self, model: HardwareModel, normalized: str
    ) -> EOLResult:
        """Classify using generation rules only (no dates, date_source='none')."""
        # Board generation prefix (X9/X10/X11/X12/X13/X14/H11-H14)
        gen = self._detect_board_generation(normalized)
        if gen:
            risk = self._risk_for_category(model.category)
            return self._make_generation_result(
                model,
                gen["status"],
                65,
                EOLReason.TECHNOLOGY_GENERATION,
                risk,
                gen["notes"],
                eol_date=gen.get("eol_date"),
            )

        # Systems: extract generation from SYS-*/AS-* model number
        gen = self._detect_system_generation(normalized)
        if gen:
            return self._make_generation_result(
                model,
                gen["status"],
                65,
                EOLReason.TECHNOLOGY_GENERATION,
                RiskCategory.SUPPORT,
                gen["notes"],
                eol_date=gen.get("eol_date"),
            )

        # Heatsinks: map SNK-P00xx to board generation
        gen = self._detect_heatsink_generation(normalized)
        if gen:
            return self._make_generation_result(
                model,
                gen["status"],
                65,
                EOLReason.TECHNOLOGY_GENERATION,
                RiskCategory.PROCUREMENT,
                gen["notes"],
                eol_date=gen.get("eol_date"),
            )

        # Chassis -- check static classification, then fall back to UNKNOWN
        if normalized.startswith("CSE-"):
            entry = _match_prefix(_STATIC_CHASSIS, normalized)
            if entry:
                return self._make_generation_result(
                    model,
                    entry["status"],
                    entry["confidence"],
                    entry["reason"],
                    entry["risk"],
                    entry["notes"],
                )
            return self._make_generation_result(
                model,
                EOLStatus.UNKNOWN,
                40,
                EOLReason.NONE,
                RiskCategory.PROCUREMENT,
                "chassis-no-generation-indicator",
            )

        # Add-on cards, modules, and risers
        if normalized.startswith(("AOC-", "AOM-", "RSC-")):
            entry = _match_prefix(_STATIC_ADDONS, normalized)
            if entry:
                return self._make_generation_result(
                    model,
                    entry["status"],
                    entry["confidence"],
                    entry["reason"],
                    entry["risk"],
                    entry["notes"],
                )
            return self._make_generation_result(
                model,
                EOLStatus.UNKNOWN,
                40,
                EOLReason.NONE,
                RiskCategory.PROCUREMENT,
                "addon-card-no-generation-indicator",
            )

        # Supermicro VLP memory
        entry = _match_substring(_STATIC_MEMORY, normalized)
        if entry:
            return self._make_generation_result(
                model,
                entry["status"],
                entry["confidence"],
                entry["reason"],
                entry["risk"],
                entry["notes"],
            )

        # Not a recognized Supermicro model pattern
        return self._make_generation_result(
            model,
            EOLStatus.NOT_FOUND,
            40,
            EOLReason.NONE,
            RiskCategory.NONE,
            "unrecognized-supermicro-model",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        if s.startswith("OPTICS:"):
            s = s[7:]
        # Strip trailing quantity suffix like " - 2"
        s = re.sub(r"\s+-\s+\d+$", "", s)
        # Strip W/xxx suffixes (W/HS, W/E31241, etc.)
        s = re.sub(r"\s+W/.*$", "", s)
        # Strip description suffixes (DUAL PORT 40G NIC, etc.)
        s = re.sub(r"\s+(?:DUAL|QUAD|SINGLE)\s+.*$", "", s)
        # For non-standard model strings, extract embedded board prefix
        known_starts = (
            "X", "H1", "CSE", "SYS", "AS-", "AOC", "AOM", "SNK", "RSC", "SPC", "S80",
        )
        if not any(s.startswith(p) for p in known_starts):
            board_match = re.search(r"\b(X\d{1,2}[A-Z])", s)
            if board_match:
                s = board_match.group(1)
        return s.strip()

    @staticmethod
    def _detect_board_generation(normalized: str) -> dict | None:
        # SPC621 -> C621 chipset = Skylake-SP era = X11 equivalent
        if normalized.startswith("SPC621"):
            return _BOARD_GENERATIONS["X11"]
        for prefix in sorted(_BOARD_GENERATIONS, key=len, reverse=True):
            if normalized.startswith(prefix):
                return _BOARD_GENERATIONS[prefix]
        return None

    @staticmethod
    def _detect_system_generation(normalized: str) -> dict | None:
        # SYS-XXYY: last digit of XXYY indicates era (7=X9, 8=X10, 9=X11)
        sys_match = re.match(r"SYS-\d{3}(\d)", normalized)
        if sys_match:
            era_digit = sys_match.group(1)
            gen_prefix = _SYSTEM_ERA_DIGIT.get(era_digit)
            if gen_prefix:
                return _BOARD_GENERATIONS[gen_prefix]
        # AS-* AMD SuperServer -- H11 era (EPYC 7001 Naples)
        if normalized.startswith("AS-"):
            return _BOARD_GENERATIONS["H11"]
        return None

    @staticmethod
    def _detect_heatsink_generation(normalized: str) -> dict | None:
        match = re.match(r"SNK-P00(\d{2})", normalized)
        if not match:
            return None
        num = int(match.group(1))
        for lo, hi, gen_prefix in _HEATSINK_GENERATIONS:
            if lo <= num <= hi:
                return _BOARD_GENERATIONS[gen_prefix]
        return None

    @staticmethod
    def _risk_for_category(category: str) -> RiskCategory:
        cat = category.lower()
        if cat in ("server-board", "server", "server-barebone"):
            return RiskCategory.SUPPORT
        return RiskCategory.PROCUREMENT

    @staticmethod
    def _make_generation_result(
        model: HardwareModel,
        status: EOLStatus,
        confidence: int,
        eol_reason: EOLReason,
        risk_category: RiskCategory,
        notes: str,
        eol_date: date | None = None,
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="supermicro-generation",
            confidence=confidence,
            notes=notes,
            eol_reason=eol_reason,
            risk_category=risk_category,
            eol_date=eol_date,
            date_source="none",
        )
