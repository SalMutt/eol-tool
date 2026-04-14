"""AMD vendor-specific checker for EPYC, Ryzen, and Threadripper processors.

Determines EOL status by identifying the processor generation from model numbers
and OPN ordering codes (100-*, PS7*, PSE-*).
No HTTP calls — all matching is local and deterministic.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── OPN ordering code boundary: numbers below this are Rome (Zen 2) or older
_OPN_MILAN_BOUNDARY = 80  # 100-000000080 = EPYC 7513 (Milan, first Zen 3)

_GENERATIONS = {
    (7, 1): {
        "status": EOLStatus.EOL,
        "eol_reason": EOLReason.TECHNOLOGY_GENERATION,
        "risk_category": RiskCategory.SUPPORT,
        "confidence": 85,
        "notes": "EPYC 7001 Naples - different socket SP3, no longer manufactured",
    },
    (7, 2): {
        "status": EOLStatus.EOL,
        "eol_reason": EOLReason.TECHNOLOGY_GENERATION,
        "risk_category": RiskCategory.INFORMATIONAL,
        "confidence": 85,
        "notes": "EPYC 7002 Rome - SP3 socket, superseded by Milan and Genoa",
    },
    (7, 3): {
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.INFORMATIONAL,
        "confidence": 85,
        "notes": "EPYC 7003 Milan - SP3 socket, current generation but superseded by Genoa",
    },
    (9, 4): {
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.NONE,
        "confidence": 90,
        "notes": "EPYC 9004 Genoa - SP5 socket, current generation",
    },
    (9, 5): {
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.NONE,
        "confidence": 90,
        "notes": "EPYC 9005 Turin - SP5 socket, latest generation Zen 5",
    },
}

# Siena matches series 4 with last digit 4 or 5
_SIENA = {
    "status": EOLStatus.ACTIVE,
    "eol_reason": EOLReason.NONE,
    "risk_category": RiskCategory.NONE,
    "confidence": 90,
    "notes": "EPYC 4004 Siena - SP6 socket, current edge/embedded generation",
}


_RYZEN_RULES = [
    {
        "patterns": ["3900X", "3950X"],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.INFORMATIONAL,
        "confidence": 85,
        "notes": "Ryzen 3000 series Zen 2 AM4 - active but aging platform",
    },
    {
        "patterns": [
            "5500", "5600G", "5600X", "5700G", "5800X", "5800X3D",
            "5900X", "5950X",
        ],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.INFORMATIONAL,
        "confidence": 85,
        "notes": "Ryzen 5000 series Zen 3 AM4 - current generation AM4",
    },
    {
        "patterns": ["7600X", "7900X", "7950X", "7960X", "7800X3D"],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.NONE,
        "confidence": 90,
        "notes": "Ryzen 7000 series Zen 4 AM5 - current generation",
    },
    {
        "patterns": ["9700X", "9900X", "9950X"],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.NONE,
        "confidence": 90,
        "notes": "Ryzen 9000 series Zen 5 AM5 - latest generation",
    },
    {
        "patterns": ["7965WX"],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.NONE,
        "confidence": 90,
        "notes": "Threadripper PRO 7000 - current generation workstation",
    },
]


class AMDChecker(BaseChecker):
    """Determines EOL status for AMD EPYC, Ryzen, and Threadripper processors."""

    manufacturer_name = "AMD"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # ── OPN ordering code classification (before human-readable names) ──
        opn_result = self._detect_opn(model, normalized)
        if opn_result:
            return opn_result

        # Try the model string first, then the original_item as fallback
        result = self._try_name_match(model, normalized)
        if result:
            return result

        # Fallback: try extracting model name from original_item
        if model.original_item and model.original_item != model.model:
            item_normalized = self._normalize(
                re.sub(
                    r"^[A-Z /]+:(NEW|USED|REFURBISHED):",
                    "",
                    model.original_item.strip().upper(),
                )
            )
            result = self._try_name_match(model, item_normalized)
            if result:
                return result

        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="amd-epyc-generation",
            confidence=0,
            notes="not-an-epyc-model-or-unknown-generation",
        )

    def _try_name_match(
        self, model: HardwareModel, normalized: str
    ) -> EOLResult | None:
        """Try to classify from EPYC/Ryzen human-readable name patterns."""
        gen = self._detect_generation(normalized)
        if gen:
            eol_date = gen.get("eol_date")
            return EOLResult(
                model=model,
                status=gen["status"],
                checked_at=datetime.now(),
                source_name="amd-epyc-generation",
                confidence=gen["confidence"],
                notes=gen["notes"],
                eol_reason=gen["eol_reason"],
                risk_category=gen["risk_category"],
                eol_date=eol_date,
                date_source="none",
            )
        ryzen = self._detect_ryzen(normalized)
        if ryzen:
            return EOLResult(
                model=model,
                status=ryzen["status"],
                checked_at=datetime.now(),
                source_name="amd-ryzen-generation",
                confidence=ryzen["confidence"],
                notes=ryzen["notes"],
                eol_reason=ryzen["eol_reason"],
                risk_category=ryzen["risk_category"],
            )
        return None

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        if s.startswith("AMD "):
            s = s[4:]
        if s.endswith(" CPU"):
            s = s[:-4]
        return s.strip()

    @staticmethod
    def _detect_opn(model: HardwareModel, normalized: str) -> EOLResult | None:
        """Classify AMD OPN ordering codes (100-*, PS7*, PSE-*)."""
        # PS7* = EPYC 7001 Naples (Zen 1) → EOL
        if normalized.startswith("PS7"):
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="amd-opn-ordering-code",
                confidence=80,
                notes="EPYC 7001 Naples (Zen 1) ordering code — EOL",
                eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                risk_category=RiskCategory.SUPPORT,
            )
        # PSE-* = EPYC 7002 Rome (Zen 2) → EOL
        if normalized.startswith("PSE"):
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="amd-opn-ordering-code",
                confidence=80,
                notes="EPYC 7002 Rome (Zen 2) ordering code — EOL",
                eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                risk_category=RiskCategory.INFORMATIONAL,
            )
        # 100-XXXXXXXXXXX = AMD OPN (both 100-000000XXX and 100-100000XXX)
        opn_match = re.match(r"^(?:AMD-?)?100[\-.](\d+)", normalized)
        if not opn_match:
            return None
        raw_digits = opn_match.group(1)
        number = int(raw_digits.lstrip("0") or "0")
        if number < _OPN_MILAN_BOUNDARY:
            # Rome (Zen 2) or older → EOL
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="amd-opn-ordering-code",
                confidence=70,
                notes=f"AMD OPN 100-...{number:03d} — Rome/Zen 2 or older, EOL",
                eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                risk_category=RiskCategory.INFORMATIONAL,
            )
        # Milan (Zen 3) or newer → active
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="amd-opn-ordering-code",
            confidence=70,
            notes=f"AMD OPN 100-...{number:03d} — Milan/Zen 3 or newer, active",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
        )

    @staticmethod
    def _detect_generation(normalized: str) -> dict | None:
        # Extract model token from "EPYC <model>" or bare model number
        epyc_match = re.search(r"EPYC\s+(\S+)", normalized)
        if epyc_match:
            token = epyc_match.group(1)
        elif re.match(r"^[479]\d[\dA-Z]*\d[A-Z]*$", normalized):
            token = normalized
        else:
            return None

        digits = [c for c in token if c.isdigit()]
        if len(digits) < 3:
            return None

        series = int(digits[0])
        gen_digit = int(digits[-1])

        # Siena: series 4 with last digit 4 or 5
        if series == 4 and gen_digit in (4, 5):
            return _SIENA

        return _GENERATIONS.get((series, gen_digit))

    @staticmethod
    def _normalize_ryzen(normalized: str) -> str:
        """Further normalize for Ryzen/Threadripper matching.

        Strips product-line names, 'PRO', and the leading tier digit + space.
        """
        s = normalized
        for keyword in ("THREADRIPPER", "RYZEN"):
            s = s.replace(keyword, "")
        s = s.replace("PRO", "")
        s = re.sub(r"\s+", " ", s).strip()
        # Strip leading tier digit + space (e.g. "5 " from "5 5500")
        if len(s) >= 2 and s[0].isdigit() and s[1] == " ":
            s = s[2:].strip()
        return s

    @staticmethod
    def _detect_ryzen(normalized: str) -> dict | None:
        token = AMDChecker._normalize_ryzen(normalized)
        if not token:
            return None
        for rule in _RYZEN_RULES:
            for pattern in rule["patterns"]:
                if pattern in token:
                    return rule
        return None
