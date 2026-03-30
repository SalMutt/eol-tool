"""Pydantic models for EOL tool."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class HardwareModel(BaseModel):
    """Represents a hardware model to check for EOL status."""

    model: str
    manufacturer: str
    category: str
    condition: str = ""
    original_item: str = ""


class EOLStatus(str, Enum):
    """End-of-life status for a hardware model."""

    EOL = "eol"
    EOL_ANNOUNCED = "eol_announced"
    ACTIVE = "active"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"


class EOLReason(str, Enum):
    """Reason for the EOL determination."""

    MANUFACTURER_DECLARED = "manufacturer_declared"
    TECHNOLOGY_GENERATION = "technology_generation"
    PRODUCT_DISCONTINUED = "product_discontinued"
    VENDOR_ACQUIRED = "vendor_acquired"
    COMMUNITY_DATA = "community_data"
    MANUAL_OVERRIDE = "manual_override"
    NONE = "none"


class RiskCategory(str, Enum):
    """Risk category for an EOL determination."""

    SECURITY = "security"
    SUPPORT = "support"
    PROCUREMENT = "procurement"
    INFORMATIONAL = "informational"
    NONE = "none"


class EOLResult(BaseModel):
    """Result of an EOL check for a hardware model."""

    model: HardwareModel
    status: EOLStatus = EOLStatus.UNKNOWN
    eol_date: date | None = None
    eos_date: date | None = None
    source_url: str = ""
    source_name: str = ""
    checked_at: datetime
    confidence: int = 0
    notes: str = ""
    eol_reason: EOLReason = EOLReason.NONE
    risk_category: RiskCategory = RiskCategory.NONE
    date_source: str = "none"
    checker_priority: int = 50
