"""NVIDIA vendor-specific checker for datacenter/professional GPUs.

Determines EOL status by identifying the GPU architecture generation from model numbers.
No HTTP calls -- all matching is local and deterministic.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_RULES: list[dict] = [
    # === Datacenter / Tesla GPUs ===
    {
        "pattern": re.compile(r"K40|K80|TESLA\s*K", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA Kepler (2012-2014) - Tesla K-series, end of life",
    },
    {
        "pattern": re.compile(r"M40|M60|TESLA\s*M", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA Maxwell (2015) - Tesla M-series, end of life",
    },
    {
        "pattern": re.compile(
            r"(?<![A-Z])(?:P40|P100|P4\b|P6\b|TESLA\s*P|P1000|P2000|P2200|P4000|P5000|P6000|QUADRO\s*P)",
            re.IGNORECASE,
        ),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA Pascal (2016-2017) - end of life",
    },
    {
        "pattern": re.compile(r"V100", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA Volta (2017-2018) - Tesla V100, end of life",
    },
    {
        "pattern": re.compile(r"T4\b|T10\b|T1000|T400|T600", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "NVIDIA Turing (2018-2019) - still widely deployed",
    },
    {
        "pattern": re.compile(
            r"A100|A40\b|A30\b|A16\b|A10\b|A2\b"
            r"|A2000|A4000|A4500|A5000|A5500|A6000"
            r"|RTX\s*A",
            re.IGNORECASE,
        ),
        "status": EOLStatus.ACTIVE,
        "confidence": 85,
        "notes": "NVIDIA Ampere (2020-2022) - current generation",
    },
    {
        "pattern": re.compile(r"H100|H200|H20\b", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "NVIDIA Hopper (2022-2024) - current generation",
    },
    {
        "pattern": re.compile(
            r"L4\b|L40|RTX\s*[456]000\s*ADA",
            re.IGNORECASE,
        ),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "NVIDIA Ada Lovelace (2023-2024) - current generation",
    },
    {
        "pattern": re.compile(r"B100|B200|GB200", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 90,
        "notes": "NVIDIA Blackwell (2024+) - current generation",
    },
    # === Quadro legacy (Kepler/Maxwell) ===
    {
        "pattern": re.compile(r"QUADRO\s*K", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA Quadro Kepler - end of life",
    },
    {
        "pattern": re.compile(r"QUADRO\s*M", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA Quadro Maxwell - end of life",
    },
    # === Quadro RTX (Turing) ===
    {
        "pattern": re.compile(r"QUADRO\s*RTX", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "NVIDIA Quadro RTX Turing - end of life",
    },
    # === GeForce ===
    {
        "pattern": re.compile(
            r"GEFORCE\s*210|GT\s*710|GT\s*730|GTX\s*7\d\d|GTX\s*9\d\d",
            re.IGNORECASE,
        ),
        "status": EOLStatus.EOL,
        "confidence": 90,
        "notes": "NVIDIA GeForce legacy - end of life",
    },
    {
        "pattern": re.compile(r"GTX\s*10[5-8]0", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 85,
        "notes": "NVIDIA GeForce Pascal (GTX 10-series) - end of life",
    },
    {
        "pattern": re.compile(r"RTX\s*20[6-8]0", re.IGNORECASE),
        "status": EOLStatus.EOL,
        "confidence": 80,
        "notes": "NVIDIA GeForce Turing (RTX 20-series) - consumer card, EOL in datacenter",
    },
    {
        "pattern": re.compile(r"RTX\s*30[6-9]0", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 75,
        "notes": "NVIDIA GeForce Ampere (RTX 30-series) - active but consumer card",
    },
    {
        "pattern": re.compile(r"RTX\s*40[6-9]0", re.IGNORECASE),
        "status": EOLStatus.ACTIVE,
        "confidence": 80,
        "notes": "NVIDIA GeForce Ada Lovelace (RTX 40-series) - active consumer card",
    },
]


class NVIDIAChecker(BaseChecker):
    """Determines EOL status for NVIDIA datacenter and professional GPUs."""

    manufacturer_name = "NVIDIA"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)
        result = self._match_rules(model, normalized)
        if result:
            return result

        # Fallback: try original_item (e.g. "GPU:NEW:PNY NVIDIA A2")
        if model.original_item and model.original_item != model.model:
            item_cleaned = re.sub(
                r"^[A-Z /]+:(NEW|USED|REFURBISHED):",
                "",
                model.original_item.strip().upper(),
            )
            item_normalized = self._normalize(item_cleaned)
            # Also strip PNY/EVGA brand prefixes
            item_normalized = re.sub(r"^(?:PNY|EVGA)\s+", "", item_normalized)
            item_normalized = self._normalize(item_normalized)
            result = self._match_rules(model, item_normalized)
            if result:
                return result

        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="nvidia-gpu-generation",
            confidence=0,
            notes="unrecognized NVIDIA GPU model",
        )

    @staticmethod
    def _match_rules(model: HardwareModel, normalized: str) -> EOLResult | None:
        for rule in _RULES:
            if rule["pattern"].search(normalized):
                return EOLResult(
                    model=model,
                    status=rule["status"],
                    checked_at=datetime.now(),
                    source_name="nvidia-gpu-generation",
                    confidence=rule["confidence"],
                    notes=rule["notes"],
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.INFORMATIONAL,
                    date_source="none",
                )
        return None

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        if s.startswith("NVIDIA "):
            s = s[7:]
        return s.strip()
