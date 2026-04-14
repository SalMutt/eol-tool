"""Tests for generation-based date lookup and pipeline date fallback tiers."""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from eol_tool.check_pipeline import _strip_item_prefix, _tier3_generation_dates
from eol_tool.generation_dates import lookup_generation_dates, reset
from eol_tool.models import EOLResult, EOLStatus, HardwareModel


@pytest.fixture(autouse=True)
def _reset_gen_dates():
    """Ensure generation dates are reloaded fresh for each test."""
    reset()
    yield
    reset()


def _make_model(
    model: str = "TEST",
    manufacturer: str = "Intel",
    category: str = "cpu",
    original_item: str = "",
) -> HardwareModel:
    return HardwareModel(
        model=model,
        manufacturer=manufacturer,
        category=category,
        original_item=original_item,
    )


def _make_result(
    model: str = "TEST",
    manufacturer: str = "Intel",
    category: str = "cpu",
    release_date: date | None = None,
    eol_date: date | None = None,
    date_source: str = "none",
    notes: str = "",
    original_item: str = "",
) -> EOLResult:
    return EOLResult(
        model=_make_model(model, manufacturer, category, original_item),
        status=EOLStatus.UNKNOWN,
        checked_at=datetime.now(),
        source_name="test",
        release_date=release_date,
        eol_date=eol_date,
        date_source=date_source,
        notes=notes,
    )


class TestGenerationDatesLookup:
    """Test the generation_dates.lookup_generation_dates function."""

    def test_haswell_matches(self):
        result = lookup_generation_dates("E5-2683V3", "Haswell", "Intel", "cpu")
        assert result is not None
        assert result["pattern"] == "Haswell"
        assert result["release_date"] == date(2013, 6, 1)

    def test_ddr4_2666_dates(self):
        result = lookup_generation_dates(
            "M393A4K40CB2-CTD", "DDR4-2666", "Samsung", "memory"
        )
        assert result is not None
        assert result["pattern"] == "DDR4-2666"
        assert result["release_date"] == date(2017, 1, 1)

    def test_ddr3_dates(self):
        result = lookup_generation_dates("HMT351U7BFR8C", "DDR3", "SK Hynix", "memory")
        assert result is not None
        assert "DDR3" in result["pattern"]
        assert result["eol_estimate"] == date(2020, 12, 31)

    def test_connectx3_dates(self):
        result = lookup_generation_dates(
            "CX312A", "ConnectX-3", "Mellanox", "nic"
        )
        assert result is not None
        assert result["pattern"] == "ConnectX-3"
        assert result["release_date"] == date(2012, 1, 1)
        assert result["eol_estimate"] == date(2022, 12, 31)

    def test_supermicro_x10_dates(self):
        result = lookup_generation_dates("X10DRI-T", "", "Supermicro", "server-board")
        assert result is not None
        assert result["pattern"] == "X10"
        assert result["release_date"] == date(2014, 1, 1)

    def test_no_match_returns_none(self):
        result = lookup_generation_dates("UNKNOWN-MODEL-XYZ", "", "Unknown", "widget")
        assert result is None

    def test_longer_pattern_preferred(self):
        """DDR4-2666 should match over plain DDR4."""
        result = lookup_generation_dates("TEST DDR4-2666", "", "Samsung", "memory")
        assert result is not None
        assert result["pattern"] == "DDR4-2666"

    def test_intel_ssd_s3500(self):
        result = lookup_generation_dates("S3500", "Intel SSD S3500", "Intel", "ssd")
        assert result is not None
        assert result["release_date"] == date(2013, 7, 1)
        assert result["eol_estimate"] == date(2021, 12, 31)

    def test_ex4300_juniper(self):
        result = lookup_generation_dates("EX4300-48T", "", "Juniper", "switch")
        assert result is not None
        assert result["pattern"] == "EX4300"
        assert result["release_date"] == date(2013, 10, 1)

    def test_intel_mpn_prefix_cm8066(self):
        """Intel CPU MPN starting with CM8066 should match Broadwell-era dates."""
        result = lookup_generation_dates("CM8066002031103", "", "Intel", "cpu")
        assert result is not None
        assert result["pattern"] == "CM8066"
        assert result["release_date"] == date(2015, 6, 1)


class TestStripItemPrefix:
    """Test the _strip_item_prefix helper."""

    def test_full_prefix(self):
        assert _strip_item_prefix("PROCESSORS:NEW:Intel Xeon E3-1230 v5") == "INTEL XEON E3-1230 V5"

    def test_two_part_prefix(self):
        assert _strip_item_prefix("MEMORY:Samsung 32GB") == "SAMSUNG 32GB"

    def test_no_prefix(self):
        assert _strip_item_prefix("Intel Xeon E3-1230 v5") == "INTEL XEON E3-1230 V5"

    def test_empty_string(self):
        assert _strip_item_prefix("") == ""


class TestTier3GenerationDates:
    """Test Tier 3 generation date post-processing."""

    def test_fills_empty_dates(self):
        results = [
            _make_result(model="E5-2683V3", notes="Haswell", category="cpu"),
        ]
        _tier3_generation_dates(results)
        assert results[0].release_date == date(2013, 6, 1)
        assert results[0].eol_date == date(2019, 12, 31)
        assert results[0].date_source != "none"

    def test_does_not_overwrite_existing_release_date(self):
        existing_date = date(2018, 1, 15)
        results = [
            _make_result(
                model="E5-2683V3",
                notes="Haswell",
                category="cpu",
                release_date=existing_date,
            ),
        ]
        _tier3_generation_dates(results)
        # Has release_date already, so Tier 3 should NOT touch it
        assert results[0].release_date == existing_date
        assert results[0].eol_date is None  # unchanged

    def test_does_not_overwrite_existing_eol_date(self):
        existing_date = date(2020, 6, 30)
        results = [
            _make_result(
                model="E5-2683V3",
                notes="Haswell",
                category="cpu",
                eol_date=existing_date,
            ),
        ]
        _tier3_generation_dates(results)
        # Has eol_date already, so Tier 3 should NOT touch it
        assert results[0].eol_date == existing_date
        assert results[0].release_date is None  # unchanged

    def test_ddr4_memory_gets_dates(self):
        results = [
            _make_result(
                model="M393A4K40CB2-CTD",
                notes="DDR4-2666",
                manufacturer="Samsung",
                category="memory",
            ),
        ]
        _tier3_generation_dates(results)
        assert results[0].release_date is not None

    def test_no_match_leaves_result_unchanged(self):
        results = [
            _make_result(model="UNKNOWN-XYZ", notes="", manufacturer="Unknown"),
        ]
        _tier3_generation_dates(results)
        assert results[0].release_date is None
        assert results[0].eol_date is None
        assert results[0].date_source == "none"

    def test_notes_appended(self):
        results = [
            _make_result(
                model="EX4300-48T",
                notes="some-existing-note",
                manufacturer="Juniper",
                category="switch",
            ),
        ]
        _tier3_generation_dates(results)
        assert "generation-estimate:EX4300" in results[0].notes
        assert "some-existing-note" in results[0].notes


class TestTier2ItemFallback:
    """Test Tier 2 item string fallback integration."""

    @pytest.mark.asyncio
    async def test_item_fallback_fills_dates(self):
        """When MPN has no dates but original_item can match, dates are filled."""
        from eol_tool.check_pipeline import _tier2_item_fallback

        results = [
            _make_result(
                model="CM8066002031103",
                manufacturer="Intel",
                category="cpu",
                original_item="PROCESSORS:NEW:Intel Xeon E3-1230 v5",
            ),
        ]

        # Mock the EndOfLifeDateChecker to return a result with dates
        mock_date_result = EOLResult(
            model=results[0].model,
            status=EOLStatus.EOL,
            checked_at=datetime.now(),
            source_name="endoflife.date",
            release_date=date(2015, 10, 1),
            eol_date=date(2021, 6, 30),
            date_source="community_database",
        )

        with patch(
            "eol_tool.check_pipeline.EndOfLifeDateChecker"
        ) as MockChecker:
            instance = AsyncMock()
            instance.check_batch = AsyncMock(return_value=[mock_date_result])
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockChecker.return_value = instance

            updated = await _tier2_item_fallback(results)

        assert updated[0].release_date == date(2015, 10, 1)
        assert updated[0].eol_date == date(2021, 6, 30)
        assert updated[0].date_source == "community_database"
        assert "dates-from-item-string-fallback" in updated[0].notes

    @pytest.mark.asyncio
    async def test_item_fallback_skips_when_dates_exist(self):
        """Models that already have dates should not be retried."""
        from eol_tool.check_pipeline import _tier2_item_fallback

        results = [
            _make_result(
                model="CM8066002031103",
                manufacturer="Intel",
                category="cpu",
                release_date=date(2015, 10, 1),
                original_item="PROCESSORS:NEW:Intel Xeon E3-1230 v5",
            ),
        ]

        with patch(
            "eol_tool.check_pipeline.EndOfLifeDateChecker"
        ) as MockChecker:
            updated = await _tier2_item_fallback(results)
            # Should NOT have created a checker at all
            MockChecker.assert_not_called()

        assert updated[0].release_date == date(2015, 10, 1)

    @pytest.mark.asyncio
    async def test_item_fallback_skips_same_model(self):
        """If original_item matches model string, don't retry."""
        from eol_tool.check_pipeline import _tier2_item_fallback

        results = [
            _make_result(
                model="EX4300-48T",
                manufacturer="Juniper",
                category="switch",
                original_item="EX4300-48T",
            ),
        ]

        with patch(
            "eol_tool.check_pipeline.EndOfLifeDateChecker"
        ) as MockChecker:
            updated = await _tier2_item_fallback(results)
            MockChecker.assert_not_called()

        assert updated[0].release_date is None
