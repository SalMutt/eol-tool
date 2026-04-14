"""Generation-based date lookup for hardware models.

Loads generation_dates.csv and provides approximate release/EOL dates
based on technology generation matching against model strings, notes,
manufacturer, and category fields.
"""
import csv
from datetime import date

from eol_tool._paths import data_dir

_DATES: list[dict] | None = None


def _load() -> None:
    global _DATES
    if _DATES is not None:
        return
    path = data_dir() / "generation_dates.csv"
    _DATES = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pattern = row["generation_pattern"].strip()
            if pattern.startswith("#"):
                continue
            _DATES.append({
                "pattern": pattern,
                "release_date": _parse_date(row.get("release_date", "")),
                "eol_estimate": _parse_date(row.get("eol_estimate", "")),
                "source": row.get("source", "generation-estimate"),
            })


def _parse_date(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    return date.fromisoformat(s)


def lookup_generation_dates(
    model_str: str,
    notes: str,
    manufacturer: str,
    category: str,
    original_item: str = "",
) -> dict | None:
    """Find generation-based dates for a model.

    Searches the combined text of model string, notes, manufacturer,
    category, and original_item for generation pattern matches.
    Returns the most specific match (longest pattern first).
    """
    _load()
    assert _DATES is not None
    search_text = f"{model_str} {notes} {manufacturer} {category} {original_item}".upper()
    # Try longest patterns first for specificity
    for entry in sorted(_DATES, key=lambda e: len(e["pattern"]), reverse=True):
        if entry["pattern"].upper() in search_text:
            return entry
    return None


def reset() -> None:
    """Reset the loaded cache (for testing)."""
    global _DATES
    _DATES = None
