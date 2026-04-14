"""Hitachi (HGST) EOL checker.

Hitachi Global Storage Technologies (HGST) was acquired by Western Digital
in 2012. All HGST drives are legacy and discontinued.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# HGST model prefixes
_HGST_RE = re.compile(
    r"^(?:HUS|HUH|H2T|0F\d|HDS|HUA|HDP|HDT|HTE|HMS|HCC)",
    re.IGNORECASE,
)


class HitachiChecker(BaseChecker):
    """Hitachi/HGST EOL checker — all products discontinued (WD acquisition)."""

    manufacturer_name = "Hitachi"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        if _HGST_RE.search(normalized):
            # Specific HGST product identified
            notes = "HGST acquired by Western Digital in 2012; product lines discontinued"
            if normalized.startswith("HUS"):
                notes = "HGST Ultrastar SAS - " + notes
            elif normalized.startswith("HUH"):
                notes = "HGST Ultrastar Helium - " + notes
            elif normalized.startswith(("HDS", "HDP", "HDT")):
                notes = "HGST Deskstar - " + notes
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="hitachi-hgst-lookup",
                confidence=85,
                notes=notes,
                eol_reason=EOLReason.VENDOR_ACQUIRED,
                risk_category=RiskCategory.PROCUREMENT,
                date_source="none",
            )

        # Default: all Hitachi/HGST products are EOL
        return EOLResult(
            model=model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="hitachi-hgst-lookup",
            confidence=80,
            notes="HGST acquired by Western Digital in 2012; product lines discontinued",
            eol_reason=EOLReason.VENDOR_ACQUIRED,
            risk_category=RiskCategory.PROCUREMENT,
            date_source="none",
        )

    @staticmethod
    def _normalize(model_str: str) -> str:
        s = model_str.strip().upper()
        for prefix in ("HITACHI ", "HGST "):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s.strip()
