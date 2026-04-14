"""Mellanox vendor-specific checker for ConnectX and BlueField adapters.

Determines EOL status by identifying the ConnectX/BlueField generation from model numbers.
Mellanox was acquired by NVIDIA in 2020.
No HTTP calls — all matching is local and deterministic.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    {
        "pattern": re.compile(r"^(?:MHQH|MHJH|MNPH)", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 90,
        "notes": "Mellanox ConnectX-2 (2009) - 10/40GbE, end of life",
    },
    {
        "pattern": re.compile(r"^MCX3", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "Mellanox ConnectX-3/3 Pro (2012) - 10/40/56GbE, end of life",
    },
    {
        "pattern": re.compile(r"^MCX4", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "Mellanox ConnectX-4/4 Lx (2015) - 25/50/100GbE, still supported",
    },
    {
        "pattern": re.compile(r"^MCX5", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 85,
        "notes": "Mellanox ConnectX-5 (2017) - 25/50/100GbE, active",
    },
    {
        "pattern": re.compile(r"^MCX6", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "Mellanox ConnectX-6 (2019) - 25/50/100/200GbE, active",
    },
    {
        "pattern": re.compile(r"^MCX7", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "Mellanox ConnectX-7 (2022) - 100/200/400GbE, active",
    },
    {
        "pattern": re.compile(r"^MBF2", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 85,
        "notes": "NVIDIA BlueField-2 DPU - active",
    },
    {
        "pattern": re.compile(r"^MBF3", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "NVIDIA BlueField-3 DPU - active",
    },
]


class MellanoxChecker(BaseChecker):
    """Determines EOL status for Mellanox ConnectX and BlueField adapters."""

    manufacturer_name = "Mellanox"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)
        for rule in _RULES:
            if rule["pattern"].search(normalized):
                return EOLResult(
                    model=model,
                    status=rule["status"],
                    checked_at=datetime.now(),
                    source_name="mellanox-connectx-generation",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.SECURITY,
                    date_source="none",
                )
        # Default: unrecognized Mellanox model → EOL with low confidence
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="mellanox-connectx-generation",
            confidence=40,
            notes="unrecognized Mellanox model - assumed EOL",
            eol_reason=EOLReason.TECHNOLOGY_GENERATION,
            risk_category=RiskCategory.SECURITY,
            date_source="none",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        for prefix in ("MELLANOX ", "NVIDIA "):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s.strip()
