"""Manufacturer correction layer.

Some models in the dataset have incorrect manufacturer assignments
(e.g., Arista optics tagged as Seagate). This module corrects the
manufacturer field before models are dispatched to checkers.
"""

import logging
import re

from .models import HardwareModel

logger = logging.getLogger(__name__)

# Each entry: (compiled regex on model string, correct manufacturer)
_CORRECTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Arista|ARISTA", re.IGNORECASE), "Arista"),
    (re.compile(r"AIF-SP-FXP|AIF-TMS-SOFTWARE|AIF SP-FXP", re.IGNORECASE), "Juniper"),
    (re.compile(r"IBM 46C9111|ServeRAID", re.IGNORECASE), "IBM"),
    (re.compile(r"X10SLH-N6-ST031", re.IGNORECASE), "Supermicro"),
    (re.compile(r"MX960|PWR-MX960|MIC3-3D-1X100GE", re.IGNORECASE), "Juniper"),
    (re.compile(r"JNP-QSFP-4X10GE", re.IGNORECASE), "Juniper"),
    (re.compile(r"VCGGTX1080", re.IGNORECASE), "PNY"),
    (re.compile(r"TOS THNSNH|THNSNH", re.IGNORECASE), "Toshiba"),
    (re.compile(r"S8016AGM2NR", re.IGNORECASE), "ASRock"),
    (re.compile(r"\bTS\d+DSTMM\d", re.IGNORECASE), "Transcend"),
]


def apply_manufacturer_corrections(models: list[HardwareModel]) -> list[HardwareModel]:
    """Fix manufacturer assignments based on model/original_item patterns.

    Checks both model.model and model.original_item for pattern matches.
    Returns the same list with corrections applied in-place.
    """
    for m in models:
        text = f"{m.model} {m.original_item}"
        for pattern, correct_mfr in _CORRECTIONS:
            if pattern.search(text):
                if m.manufacturer != correct_mfr:
                    logger.info(
                        "Manufacturer correction: %s -> %s for model %s",
                        m.manufacturer,
                        correct_mfr,
                        m.model,
                    )
                    m.manufacturer = correct_mfr
                break  # first match wins
    return models
