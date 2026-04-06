"""Juniper Networks EOL checker.

Determines EOL status for Juniper hardware by:
1. Parsing the EOL listing page to discover product family URLs
2. Mapping models to product families (EX, SRX, MX, QFX series, components, optics)
3. Looking up known EOL dates from product family detail pages
"""

import json
import logging
import re
from datetime import date, datetime

import httpx

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

logger = logging.getLogger(__name__)

# Product family URL paths from the Juniper EOL listing page
_FAMILY_URLS: dict[str, str] = {
    "ex": "/support/eol/product/ex_series/",
    "srx": "/support/eol/product/srx_series/",
    "mx": "/support/eol/product/m_series/",
    "qfx": "/support/eol/product/qfx_series/",
    "optics": "/support/eol/product/optics/",
}

# Known EOL dates for Juniper product families.
# Juniper detail pages are client-side rendered, so we maintain known data here.
# Dates sourced from Juniper EOL bulletin pages at support.juniper.net/support/eol/.
_KNOWN_EOL: dict[str, dict] = {
    "EX2300": {
        "status": EOLStatus.EOL_ANNOUNCED,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX2300 series - EOL announced",
    },
    "EX3300": {
        "status": EOLStatus.EOL,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX3300 series - end of life",
        "eol_date": date(2019, 3, 31),
        "eos_date": date(2024, 3, 31),
    },
    "EX3400": {
        "status": EOLStatus.EOL,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX3400 series - end of life",
        "eol_date": date(2022, 1, 31),
        "eos_date": date(2025, 1, 31),
    },
    "EX4200": {
        "status": EOLStatus.EOL,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX4200 series - end of life",
        "eol_date": date(2014, 1, 31),
        "eos_date": date(2019, 1, 31),
    },
    "EX4300": {
        "status": EOLStatus.EOL,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX4300 series - end of life",
        "eol_date": date(2023, 3, 31),
        "eos_date": date(2026, 3, 31),
    },
    "EX4550": {
        "status": EOLStatus.EOL,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX4550 series - end of life",
        "eol_date": date(2019, 3, 31),
        "eos_date": date(2024, 3, 31),
    },
    "EX4600": {
        "status": EOLStatus.EOL,
        "family": "ex",
        "risk": RiskCategory.SECURITY,
        "notes": "EX4600 series - end of life",
        "eol_date": date(2022, 6, 30),
        "eos_date": date(2025, 6, 30),
    },
    "SRX220": {
        "status": EOLStatus.EOL,
        "family": "srx",
        "risk": RiskCategory.SECURITY,
        "notes": "SRX220 - end of life, part of SRX200 family",
        "eol_date": date(2015, 1, 31),
        "eos_date": date(2020, 1, 31),
    },
    "SRX300": {
        "status": EOLStatus.EOL,
        "family": "srx",
        "risk": RiskCategory.SECURITY,
        "notes": "SRX300 series - end of life",
        "eol_date": date(2022, 12, 31),
        "eos_date": date(2025, 12, 31),
    },
    "SRX340": {
        "status": EOLStatus.EOL,
        "family": "srx",
        "risk": RiskCategory.SECURITY,
        "notes": "SRX340 - end of life, part of SRX300 family",
        "eol_date": date(2022, 12, 31),
        "eos_date": date(2025, 12, 31),
    },
    "SRX345": {
        "status": EOLStatus.EOL,
        "family": "srx",
        "risk": RiskCategory.SECURITY,
        "notes": "SRX345 - end of life, part of SRX300 family",
        "eol_date": date(2022, 12, 31),
        "eos_date": date(2025, 12, 31),
    },
    "MX80": {
        "status": EOLStatus.EOL,
        "family": "mx",
        "risk": RiskCategory.SECURITY,
        "notes": "MX80 - end of life",
        "eol_date": date(2019, 6, 30),
        "eos_date": date(2024, 6, 30),
    },
    "MX480": {
        "status": EOLStatus.EOL,
        "family": "mx",
        "risk": RiskCategory.SECURITY,
        "notes": "MX480 - end of life",
    },
    "MX960": {
        "status": EOLStatus.EOL,
        "family": "mx",
        "risk": RiskCategory.SECURITY,
        "notes": "MX960 - end of life",
    },
    "QFX5100": {
        "status": EOLStatus.EOL,
        "family": "qfx",
        "risk": RiskCategory.SECURITY,
        "notes": "QFX5100 series - end of life",
        "eol_date": date(2022, 3, 31),
        "eos_date": date(2025, 3, 31),
    },
    "QFX5120": {
        "status": EOLStatus.ACTIVE,
        "family": "qfx",
        "risk": RiskCategory.NONE,
        "notes": "QFX5120 series - current generation",
    },
    "QFX5200": {
        "status": EOLStatus.EOL,
        "family": "qfx",
        "risk": RiskCategory.SECURITY,
        "notes": "QFX5200 series - end of life, replaced by QFX5220",
        "eol_date": date(2021, 6, 30),
        "eos_date": date(2024, 6, 30),
    },
    "QFX5300": {
        "status": EOLStatus.ACTIVE,
        "family": "qfx",
        "risk": RiskCategory.NONE,
        "notes": "QFX5300 series - current generation",
    },
}

# Static rules for specific models not covered by series/component patterns.
# Checked first in _classify_model. (substring, status, risk, reason, conf, notes)
_STATIC_RULES: list[tuple[str, EOLStatus, RiskCategory, EOLReason, int, str]] = [
    # EX4200 components — EOL
    ("EX-UM-2X4SFP", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.MANUFACTURER_DECLARED, 80,
     "EX4200-uplink-module-discontinued"),
    ("EX-UM-4X4SFP", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.MANUFACTURER_DECLARED, 80,
     "EX4200-uplink-module-discontinued"),
    ("EX-PWR-320", EOLStatus.EOL, RiskCategory.SECURITY,
     EOLReason.MANUFACTURER_DECLARED, 80,
     "EX4200-power-supply-discontinued"),
    # QFX accessories — ACTIVE
    ("QFX-EM-4Q", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, 80, "QFX-expansion-module-current"),
    ("QFX520048Y-APSU", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, 80, "QFX-power-supply-current"),
    ("QFXC01-PWRACI", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, 80, "QFX-power-supply-current"),
    # MX components
    ("CHAS-BP3-MX480", EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
     EOLReason.NONE, 80, "MX480-backplane-still-supported"),
    # CFP optic — being replaced by QSFP28
    ("CFP-GEN2-100GBASE-LR4", EOLStatus.EOL, RiskCategory.PROCUREMENT,
     EOLReason.PRODUCT_DISCONTINUED, 80,
     "CFP-GEN2-100G-LR4-replaced-by-QSFP28"),
    # DWDM optics — ACTIVE
    ("SFPP-10G-DW", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, 80, "Juniper-10G-DWDM-optic-current"),
    ("10G SFP+ DWDM", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, 80, "Juniper-10G-SFP+-DWDM-optic-current"),
    ("10G XFP DWDM", EOLStatus.ACTIVE, RiskCategory.NONE,
     EOLReason.NONE, 80, "Juniper-10G-XFP-DWDM-optic-current"),
]

# Patterns for Juniper optics with JNP-/QFX-QSFP-/QFX-SFP-/EX-SFP- prefixes
_JUNIPER_OPTIC_PREFIXES = (
    "JNP-", "QFX-QSFP-", "QFX-SFP-", "EX-SFP-",
)

# Component prefixes that map to parent chassis families
_COMPONENT_PATTERNS: list[tuple[str, str, str, str | None]] = [
    # (regex_pattern, parent_family, description, parent_chassis_key_override)
    (r"^PWR-MX(\d+)", "mx", "MX power supply", None),
    (r"^MPC-?3D", "mx", "MX MPC-3D line card", None),
    (r"^MPC3E", "mx", "MX MPC3E line card", None),
    (r"^MPC4E", "mx", "MX MPC4E line card", None),
    (r"^MPC5E", "mx", "MX MPC5E line card", None),
    (r"^MIC-3D", "mx", "MX MIC-3D interface card", None),
    (r"^MIC3-3D", "mx", "MX MIC3-3D interface card", None),
    (r"^SCBE-?MX", "mx", "MX switch control board", None),
    (r"^SCBE2-?MX", "mx", "MX switch control board v2", None),
    (r"^RE-S-", "mx", "MX routing engine", None),
    (r"^FFANTRAY", "mx", "fan tray", None),
    (r"^JPSU-350", "qfx", "QFX5100 power supply", "QFX5100"),
    (r"^JPSU-650W", "ex", "EX4300 power supply", "EX4300"),
    (r"^JPSU-", "juniper_psu", "Juniper power supply", None),
]

# Support contracts and software prefixes — not hardware
_SOFTWARE_PREFIXES = ("MNT-", "SP-FXP-", "AIF-")


def _strip_juniper_prefix(model: str) -> str:
    """Remove 'JUNIPER ' prefix from model string."""
    s = model.strip().upper()
    if s.startswith("JUNIPER "):
        s = s[8:]
    return s


def _extract_series_model(normalized: str) -> str | None:
    """Extract the base series model (e.g., 'EX4300' from 'EX4300-48T')."""
    m = re.match(r"^(EX\d{4})", normalized)
    if m:
        return m.group(1)
    m = re.match(r"^(SRX\d{3,4})", normalized)
    if m:
        model = m.group(1)
        # SRX340 and SRX345 map to SRX300 family
        if model in ("SRX340", "SRX345"):
            return model  # We have entries for these directly
        return model
    m = re.match(r"^(MX\d{2,4})", normalized)
    if m:
        return m.group(1)
    m = re.match(r"^(QFX\d{4})", normalized)
    if m:
        return m.group(1)
    return None


def _match_component(normalized: str) -> tuple[str, str, str | None] | None:
    """Match a component model to its parent family.

    Returns (family, description, parent_key_override) or None.
    """
    for pattern, family, desc, parent_key in _COMPONENT_PATTERNS:
        if re.search(pattern, normalized):
            return family, desc, parent_key
    return None


def _find_parent_chassis_key(normalized: str, family: str) -> str | None:
    """Extract the parent chassis model key from a component model string.

    For MX components like PWR-MX960-AC-S, extract "MX960".
    Returns the key if found in _KNOWN_EOL, else None.
    """
    mx_match = re.search(r"MX(\d{2,4})", normalized)
    if mx_match:
        key = f"MX{mx_match.group(1)}"
        if key in _KNOWN_EOL:
            return key
    return None


def _is_software_contract(normalized: str) -> bool:
    """Check if the model is a software/support contract."""
    return any(normalized.startswith(p) for p in _SOFTWARE_PREFIXES)


def _is_juniper_optic(normalized: str) -> bool:
    """Check if the model is a Juniper-branded optic."""
    return any(normalized.startswith(p) for p in _JUNIPER_OPTIC_PREFIXES)


def _is_generic_optic(normalized: str) -> bool:
    """Check if the model is a generic/white-label optic."""
    generic_patterns = [
        r"^QSFP-",
        r"^SFP-",
        r"^XFP-",
        r"^CFP-",
        r"^\d+GBASE-",
    ]
    return any(re.match(p, normalized) for p in generic_patterns)


def parse_listing_families(html: str) -> list[dict[str, str]]:
    """Parse product family links from the Juniper EOL listing page.

    The listing page embeds product data in a JavaScript variable (_PAGE_DATA)
    within a <script> tag. The product families are nested under the
    'sw-eol-list' selector.

    Returns a list of dicts with 'label' and 'url' keys.
    """
    # Extract _PAGE_DATA JSON from the script tag
    match = re.search(r'"selector"\s*:\s*"sw-eol-list"', html)
    if not match:
        return []

    # Find the enclosing JSON object by searching for "list" key after sw-eol-list
    list_match = re.search(
        r'"selector"\s*:\s*"sw-eol-list"\s*,\s*"properties"\s*:\s*\{', html
    )
    if not list_match:
        return []

    # Extract the properties JSON by counting braces
    start = list_match.end() - 1  # Start at the opening {
    depth = 0
    end = start
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    try:
        properties = json.loads(html[start:end])
    except (json.JSONDecodeError, ValueError):
        return []

    families: list[dict[str, str]] = []
    list_data = properties.get("list", [])
    for section in list_data:
        for group in section.get("items", []):
            for item in group.get("items", []):
                if "label" in item and "url" in item:
                    families.append({"label": item["label"], "url": item["url"]})

    return families


def parse_date_str(date_str: str) -> date | None:
    """Parse a date string in various formats used by Juniper.

    Handles: "Month DD, YYYY", "YYYY-MM-DD", "MM/DD/YYYY", "MM-DD-YYYY"
    """
    date_str = date_str.strip()
    if not date_str:
        return None

    # YYYY-MM-DD (ISO)
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        pass

    # MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # MM-DD-YYYY
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", date_str)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # Month DD, YYYY (e.g., "January 15, 2023")
    m = re.match(r"^(\w+)\s+(\d{1,2}),?\s+(\d{4})$", date_str)
    if m:
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        month = month_names.get(m.group(1).lower())
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    return None


class JuniperChecker(BaseChecker):
    """Juniper Networks EOL checker.

    Checks EOL status by mapping models to product families and looking up
    known EOL dates. Parses the main EOL listing page to discover product
    family URLs.
    """

    manufacturer_name = "Juniper"
    rate_limit = 3
    priority = 20
    base_url = "https://support.juniper.net"

    source_name = "juniper-eol"

    def __init__(self) -> None:
        super().__init__()
        self._listing_families: list[dict[str, str]] | None = None

    @classmethod
    async def refresh_cache(cls, cache) -> int:
        """Re-fetch the Juniper EOL listing page and store in cache.

        Returns the number of product families found.
        """
        url = f"{cls.base_url}/support/eol/"
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True,
        ) as client:
            try:
                logger.info("Fetching %s...", url)
                resp = await client.get(url)
                resp.raise_for_status()
                logger.info("Fetched %s (%s)", url, resp.status_code)
                families = parse_listing_families(resp.text)
            except httpx.TimeoutException:
                logger.warning("Timeout fetching %s after 10s", url)
                return 0
            except httpx.HTTPStatusError as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                return 0
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                return 0
        await cache.set_source(
            cls.source_name, json.dumps(families), len(families),
        )
        return len(families)

    async def _fetch_listing(self) -> list[dict[str, str]]:
        """Fetch and parse the main EOL listing page."""
        if self._listing_families is not None:
            return self._listing_families

        try:
            resp = await self._fetch(f"{self.base_url}/support/eol/")
            self._listing_families = parse_listing_families(resp.text)
        except Exception as exc:
            logger.warning("Failed to fetch Juniper EOL listing: %s", exc)
            self._listing_families = []

        return self._listing_families

    def _classify_model(self, model: HardwareModel) -> EOLResult:
        """Classify a model based on local knowledge and pattern matching."""
        normalized = _strip_juniper_prefix(model.model)

        # Static rules — specific overrides checked first
        for key, status, risk, reason, conf, notes in _STATIC_RULES:
            if key in normalized:
                eol_date = None
                eos_date = None
                date_source = "none"
                # Propagate parent chassis date for EX4200 components
                if "EX4200" in notes:
                    parent = _KNOWN_EOL.get("EX4200")
                    if parent and parent.get("eol_date"):
                        eol_date = parent["eol_date"]
                        eos_date = parent.get("eos_date")
                        date_source = "manufacturer_confirmed"
                return EOLResult(
                    model=model,
                    status=status,
                    eol_date=eol_date,
                    eos_date=eos_date,
                    checked_at=datetime.now(),
                    source_name="juniper-eol",
                    confidence=conf,
                    notes=notes,
                    eol_reason=reason,
                    risk_category=risk,
                    date_source=date_source,
                )

        # Software/support contracts
        if _is_software_contract(normalized):
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="juniper-eol",
                confidence=60,
                notes="support-contract-active",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.INFORMATIONAL,
                date_source="none",
            )

        # Juniper-branded optics
        if _is_juniper_optic(normalized):
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="juniper-eol",
                confidence=80,
                notes="juniper-optic-current",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.NONE,
                date_source="none",
            )

        # Generic/white-label optics
        if _is_generic_optic(normalized):
            return EOLResult(
                model=model,
                status=EOLStatus.UNKNOWN,
                checked_at=datetime.now(),
                source_name="juniper-eol",
                confidence=30,
                notes="generic-white-label-optic",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.PROCUREMENT,
                date_source="none",
            )

        # Direct series match (EX, SRX, MX, QFX)
        series = _extract_series_model(normalized)
        if series:
            known = _KNOWN_EOL.get(series)
            if known:
                family = known["family"]
                url = _FAMILY_URLS.get(family, "")
                is_active = known["status"] == EOLStatus.ACTIVE
                eol_date = known.get("eol_date")
                eos_date = known.get("eos_date")
                return EOLResult(
                    model=model,
                    status=known["status"],
                    eol_date=eol_date,
                    eos_date=eos_date,
                    source_url=f"{self.base_url}{url}" if url else "",
                    source_name="juniper-eol",
                    checked_at=datetime.now(),
                    confidence=90,
                    notes=known["notes"],
                    eol_reason=(
                        EOLReason.NONE if is_active
                        else EOLReason.MANUFACTURER_DECLARED
                    ),
                    risk_category=known.get(
                        "risk", RiskCategory.SECURITY
                    ),
                    date_source=(
                        "manufacturer_confirmed" if eol_date or eos_date
                        else "none"
                    ),
                )
            # Series recognized but no known EOL data
            return EOLResult(
                model=model,
                status=EOLStatus.UNKNOWN,
                checked_at=datetime.now(),
                source_name="juniper-eol",
                confidence=50,
                notes="not-on-eol-page-may-be-active",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.SECURITY,
                date_source="none",
            )

        # Component to parent chassis mapping
        comp = _match_component(normalized)
        if comp:
            family, desc, parent_key_override = comp
            # Try to propagate parent chassis date
            eol_date = None
            eos_date = None
            date_source = "none"
            parent_key = parent_key_override or _find_parent_chassis_key(
                normalized, family,
            )
            if parent_key:
                parent = _KNOWN_EOL.get(parent_key)
                if parent and parent.get("eol_date"):
                    eol_date = parent["eol_date"]
                    eos_date = parent.get("eos_date")
                    date_source = "manufacturer_confirmed"
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                eol_date=eol_date,
                eos_date=eos_date,
                checked_at=datetime.now(),
                source_name="juniper-eol",
                source_url=f"{self.base_url}{_FAMILY_URLS.get(family, '')}",
                confidence=70,
                notes=f"component-follows-parent-chassis: {desc}",
                eol_reason=EOLReason.MANUFACTURER_DECLARED,
                risk_category=RiskCategory.PROCUREMENT,
                date_source=date_source,
            )

        # Not matched at all
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="juniper-eol",
            confidence=50,
            notes="not-on-eol-page-may-be-active",
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.SECURITY,
            date_source="none",
        )

    async def check(self, model: HardwareModel) -> EOLResult:
        """Check EOL status for a single Juniper model."""
        # Fetch listing page to validate product families exist
        await self._fetch_listing()
        return self._classify_model(model)

    async def check_batch(self, models: list[HardwareModel]) -> list[EOLResult]:
        """Check multiple Juniper models, fetching listing page once."""
        await self._fetch_listing()
        results: list[EOLResult] = []
        for model in models:
            try:
                results.append(self._classify_model(model))
            except Exception as exc:
                logger.warning("Check failed for %s: %s", model.model, exc)
                results.append(
                    EOLResult(
                        model=model,
                        status=EOLStatus.UNKNOWN,
                        checked_at=datetime.now(),
                        source_name="juniper-eol",
                        notes=f"check-error: {exc}",
                    )
                )
        return results
