"""Intel EOL checker using static lookup for NICs, SSDs, RAID, and ordering codes.

Covers Intel CPU ordering codes (CM806x, CD806x, BX806x, PK8071, SR S-specs),
Intel SSD ordering codes (SSDSC2*, SSDPE*), NICs, and RAID products.
CPUs with human-readable names are handled by tech_generation.py.
"""

import re
from datetime import date, datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

# ── CPU ordering code patterns ─────────────────────────────────────
# (regex, status, risk, confidence, notes)
_CPU_ORDERING_RULES: list[tuple[re.Pattern, EOLStatus, RiskCategory, int, str]] = [
    # PK8071* = Sapphire Rapids / Emerald Rapids (4th/5th gen Scalable) → active
    (re.compile(r"^PK8071"), EOLStatus.ACTIVE, RiskCategory.NONE, 75,
     "Intel Sapphire Rapids / Emerald Rapids (4th/5th gen Scalable)"),
    # CM8064* = Haswell → EOL
    (re.compile(r"^CM8064"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Haswell (4th gen, LGA2011-3) ordering code"),
    # CM8066* = Broadwell → EOL
    (re.compile(r"^CM8066"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Broadwell (5th gen) ordering code"),
    # CM8067* = Skylake/Kaby Lake → EOL
    (re.compile(r"^CM8067"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Skylake/Kaby Lake (6th/7th gen) ordering code"),
    # CM8068* = Coffee Lake → EOL
    (re.compile(r"^CM8068"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Intel Coffee Lake (8th/9th gen) ordering code"),
    # CD8067* = Skylake-SP (1st gen Scalable) → EOL
    (re.compile(r"^CD8067"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Skylake-SP (1st gen Scalable, LGA3647) ordering code"),
    # CD8069* = Cascade Lake (2nd gen Scalable) → EOL
    (re.compile(r"^CD8069"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Cascade Lake (2nd gen Scalable, LGA3647) ordering code"),
    # CD8068* = Ice Lake-SP (3rd gen Scalable) → active
    (re.compile(r"^CD8068"), EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, 75,
     "Intel Ice Lake-SP (3rd gen Scalable, LGA4189) ordering code"),
    # BX80644* = Haswell-EP → EOL
    (re.compile(r"^BX80644"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Haswell-EP boxed ordering code"),
    # BX80660* = Broadwell-EP → EOL
    (re.compile(r"^BX80660"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Broadwell-EP boxed ordering code"),
    # BX80677* = Kaby Lake boxed → EOL
    (re.compile(r"^BX80677"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Kaby Lake boxed ordering code"),
    # BX80684* = Coffee Lake boxed → EOL
    (re.compile(r"^BX80684"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 70,
     "Intel Coffee Lake boxed ordering code"),
    # BX80695* = Cascade Lake boxed → EOL
    (re.compile(r"^BX80695"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 75,
     "Intel Cascade Lake boxed ordering code"),
    # BX80689* = Ice Lake boxed → active
    (re.compile(r"^BX80689"), EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL, 75,
     "Intel Ice Lake boxed ordering code"),
    # Catch-all CM806[4-9]* → EOL (older tray CPUs)
    (re.compile(r"^CM806[4-9]"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 65,
     "Intel tray CPU ordering code (CM806x generation)"),
    # Catch-all CD806[7-9]* → EOL (Xeon Scalable)
    (re.compile(r"^CD806[7-9]"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 60,
     "Intel Xeon Scalable ordering code (CD806x generation)"),
    # Catch-all BX806* → EOL (boxed CPU)
    (re.compile(r"^BX806"), EOLStatus.EOL, RiskCategory.PROCUREMENT, 60,
     "Intel boxed CPU ordering code (BX806x generation)"),
    # SR[A-Z0-9]{2,3} = Intel S-spec → EOL with low confidence
    (re.compile(r"^SR[A-Z0-9]{2,3}$"), EOLStatus.EOL, RiskCategory.INFORMATIONAL, 40,
     "Intel S-spec — use ordering code for precise classification"),
]

# ── SSD ordering code patterns ─────────────────────────────────────
# All Intel SSDs are EOL (NAND business sold to Solidigm 2021)
_SSD_ORDERING_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^SSDSC2BB"), "Intel S3500/S3510/S3700 SATA SSD"),
    (re.compile(r"^SSDSC2KB"), "Intel S4510/D3-S4510 SATA SSD"),
    (re.compile(r"^SSDSC2KG"), "Intel S4500/D3-S4610 SATA SSD"),
    (re.compile(r"^SSDSC2CW"), "Intel 520 Series SATA SSD"),
    (re.compile(r"^SSDSC2KW"), "Intel 540s SATA SSD"),
    (re.compile(r"^SSDSC2"),   "Intel SATA SSD"),
    (re.compile(r"^SSDPE2"),   "Intel P3xxx/P4xxx data center NVMe SSD"),
    (re.compile(r"^SSDPEKK"),  "Intel 760p consumer NVMe SSD"),
    (re.compile(r"^SSDPEDM"),  "Intel P3xxx NVMe SSD"),
    (re.compile(r"^SSDPELN"),  "Intel NVMe SSD"),
    (re.compile(r"^SSDPE"),    "Intel NVMe SSD"),
]

# ── NIC lookup (prefix-matched against normalized model string) ──────
_NIC_MODELS: dict[str, dict] = {
    "X520-DA2": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel Ethernet X520 - 10GbE SFP+ dual port, discontinued",
        "eol_date": date(2021, 7, 1),
    },
    "X540-T2": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel Ethernet X540 - 10GBASE-T dual port, discontinued",
        "eol_date": date(2021, 7, 1),
    },
    "I350-T4": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.INFORMATIONAL,
        "notes": "Intel Ethernet I350 - 1GbE quad port, still widely available",
    },
    "X550-T2": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X550 - 10GBASE-T dual port, current",
    },
    "X710-BM2": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X710 - 10GbE SFP+ dual port, current",
    },
    "X710-T4L": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X710 - 10GBASE-T quad port, current",
    },
    "X722-DA4": {
        "status": EOLStatus.ACTIVE,
        "risk": RiskCategory.NONE,
        "notes": "Intel Ethernet X722 - 10GbE SFP+ quad port, current",
    },
}

# ── SSD lookup (matched only when category is ssd) ──────────────────
_SSD_MODELS: dict[str, dict] = {
    "540": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 540s - consumer SATA, discontinued",
    },
    "520": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 520 - consumer SATA, discontinued",
    },
    "660P": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 660p - QLC NVMe, discontinued",
    },
    "760P": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD 760p - consumer NVMe, discontinued",
    },
    "DC P4511": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel SSD DC P4511 - datacenter NVMe M.2, Solidigm transition",
    },
}

# ── RAID lookup ──────────────────────────────────────────────────────
_RAID_MODELS: dict[str, dict] = {
    "RES2SV240": {
        "status": EOLStatus.EOL,
        "risk": RiskCategory.PROCUREMENT,
        "notes": "Intel RAID Expander RES2SV240 - very old SAS expander",
    },
}

_INTEL_PREFIX_RE = re.compile(r"^INTEL\s+", re.IGNORECASE)


class IntelChecker(BaseChecker):
    """Intel EOL checker using static product lookup."""

    manufacturer_name = "Intel"
    rate_limit = 100
    priority = 40
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        normalized = self._normalize(model.model)

        # ── Ordering code classification (before human-readable patterns) ──
        # SSD ordering codes (all Intel SSDs → EOL, sold to Solidigm)
        result = self._match_ssd_ordering_code(model, normalized)
        if result:
            return result

        # CPU ordering codes
        result = self._match_cpu_ordering_code(model, normalized)
        if result:
            return result

        # ── Human-readable CPU name patterns ──
        if model.category.lower() == "cpu":
            result = self._match_cpu_name(model, normalized)
            if result:
                return result
            # Fallback: try original_item for CPU names
            if model.original_item and model.original_item != model.model:
                item_cleaned = re.sub(
                    r"^[A-Z /]+:(NEW|USED|REFURBISHED):",
                    "",
                    model.original_item.strip().upper(),
                )
                item_normalized = self._normalize(item_cleaned)
                result = self._match_cpu_name(model, item_normalized)
                if result:
                    return result
            return self._not_found(model, "cpu-handled-by-tech-generation")

        is_ssd = model.category.lower() == "ssd"

        # Try RAID lookup first (exact match)
        entry = self._match_raid(normalized)
        if entry:
            return self._make_result(model, entry)

        # Try NIC lookup (prefix match)
        entry = self._match_nic(normalized)
        if entry:
            return self._make_result(model, entry)

        # Try SSD lookup (only for SSD category to avoid 520/540 collisions)
        if is_ssd:
            entry = self._match_ssd(normalized)
            if entry:
                return self._make_result(model, entry)

        return self._not_found(model, "not-found-in-intel-lookup")

    @staticmethod
    def _normalize(model_str: str) -> str:
        """Normalize model string for lookup."""
        s = model_str.strip().upper()
        s = _INTEL_PREFIX_RE.sub("", s)
        return s.strip()

    @staticmethod
    def _match_nic(normalized: str) -> dict | None:
        """Match NIC models by checking if normalized string contains the key."""
        for key in sorted(_NIC_MODELS, key=len, reverse=True):
            if key in normalized:
                return _NIC_MODELS[key]
        return None

    @staticmethod
    def _match_ssd(normalized: str) -> dict | None:
        """Match SSD models — careful with short keys like 520/540."""
        for key in sorted(_SSD_MODELS, key=len, reverse=True):
            if key in normalized:
                return _SSD_MODELS[key]
        return None

    @staticmethod
    def _match_raid(normalized: str) -> dict | None:
        """Match RAID models by exact key match."""
        for key in _RAID_MODELS:
            if key in normalized:
                return _RAID_MODELS[key]
        return None

    @staticmethod
    def _match_cpu_ordering_code(
        model: HardwareModel, normalized: str,
    ) -> EOLResult | None:
        for pattern, status, risk, confidence, notes in _CPU_ORDERING_RULES:
            if pattern.search(normalized):
                return EOLResult(
                    model=model,
                    status=status,
                    checked_at=datetime.now(),
                    source_name="intel-ordering-code",
                    confidence=confidence,
                    notes=notes,
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION
                    if status == EOLStatus.EOL
                    else EOLReason.NONE,
                    risk_category=risk,
                    date_source="none",
                )
        return None

    @staticmethod
    def _match_ssd_ordering_code(
        model: HardwareModel, normalized: str,
    ) -> EOLResult | None:
        for pattern, notes in _SSD_ORDERING_RULES:
            if pattern.search(normalized):
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="intel-ordering-code",
                    confidence=75,
                    notes=f"{notes} — Intel NAND business sold to SK Hynix/Solidigm in 2021",
                    eol_reason=EOLReason.VENDOR_ACQUIRED,
                    risk_category=RiskCategory.PROCUREMENT,
                    date_source="none",
                )
        return None

    @staticmethod
    def _make_result(model: HardwareModel, entry: dict) -> EOLResult:
        eol_date = entry.get("eol_date")
        return EOLResult(
            model=model,
            status=entry["status"],
            checked_at=datetime.now(),
            source_name="intel-static-lookup",
            confidence=80,
            notes=entry["notes"],
            eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            risk_category=entry["risk"],
            eol_date=eol_date,
            date_source="community_database" if eol_date else "none",
        )

    @staticmethod
    def _match_cpu_name(
        model: HardwareModel, normalized: str,
    ) -> EOLResult | None:
        """Match human-readable Intel CPU names (Xeon E-2xxx, Gold/Silver)."""
        # Xeon E-2xxx (Coffee Lake Xeon E)
        m = re.search(r"E-2[01]\d{2}", normalized)
        if m:
            return EOLResult(
                model=model,
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                source_name="intel-cpu-name",
                confidence=75,
                notes="Intel Xeon E-2100/E-2200 Coffee Lake, discontinued",
                eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                risk_category=RiskCategory.PROCUREMENT,
                date_source="none",
            )
        # Xeon E-23xx / E-24xx (newer, active)
        m = re.search(r"E-2[34]\d{2}", normalized)
        if m:
            return EOLResult(
                model=model,
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="intel-cpu-name",
                confidence=75,
                notes="Intel Xeon E-2300/E-2400, current generation",
                eol_reason=EOLReason.NONE,
                risk_category=RiskCategory.NONE,
                date_source="none",
            )
        # Xeon Scalable Gold/Silver/Bronze/Platinum by 4-digit model
        m = re.search(r"\b(\d{4})\w?\s*(?:GOLD|SILVER|BRONZE|PLATINUM)", normalized)
        if not m:
            m = re.search(r"(?:GOLD|SILVER|BRONZE|PLATINUM)\s*\w?\s*(\d{4})", normalized)
        if m:
            num = int(m.group(1))
            if num < 4000:
                # 1st gen Skylake-SP (31xx, 41xx, 51xx, 61xx, 81xx)
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="intel-cpu-name",
                    confidence=70,
                    notes=f"Intel Xeon Scalable {num} (1st gen Skylake-SP), EOL",
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.PROCUREMENT,
                    date_source="none",
                )
            elif num < 5000:
                # 2nd gen Cascade Lake (42xx, 52xx, 62xx, 82xx)
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="intel-cpu-name",
                    confidence=70,
                    notes=f"Intel Xeon Scalable {num} (2nd gen Cascade Lake), EOL",
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.PROCUREMENT,
                    date_source="none",
                )
            elif num < 6000:
                # 3rd gen Ice Lake-SP
                return EOLResult(
                    model=model,
                    status=EOLStatus.ACTIVE,
                    checked_at=datetime.now(),
                    source_name="intel-cpu-name",
                    confidence=70,
                    notes=f"Intel Xeon Scalable {num} (3rd gen Ice Lake-SP), current",
                    eol_reason=EOLReason.NONE,
                    risk_category=RiskCategory.INFORMATIONAL,
                    date_source="none",
                )
            else:
                # 1st gen used 6xxx/8xxx too; classify as EOL for Skylake-SP era
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="intel-cpu-name",
                    confidence=65,
                    notes=f"Intel Xeon Scalable {num} (1st gen Skylake-SP), EOL",
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.PROCUREMENT,
                    date_source="none",
                )
        # Bare 4-digit Xeon number (e.g. "6132", "4110") without Gold/Silver suffix
        m = re.match(r"^(\d{4})\w?$", normalized)
        if m:
            num = int(m.group(1))
            if 3100 <= num <= 8199:
                return EOLResult(
                    model=model,
                    status=EOLStatus.EOL,
                    checked_at=datetime.now(),
                    source_name="intel-cpu-name",
                    confidence=60,
                    notes=f"Intel Xeon Scalable {num}, likely 1st/2nd gen, EOL",
                    eol_reason=EOLReason.TECHNOLOGY_GENERATION,
                    risk_category=RiskCategory.PROCUREMENT,
                    date_source="none",
                )
        return None

    @staticmethod
    def _not_found(model: HardwareModel, reason: str) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="intel-static-lookup",
            confidence=0,
            notes=reason,
        )
