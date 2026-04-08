"""Input filter to strip junk rows before the classification pipeline."""

import logging
import re

from .models import HardwareModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelists — if a model string matches any of these, it is NEVER filtered.
# These are checked before junk patterns to avoid false positives.
# ---------------------------------------------------------------------------

# Manufacturer names that can appear in the model string itself.
_MANUFACTURER_WHITELIST = re.compile(
    r"\b(?:"
    r"WD|WESTERN\s*DIGITAL|SEAGATE|TOSHIBA|TOS|HITACHI|HGST"
    r"|SANDISK|JUNIPER|EVGA|PNY|NVIDIA|GEFORCE|RADEON|AMD|INTEL"
    r"|SAMSUNG|KINGSTON|MICRON|CRUCIAL|BROADCOM|BROCADE|MELLANOX"
    r"|CORSAIR|SK\s*HYNIX|KIOXIA|ADATA|MUSHKIN|OCZ|SOLIDIGM|TRANSCEND"
    r"|DELL|HPE|SUPERMICRO|CISCO|ARISTA|ASROCK|ASUS|GIGABYTE|MSI|ZOTAC"
    r"|ADAPTEC|AXIOM|CHENBRO|DYNATRON|IBM"
    r")\b",
    re.IGNORECASE,
)

# Model number patterns for known hardware families.
_MODEL_NUMBER_WHITELIST = re.compile(
    r"(?:"
    r"\bWD[A-Z0-9]{4,}\b"           # WD drives (WD102KFBX, WD2005FBYZ)
    r"|\bMG\d{2}[A-Z]+"             # Toshiba MG series (MG06ACA10TE)
    r"|\bST\d{3,}"                  # Seagate drives (ST8000NM000A)
    r"|\b\dF\d+"                    # Hitachi model numbers (0F12470)
    r"|\bSRX\d+"                    # Juniper firewalls (SRX300, SRX340)
    r"|\bEX\d+"                     # Juniper switches (EX4300)
    r"|\bQFX\d+"                    # Juniper switches (QFX5100)
    r"|\bMX\d+"                     # Juniper routers (MX204)
    r"|\bCSE-[A-Z0-9]+"            # Supermicro chassis (CSE-826)
    r"|\bX\d{1,2}[A-Z]+"           # Supermicro boards (X11DPH)
    r"|\bEPYC\b|\bRYZEN\b|\bTHREADRIPPER\b"  # AMD CPUs
    r"|\bGEFORCE\b|\bRTX\b|\bGTX\b|\bQUADRO\b"  # GPUs
    r"|\bP\d{4}\b|\bT\d{3,4}\b|\bA\d{3,4}\b"    # NVIDIA pro GPUs
    r"|\bVCQRTX[A-Z0-9]+|\bVCQ[A-Z]+"            # PNY/NVIDIA Quadro
    r")",
    re.IGNORECASE,
)

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


def _matches_whitelist(upper: str) -> bool:
    """Return True if the model string matches a known manufacturer or model pattern."""
    if _MANUFACTURER_WHITELIST.search(upper):
        return True
    if _MODEL_NUMBER_WHITELIST.search(upper):
        return True
    return False


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

    # Whitelists — if the model contains a known manufacturer name or
    # model-number pattern, keep it regardless of junk-pattern matches.
    if _matches_whitelist(upper):
        return False

    # Optics are always real hardware
    if _OPTIC_RE.search(upper):
        return False

    # Explicit junk patterns — only these cause filtering
    for pattern, _ in _JUNK_PATTERNS:
        if pattern.search(upper):
            return True

    # Default: keep the row.  The junk patterns above catch genuinely
    # non-hardware rows; everything else is assumed to be real hardware.
    return False


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
