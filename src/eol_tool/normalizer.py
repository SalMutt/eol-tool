"""Model string normalization."""

import re

# Categories that may appear as colon-separated prefixes in raw model strings.
_CATEGORY_PREFIXES = frozenset({
    "CHASSIS", "FIREWALLS", "GPU", "HARD DRIVES", "HEAT SINKS",
    "MAINBOARD", "MEMORY", "NETWORK CARDS", "NETWORK DEVICES",
    "OPTICS", "PROCESSORS", "RAID CARDS", "SERVER", "SERVER BAREBONE",
    "SSD DRIVES", "SWITCHES",
})

# Condition labels that may appear as colon-separated prefixes.
_CONDITION_PREFIXES = frozenset({"NEW", "USED", "REFURBISHED"})


def normalize_model(raw: str, manufacturer: str = "") -> str:
    """Normalize a raw model string.

    Strips category/condition colon-prefixes, capacity prefixes,
    brand abbreviations, and applies manufacturer-specific rules.
    """
    text = raw.strip().upper()
    if not text:
        return text

    # Strip CATEGORY: and CONDITION: colon-prefixes
    # e.g. "MAINBOARD:NEW:AsRock X470D4U" → "ASROCK X470D4U"
    text = _strip_colon_prefixes(text)

    # Strip capacity prefixes (e.g. "32GB ", "1.92TB ", "960GB ", "8GB:")
    text = re.sub(r"^\d+(\.\d+)?\s*(GB|TB|MB|PB)[:\s]+", "", text)

    mfr = manufacturer.strip().upper()

    # Manufacturer-specific rules (these handle their own brand stripping)
    if mfr == "INTEL":
        text = _normalize_intel(text)
    elif mfr == "AMD":
        text = _normalize_amd(text)
    elif mfr == "SEAGATE":
        text = _normalize_seagate(text)
    elif mfr == "SAMSUNG":
        text = _normalize_samsung(text)
    elif mfr == "SUPERMICRO":
        text = _normalize_supermicro(text)
    elif mfr == "ASUS":
        text = _normalize_asus(text)
    elif mfr and text.startswith(mfr + " "):
        # Generic brand prefix removal for other manufacturers
        text = text[len(mfr):].strip()

    return text.strip()


def _strip_colon_prefixes(text: str) -> str:
    """Strip leading CATEGORY: and CONDITION: colon-prefixes."""
    idx = text.find(":")
    if idx > 0 and text[:idx].strip() in _CATEGORY_PREFIXES:
        text = text[idx + 1:].strip()

    idx = text.find(":")
    if idx > 0 and text[:idx].strip() in _CONDITION_PREFIXES:
        text = text[idx + 1:].strip()

    return text


def _normalize_intel(text: str) -> str:
    """Intel CPU normalization."""
    # Strip "INTEL " prefix if present
    text = re.sub(r"^INTEL\s+", "", text)

    # Pattern: "6146 GOLD" -> "XEON GOLD 6146"
    m = re.match(r"^(\d{4}\w?)\s+(GOLD|SILVER|BRONZE|PLATINUM)$", text)
    if m:
        return f"XEON {m.group(2)} {m.group(1)}"

    # Pattern: "4110 SILVER XEON" -> "XEON SILVER 4110"
    m = re.match(r"^(\d{4}\w?)\s+(SILVER|GOLD|BRONZE|PLATINUM)\s+XEON$", text)
    if m:
        return f"XEON {m.group(2)} {m.group(1)}"

    # Collapse space before V in Xeon E-series: "E3-1230 V5" -> "E3-1230V5"
    # Then prepend XEON if it's an E-series without it
    text = re.sub(r"(E\d-\d{4}\w?)\s+(V\d+)", r"\1\2", text)

    # If it's an E-series model without XEON prefix, add it
    if re.match(r"^E\d-", text):
        text = "XEON " + text

    return text


def _normalize_amd(text: str) -> str:
    """AMD CPU normalization: strip AMD prefix."""
    return re.sub(r"^AMD\s+", "", text)


def _normalize_seagate(text: str) -> str:
    """Seagate drive normalization: strip ENT and dash suffixes."""
    text = re.sub(r"\s*\bENT\b", "", text)
    text = re.sub(r"\s*-\s*M\d+$", "", text)
    return text


def _normalize_samsung(text: str) -> str:
    """Samsung normalization: strip SAM prefix."""
    return re.sub(r"^SAM\s+", "", text)


def _normalize_supermicro(text: str) -> str:
    """Supermicro normalization: strip SM prefix."""
    return re.sub(r"^SM\s+", "", text)


def _normalize_asus(text: str) -> str:
    """ASUS normalization: strip ASUS, ASU SV, ASU prefixes."""
    return re.sub(r"^(?:ASUS\s+|ASU\s+SV\s+|ASU\s+)", "", text)
