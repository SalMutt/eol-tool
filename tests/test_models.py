"""Tests for Pydantic models."""

from datetime import date, datetime

from eol_tool.models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory


class TestHardwareModel:
    def test_create_minimal(self):
        m = HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch")
        assert m.model == "EX4300-48T"
        assert m.manufacturer == "Juniper"
        assert m.category == "switch"
        assert m.condition == ""
        assert m.original_item == ""

    def test_create_full(self):
        m = HardwareModel(
            model="EX4300-48T",
            manufacturer="Juniper",
            category="switch",
            condition="used",
            original_item="Juniper EX4300-48T Switch",
        )
        assert m.condition == "used"
        assert m.original_item == "Juniper EX4300-48T Switch"

    def test_serialization_roundtrip(self):
        m = HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch")
        d = m.model_dump()
        assert d["model"] == "EX4300-48T"
        assert "manufacturer" in d
        m2 = HardwareModel.model_validate(d)
        assert m2 == m


class TestEOLStatus:
    def test_enum_values(self):
        assert EOLStatus.EOL.value == "eol"
        assert EOLStatus.EOL_ANNOUNCED.value == "eol_announced"
        assert EOLStatus.ACTIVE.value == "active"
        assert EOLStatus.UNKNOWN.value == "unknown"
        assert EOLStatus.NOT_FOUND.value == "not_found"

    def test_string_comparison(self):
        assert EOLStatus.EOL == "eol"
        assert EOLStatus.ACTIVE == "active"


class TestEOLReason:
    def test_enum_values(self):
        assert EOLReason.MANUFACTURER_DECLARED.value == "manufacturer_declared"
        assert EOLReason.TECHNOLOGY_GENERATION.value == "technology_generation"
        assert EOLReason.PRODUCT_DISCONTINUED.value == "product_discontinued"
        assert EOLReason.VENDOR_ACQUIRED.value == "vendor_acquired"
        assert EOLReason.COMMUNITY_DATA.value == "community_data"
        assert EOLReason.MANUAL_OVERRIDE.value == "manual_override"
        assert EOLReason.NONE.value == "none"

    def test_string_comparison(self):
        assert EOLReason.COMMUNITY_DATA == "community_data"
        assert EOLReason.NONE == "none"


class TestRiskCategory:
    def test_enum_values(self):
        assert RiskCategory.SECURITY.value == "security"
        assert RiskCategory.SUPPORT.value == "support"
        assert RiskCategory.PROCUREMENT.value == "procurement"
        assert RiskCategory.INFORMATIONAL.value == "informational"
        assert RiskCategory.NONE.value == "none"

    def test_string_comparison(self):
        assert RiskCategory.SECURITY == "security"
        assert RiskCategory.NONE == "none"


class TestEOLResult:
    def test_create_defaults(self):
        m = HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch")
        r = EOLResult(model=m, checked_at=datetime(2025, 1, 1))
        assert r.status == EOLStatus.UNKNOWN
        assert r.eol_date is None
        assert r.eos_date is None
        assert r.confidence == 0
        assert r.source_url == ""
        assert r.eol_reason == EOLReason.NONE
        assert r.risk_category == RiskCategory.NONE

    def test_create_full(self):
        m = HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch")
        r = EOLResult(
            model=m,
            status=EOLStatus.EOL,
            eol_date=date(2023, 6, 15),
            eos_date=date(2026, 6, 15),
            source_url="https://example.com/eol",
            source_name="juniper-eol-page",
            checked_at=datetime(2025, 1, 1),
            confidence=95,
            notes="Confirmed via official bulletin",
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SECURITY,
        )
        assert r.status == EOLStatus.EOL
        assert r.eol_date == date(2023, 6, 15)
        assert r.confidence == 95
        assert r.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert r.risk_category == RiskCategory.SECURITY

    def test_serialization_roundtrip(self):
        m = HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch")
        r = EOLResult(
            model=m,
            checked_at=datetime(2025, 1, 1),
            eol_reason=EOLReason.COMMUNITY_DATA,
            risk_category=RiskCategory.SUPPORT,
        )
        d = r.model_dump()
        assert d["status"] == "unknown"
        assert d["eol_reason"] == "community_data"
        assert d["risk_category"] == "support"
        r2 = EOLResult.model_validate(d)
        assert r2.status == EOLStatus.UNKNOWN
        assert r2.model == m
        assert r2.eol_reason == EOLReason.COMMUNITY_DATA
        assert r2.risk_category == RiskCategory.SUPPORT
