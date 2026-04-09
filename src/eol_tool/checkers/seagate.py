"""Seagate EOL checker using capacity and product-line classification rules.

Seagate does not publish formal EOL pages.  Classification is based on
drive capacity, product line, and model number patterns.  Enterprise
performance 10K/15K SAS drives and older Exos models are considered EOL.
No HTTP calls needed.
"""

import re
from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# Regex to extract capacity from model strings like "1.2TB SEAGATE ENT - M0009"
_CAPACITY_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(TB|GB)",
    re.IGNORECASE,
)

_SEAGATE_PREFIX_RE = re.compile(
    r"^(?:SEAGATE\s+ENT(?:ERPRISE)?|SEAGATE)\s*[-–]?\s*",
    re.IGNORECASE,
)

# ── Product line patterns ────────────────────────────────────────────

# Constellation: ST*NM* or ST*NX* models — discontinued product line
_CONSTELLATION_RE = re.compile(r"\bST\d+N[MX]\d", re.IGNORECASE)

# Exos current-gen models: ST*NM*1G or later suffix patterns (X16+)
# Exos X16: ST16000NM001G, Exos X18: ST18000NM000J, X20: ST20000NM007D
_EXOS_CURRENT_RE = re.compile(
    r"\bST(?:16|18|20|22|24)\d{3}NM\d{3}[A-Z]", re.IGNORECASE,
)

# Nytro SSD models
_NYTRO_RE = re.compile(r"\bNYTRO\b", re.IGNORECASE)
# Nytro current generation: 3000/5000 series
_NYTRO_CURRENT_RE = re.compile(r"\bNYTRO\s*(?:3[3-9]|[4-9]\d|5\d)", re.IGNORECASE)

# HGST models: legacy (WD acquired HGST)
_HGST_RE = re.compile(r"\bHGST\b|^HUS\d|^HUH\d|^HUSMM|^HGST", re.IGNORECASE)

# Enterprise Performance 10K/15K SAS (legacy)
_ENT_PERF_RE = re.compile(r"\b(?:10K|15K|10000|15000)\b", re.IGNORECASE)

# Enterprise Capacity older models: ST*NM* without the current-gen suffix
# These are pre-Exos Seagate enterprise drives
_ENT_CAPACITY_OLD_RE = re.compile(
    r"\bST(?:1|2|3|4|5|6|8)\d{3,4}NM\d{3}[0-9]", re.IGNORECASE,
)

# BarraCuda Desktop drives: ST*DM* models
_BARRACUDA_RE = re.compile(r"\bST\d+DM\d", re.IGNORECASE)

# IronWolf NAS drives: ST*VN* or ST*NT* (IronWolf Pro) models
_IRONWOLF_RE = re.compile(r"\bST\d+(?:VN|NT)\d", re.IGNORECASE)

# ── Keyword patterns for serial-fragment models ────────────────────
_ENT_KEYWORD_RE = re.compile(r"\bENT(?:ERPRISE)?\b|\bEXOS\b", re.IGNORECASE)
_NAS_KEYWORD_RE = re.compile(r"\bNAS\b|\bIRONWOLF\b", re.IGNORECASE)
_DESKTOP_KEYWORD_RE = re.compile(r"\bDESKTOP\b|\bBARRACUDA\b|\bTERASCALE\b", re.IGNORECASE)

# Bare Seagate: just the brand name optionally followed by a serial fragment
_BARE_SEAGATE_RE = re.compile(
    r"^SEAGATE\s*(?:-\s*[A-Z0-9]+)?$", re.IGNORECASE,
)


def _extract_capacity_tb(model_str: str) -> float | None:
    """Extract drive capacity in TB from a model string."""
    m = _CAPACITY_RE.search(model_str)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "GB":
        value /= 1000
    return value


def _classify_by_capacity(
    capacity_tb: float,
) -> tuple[EOLStatus, RiskCategory, str]:
    """Classify a Seagate enterprise HDD by capacity."""
    if capacity_tb < 4.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            f"Seagate enterprise {capacity_tb:.1f}TB - legacy small capacity, EOL",
        )
    if capacity_tb < 8.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            f"Seagate enterprise {capacity_tb:.1f}TB - older generation, EOL",
        )
    if capacity_tb < 10.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Exos X10 10TB - EOL",
        )
    if capacity_tb < 12.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Exos X12 12TB - EOL",
        )
    if capacity_tb < 14.1:
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Exos X14 14TB - EOL, replaced by X16+",
        )
    if capacity_tb < 16.1:
        return (
            EOLStatus.ACTIVE,
            RiskCategory.INFORMATIONAL,
            "Seagate Exos X16 16TB - active but aging",
        )
    return (
        EOLStatus.ACTIVE,
        RiskCategory.NONE,
        f"Seagate Exos {capacity_tb:.0f}TB - current generation",
    )


def _classify_by_product_line(
    raw: str,
) -> tuple[EOLStatus, RiskCategory, str, EOLReason, int] | None:
    """Classify a Seagate/HGST model by product line patterns.

    Returns (status, risk, notes, eol_reason, confidence) or None.
    """
    # HGST models: all legacy/EOL (WD acquired HGST)
    if _HGST_RE.search(raw):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "HGST legacy model (acquired by WD) - EOL",
            EOLReason.VENDOR_ACQUIRED,
            70,
        )

    # Enterprise Performance 10K/15K SAS: all EOL
    if _ENT_PERF_RE.search(raw):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Enterprise Performance 10K/15K - EOL",
            EOLReason.PRODUCT_DISCONTINUED,
            70,
        )

    # Nytro SSDs
    if _NYTRO_RE.search(raw):
        if _NYTRO_CURRENT_RE.search(raw):
            return (
                EOLStatus.ACTIVE,
                RiskCategory.NONE,
                "Seagate Nytro current generation - active",
                EOLReason.NONE,
                60,
            )
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Nytro previous generation - EOL",
            EOLReason.PRODUCT_DISCONTINUED,
            60,
        )

    # Exos current generation (16TB+, new suffix patterns)
    if _EXOS_CURRENT_RE.search(raw):
        return (
            EOLStatus.ACTIVE,
            RiskCategory.NONE,
            "Seagate Exos current generation - active",
            EOLReason.NONE,
            65,
        )

    # Older Enterprise Capacity / pre-Exos Constellation models
    if _ENT_CAPACITY_OLD_RE.search(raw):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Enterprise Capacity older generation - EOL",
            EOLReason.PRODUCT_DISCONTINUED,
            65,
        )

    # Constellation models (ST*NM*, ST*NX*) not caught above
    if _CONSTELLATION_RE.search(raw):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Constellation (discontinued product line) - EOL",
            EOLReason.PRODUCT_DISCONTINUED,
            70,
        )

    # BarraCuda Desktop (ST*DM* models) — consumer drives, EOL for datacenter
    if _BARRACUDA_RE.search(raw):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate BarraCuda Desktop drive - consumer, EOL for datacenter use",
            EOLReason.PRODUCT_DISCONTINUED,
            60,
        )

    # IronWolf NAS (ST*VN* models)
    if _IRONWOLF_RE.search(raw):
        return (
            EOLStatus.ACTIVE,
            RiskCategory.INFORMATIONAL,
            "Seagate IronWolf NAS drive - active product line",
            EOLReason.NONE,
            60,
        )

    return None


def _classify_by_keyword(
    text: str,
) -> tuple[EOLStatus, RiskCategory, str, EOLReason, int] | None:
    """Classify Seagate drives by product-line keywords in any available text.

    Used for serial-fragment models where the actual model number is missing
    but product-line keywords (ENT, NAS, DESKTOP) survive in the original text.
    """
    if _ENT_KEYWORD_RE.search(text):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Enterprise drive - model number not available, assumed EOL due to age",
            EOLReason.PRODUCT_DISCONTINUED,
            50,
        )
    if _NAS_KEYWORD_RE.search(text):
        return (
            EOLStatus.ACTIVE,
            RiskCategory.INFORMATIONAL,
            "Seagate NAS/IronWolf drive - model number not available, product line active",
            EOLReason.NONE,
            50,
        )
    if _DESKTOP_KEYWORD_RE.search(text):
        return (
            EOLStatus.EOL,
            RiskCategory.PROCUREMENT,
            "Seagate Desktop/BarraCuda drive - consumer, EOL for datacenter use",
            EOLReason.PRODUCT_DISCONTINUED,
            50,
        )
    return None


class SeagateChecker(BaseChecker):
    """Seagate EOL checker using capacity and product-line classification."""

    manufacturer_name = "Seagate"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        # Capacity may be in original_item (before normalization strips it)
        raw = model.original_item or model.model

        # Try capacity-based classification first (highest confidence)
        capacity_tb = _extract_capacity_tb(raw)
        if capacity_tb is not None:
            status, risk, notes = _classify_by_capacity(capacity_tb)
            return EOLResult(
                model=model,
                status=status,
                checked_at=datetime.now(),
                source_name="seagate-capacity-rules",
                confidence=65,
                notes=notes,
                eol_reason=EOLReason.PRODUCT_DISCONTINUED
                if status == EOLStatus.EOL
                else EOLReason.NONE,
                risk_category=risk,
                date_source="none",
            )

        # Try product-line classification (model number patterns)
        pl = _classify_by_product_line(raw)
        if pl is not None:
            status, risk, notes, eol_reason, confidence = pl
            return EOLResult(
                model=model,
                status=status,
                checked_at=datetime.now(),
                source_name="seagate-product-line-rules",
                confidence=confidence,
                notes=notes,
                eol_reason=eol_reason,
                risk_category=risk,
                date_source="none",
            )

        # Try keyword-based classification from all available text
        # (original_item may contain ENT/NAS/DESKTOP stripped during normalization)
        all_text = f"{model.model} {model.original_item or ''}"
        kw = _classify_by_keyword(all_text)
        if kw is not None:
            status, risk, notes, eol_reason, confidence = kw
            return EOLResult(
                model=model,
                status=status,
                checked_at=datetime.now(),
                source_name="seagate-product-line-rules",
                confidence=confidence,
                notes=notes,
                eol_reason=eol_reason,
                risk_category=risk,
                date_source="none",
            )

        # Bare Seagate with serial fragment: no model info, assume EOL due to age
        if _BARE_SEAGATE_RE.match(model.model.strip()):
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="seagate-product-line-rules",
                confidence=30,
                notes="Seagate drive - insufficient model info, assumed EOL due to age",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                risk_category=RiskCategory.PROCUREMENT,
                date_source="none",
            )

        # Cannot classify — return UNKNOWN
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="seagate-capacity-rules",
            confidence=50,
            notes="seagate-model-not-classified",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.PROCUREMENT,
        )
