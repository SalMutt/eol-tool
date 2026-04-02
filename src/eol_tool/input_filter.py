"""Input filter to strip junk rows before the classification pipeline."""

import logging
import re

from .models import HardwareModel

logger = logging.getLogger(__name__)

# Optics keywords — items containing these are real hardware
_OPTIC_RE = re.compile(r"\bQ?SFPP?\b|\bQ?SFP\d|SFP\+|\bXFP\b|\bCFP\b")

# Junk patterns with human-readable reasons.
# Checked against uppercased model strings.
_JUNK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Vague single-word labels
    (re.compile(r"^(NEW|USED|REFURBISHED)$"), "vague label"),
    (re.compile(r"^FS\s+BOX$"), "vague label"),
    # Size / capacity descriptions
    (re.compile(r"^\d+U\s+\d+BAY"), "size/capacity description"),
    # Server build configs
    (re.compile(r"\bSERVER\s*(BAREBONE|:?\s*USED)"), "server build config"),
    (re.compile(r"\bRW\s+SERVER\b"), "server build config"),
    (re.compile(r"\bAMS\d*\s+SERVER\b"), "server build config"),
    # Internal inventory codes
    (re.compile(r"^UK-\d+"), "internal inventory code"),
    # RAM config strings
    (re.compile(r"\d+\s*X\s+\d+\s*[-\u2013]\s*\d+\s*GB"), "RAM config string"),
    (re.compile(r"\d+\s*[-\u2013]\s*\d+\s*GB\s*[-\u2013]\s*\d+\s*GB"), "RAM config string"),
    # CPU config with SERIES
    (re.compile(r"\bSERIES\b"), "CPU config string"),
    # Vague storage labels
    (re.compile(r"HALF-SLIM\s+SSD"), "vague label"),
    # Short cryptic codes / capacity+speed specs
    (re.compile(r"\d+TBI?\s+\d+K\b"), "short cryptic code"),
    (re.compile(r"\d+TB\s*RAM"), "short cryptic code"),
    (re.compile(r"^\d+CH\s+\d+-\d+$"), "short cryptic code"),
]

# Hardware part-number pattern: letter prefix + dash + segment containing a letter
_PART_NUMBER_RE = re.compile(r"^[A-Z]{2,}\d*-[A-Z0-9]*[A-Z][A-Z0-9]*")

# Drive model number: starts with digit(s) immediately followed by letter(s), min 5 chars
_DRIVE_MODEL_RE = re.compile(r"^\d+[A-Z]")

_MIN_DRIVE_MODEL_LEN = 5


def is_junk_row(model: str, manufacturer: str) -> bool:
    """Return True if the row should be filtered out.

    A row is junk when the manufacturer is empty/blank AND the model string
    does not match any known hardware pattern.
    """
    if manufacturer and manufacturer.strip():
        return False

    upper = model.strip().upper()
    if not upper:
        return True

    # Optics are always real hardware
    if _OPTIC_RE.search(upper):
        return False

    # Explicit junk patterns (checked before generic hardware patterns)
    for pattern, _ in _JUNK_PATTERNS:
        if pattern.search(upper):
            return True

    # Known hardware patterns — kept even without manufacturer
    if _PART_NUMBER_RE.match(upper):
        return False
    if _DRIVE_MODEL_RE.match(upper) and len(upper) >= _MIN_DRIVE_MODEL_LEN:
        return False

    # No manufacturer and no recognized hardware pattern
    return True


def _get_reason(model: str) -> str:
    """Return a human-readable reason why the model was filtered."""
    upper = model.strip().upper()
    for pattern, reason in _JUNK_PATTERNS:
        if pattern.search(upper):
            return reason
    return "no recognized hardware pattern"


def filter_models(
    models: list[HardwareModel],
) -> tuple[list[HardwareModel], list[dict]]:
    """Split models into clean and filtered lists.

    Returns (clean_models, filtered_rows).
    Each entry in *filtered_rows* is a dict with keys model, manufacturer,
    and reason.
    """
    clean: list[HardwareModel] = []
    filtered: list[dict] = []

    for m in models:
        if is_junk_row(m.model, m.manufacturer):
            reason = _get_reason(m.model)
            filtered.append({
                "model": m.model,
                "manufacturer": m.manufacturer,
                "reason": reason,
            })
            logger.info("Filtered junk row: model='%s' reason='%s'", m.model, reason)
        else:
            clean.append(m)

    return clean, filtered
