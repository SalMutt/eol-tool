"""Manual override checker using a local CSV of known model classifications.

Provides EOL status for models that cannot be resolved by vendor-specific
checkers, tech generation rules, or the endoflife.date API. This is the
last checker in the priority chain before returning UNKNOWN.
"""
import csv
import logging
from datetime import date, datetime

from eol_tool._paths import data_dir

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

logger = logging.getLogger(__name__)


_CSV_PATH = data_dir() / "manual_overrides.csv"

_STATUS_MAP = {
    "eol": EOLStatus.EOL,
    "eol_announced": EOLStatus.EOL_ANNOUNCED,
    "active": EOLStatus.ACTIVE,
    "unknown": EOLStatus.UNKNOWN,
    "not_found": EOLStatus.NOT_FOUND,
}

_REASON_MAP = {
    "manufacturer_declared": EOLReason.MANUFACTURER_DECLARED,
    "technology_generation": EOLReason.TECHNOLOGY_GENERATION,
    "product_discontinued": EOLReason.PRODUCT_DISCONTINUED,
    "vendor_acquired": EOLReason.VENDOR_ACQUIRED,
    "community_data": EOLReason.COMMUNITY_DATA,
    "manual_override": EOLReason.MANUAL_OVERRIDE,
    "none": EOLReason.NONE,
}

_RISK_MAP = {
    "security": RiskCategory.SECURITY,
    "support": RiskCategory.SUPPORT,
    "procurement": RiskCategory.PROCUREMENT,
    "informational": RiskCategory.INFORMATIONAL,
    "none": RiskCategory.NONE,
}


class _OverrideEntry:
    """A single row from the manual overrides CSV."""

    __slots__ = (
        "model",
        "manufacturer",
        "status",
        "eol_reason",
        "risk_category",
        "eol_date",
        "eos_date",
        "source_url",
        "notes",
        "release_date",
        "confidence",
    )

    def __init__(self, row: dict[str, str]) -> None:
        self.model = row.get("model", "").strip()
        self.manufacturer = row.get("manufacturer", "").strip()
        self.status = _STATUS_MAP.get(row.get("status", "").strip().lower(), EOLStatus.UNKNOWN)
        self.eol_reason = _REASON_MAP.get(
            row.get("eol_reason", "").strip().lower(), EOLReason.NONE
        )
        self.risk_category = _RISK_MAP.get(
            row.get("risk_category", "").strip().lower(), RiskCategory.NONE
        )
        self.eol_date = _parse_date(row.get("eol_date") or "")
        self.eos_date = _parse_date(row.get("eos_date") or "")
        self.source_url = (row.get("source_url") or "").strip()
        self.notes = (row.get("notes") or "").strip()
        self.release_date = _parse_date(row.get("release_date") or "")
        raw_conf = (row.get("confidence") or "").strip()
        self.confidence = int(raw_conf) if raw_conf else None


def _parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class ManualChecker(BaseChecker):
    """Checks models against a local CSV of manual overrides.

    Supports partial model matching: a CSV entry for "EX4300" will match
    input models like "EX4300-48T" or "EX4300-48T-CPO". Matching is
    case-insensitive.
    """

    manufacturer_name = "__manual__"
    rate_limit = 100
    priority = 10
    base_url = ""

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[_OverrideEntry] = []
        self._load_csv()

    def _load_csv(self) -> None:
        if not _CSV_PATH.exists():
            logger.warning("Manual overrides CSV not found: %s", _CSV_PATH)
            return
        with open(_CSV_PATH, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entry = _OverrideEntry(row)
                if entry.model:
                    self._entries.append(entry)
        logger.debug("Loaded %d manual override entries", len(self._entries))

    def _find_match(self, model_name: str) -> _OverrideEntry | None:
        """Find the best matching override entry for a model name.

        Tries exact match first, then partial (prefix) match. Longer CSV
        model strings are preferred to avoid overly broad matches.
        """
        upper = model_name.upper()

        # Exact match first
        for entry in self._entries:
            if entry.model.upper() == upper:
                return entry

        # Partial match: CSV model is a prefix of the input model
        best: _OverrideEntry | None = None
        best_len = 0
        for entry in self._entries:
            entry_upper = entry.model.upper()
            if upper.startswith(entry_upper) and len(entry_upper) > best_len:
                best = entry
                best_len = len(entry_upper)

        return best

    async def check(self, model: HardwareModel) -> EOLResult:
        entry = self._find_match(model.model)
        if entry is None and model.original_item:
            entry = self._find_match(model.original_item)
        if entry is None:
            return EOLResult(
                model=model,
                status=EOLStatus.UNKNOWN,
                checked_at=datetime.now(),
                source_name="manual-overrides",
                confidence=0,
                notes="no-automated-checker-available",
            )

        return EOLResult(
            model=model,
            status=entry.status,
            eol_date=entry.eol_date,
            eos_date=entry.eos_date,
            release_date=entry.release_date,
            source_url=entry.source_url,
            source_name="manual-overrides",
            checked_at=datetime.now(),
            confidence=entry.confidence if entry.confidence is not None else 80,
            notes=entry.notes,
            eol_reason=EOLReason.MANUAL_OVERRIDE,
            risk_category=entry.risk_category,
            date_source=(
                "manufacturer_confirmed"
                if entry.eol_date or entry.eos_date or entry.release_date
                else "none"
            ),
        )
