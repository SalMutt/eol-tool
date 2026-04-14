"""KIOXIA EOL checker for enterprise SSDs.

KIOXIA was spun off from Toshiba Memory in 2019.  Products are classified
by series and generation number extracted from the model string.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Maximum generation number considered EOL for each series.
# Generations at or below this threshold are EOL; above are active.
_EOL_GEN_THRESHOLD: dict[str, int] = {
    "CD": 5,
    "CM": 5,
    "PM": 5,
    "XD": 5,
    "XG": 6,
    "BG": 4,
    "HK": 5,
}

# Pattern: [K]<series two letters><generation digit>  e.g. KCD51LUG960G or CD6-R
_MODEL_RE = re.compile(r"(?:^|(?<=K))([A-Z]{2})(\d)", re.IGNORECASE)


class KIOXIAChecker(BaseChecker):
    """KIOXIA EOL checker for enterprise SSDs."""

    manufacturer_name = "KIOXIA"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)
        upper = normalized.upper()

        if "EXCERIA" in upper:
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="kioxia-product-rules",
                confidence=75,
                notes="KIOXIA EXCERIA - current consumer NVMe SSD",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.PROCUREMENT,
            )

        m = _MODEL_RE.search(upper)
        if m:
            series = m.group(1).upper()
            gen = int(m.group(2))
            threshold = _EOL_GEN_THRESHOLD.get(series)
            if threshold is not None:
                if gen <= threshold:
                    return EOLResult(
                        model=model,
                        status=EOLStatus.EOL,
                        checked_at=datetime.now(),
                        source_name="kioxia-product-rules",
                        confidence=85,
                        notes=f"KIOXIA {series}{gen} - legacy generation, EOL",
                        eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                        risk_category=RiskCategory.PROCUREMENT,
                    )
                return EOLResult(
                    model=model,
                    status=EOLStatus.ACTIVE,
                    checked_at=datetime.now(),
                    source_name="kioxia-product-rules",
                    confidence=75,
                    notes=f"KIOXIA {series}{gen} - current generation",
                    eol_reason=EOLReason.NONE,
                    risk_category=RiskCategory.PROCUREMENT,
                )

        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="kioxia-product-rules",
            confidence=40,
            notes="KIOXIA model not specifically classified",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.PROCUREMENT,
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip()
        upper = s.upper()
        for prefix in ("KIOXIA ", "TOSHIBA "):
            if upper.startswith(prefix):
                s = s[len(prefix):].strip()
                break
        return s
