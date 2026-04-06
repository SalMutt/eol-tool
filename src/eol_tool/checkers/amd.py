"""AMD vendor-specific checker for EPYC, Ryzen, and Threadripper processors.

Determines EOL status by identifying the processor generation from model numbers.
No HTTP calls — all matching is local and deterministic.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_GENERATIONS = {
    (7, 1): {
        "status": EOLStatus.EOL,
        "eol_reason": EOLReason.MANUFACTURER_DECLARED,
        "risk_category": RiskCategory.SUPPORT,
        "confidence": 85,
        "notes": "EPYC 7001 Naples - different socket SP3, no longer manufactured",
    },
    (7, 2): {
        "status": EOLStatus.EOL,
        "eol_reason": EOLReason.MANUFACTURER_DECLARED,
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
        "patterns": ["5500", "5600G", "5700G", "5800X", "5900X", "5950X"],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.INFORMATIONAL,
        "confidence": 85,
        "notes": "Ryzen 5000 series Zen 3 AM4 - current generation AM4",
    },
    {
        "patterns": ["7600X", "7900X", "7950X", "7960X"],
        "status": EOLStatus.ACTIVE,
        "eol_reason": EOLReason.NONE,
        "risk_category": RiskCategory.NONE,
        "confidence": 90,
        "notes": "Ryzen 7000 series Zen 4 AM5 - current generation",
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
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="amd-epyc-generation",
            confidence=0,
            notes="not-an-epyc-model-or-unknown-generation",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        if s.startswith("AMD "):
            s = s[4:]
        if s.endswith(" CPU"):
            s = s[:-4]
        return s.strip()

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
