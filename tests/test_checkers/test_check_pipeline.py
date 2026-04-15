"""Tests for the check pipeline result selection logic."""

from datetime import date, datetime

from eol_tool.check_pipeline import _clean_intel_item_for_ark, select_best_result
from eol_tool.models import EOLResult, EOLStatus, HardwareModel


def _make_model(name: str = "TEST-MODEL") -> HardwareModel:
    return HardwareModel(model=name, manufacturer="TestMfr", category="switch")


def _make_result(
    *,
    status: EOLStatus = EOLStatus.EOL,
    eol_date: date | None = None,
    confidence: int = 80,
    priority: int = 50,
    source: str = "test",
) -> EOLResult:
    return EOLResult(
        model=_make_model(),
        status=status,
        eol_date=eol_date,
        checked_at=datetime.now(),
        source_name=source,
        confidence=confidence,
        checker_priority=priority,
    )


class TestDatedBeatsDaterless:
    """Dated results should always be preferred over dateless ones."""

    def test_dated_wins_over_dateless(self):
        dated = _make_result(
            eol_date=date(2024, 1, 1), confidence=50, priority=40,
        )
        dateless = _make_result(confidence=90, priority=20)

        best = select_best_result([dateless, dated])
        assert best.eol_date == date(2024, 1, 1)

    def test_dated_wins_even_with_worse_priority(self):
        dated = _make_result(
            eol_date=date(2024, 6, 1), priority=60, confidence=70,
        )
        dateless = _make_result(priority=10, confidence=100)

        best = select_best_result([dateless, dated])
        assert best.eol_date is not None


class TestPriorityAmongDated:
    """Among dated results, lower checker_priority wins."""

    def test_lower_priority_wins(self):
        high_pri = _make_result(
            eol_date=date(2024, 1, 1), priority=20, confidence=80,
        )
        low_pri = _make_result(
            eol_date=date(2023, 6, 1), priority=40, confidence=80,
        )

        best = select_best_result([low_pri, high_pri])
        assert best.checker_priority == 20

    def test_confidence_breaks_tie_among_dated(self):
        a = _make_result(
            eol_date=date(2024, 1, 1), priority=30, confidence=90,
        )
        b = _make_result(
            eol_date=date(2023, 6, 1), priority=30, confidence=70,
        )

        best = select_best_result([b, a])
        assert best.confidence == 90


class TestNotFoundFiltering:
    """NOT_FOUND results should be filtered out when actionable results exist."""

    def test_not_found_filtered_when_actionable_exists(self):
        nf = _make_result(status=EOLStatus.NOT_FOUND, confidence=100, priority=10)
        eol = _make_result(status=EOLStatus.EOL, confidence=50, priority=40)

        best = select_best_result([nf, eol])
        assert best.status == EOLStatus.EOL

    def test_unknown_filtered_when_actionable_exists(self):
        unk = _make_result(status=EOLStatus.UNKNOWN, confidence=100, priority=10)
        active = _make_result(status=EOLStatus.ACTIVE, confidence=50, priority=40)

        best = select_best_result([unk, active])
        assert best.status == EOLStatus.ACTIVE


class TestAllNotFound:
    """When all results are NOT_FOUND, should return NOT_FOUND."""

    def test_all_not_found(self):
        results = [
            _make_result(status=EOLStatus.NOT_FOUND, source="a"),
            _make_result(status=EOLStatus.NOT_FOUND, source="b"),
        ]
        best = select_best_result(results)
        assert best.status == EOLStatus.NOT_FOUND

    def test_unknown_preferred_over_not_found(self):
        results = [
            _make_result(status=EOLStatus.NOT_FOUND, source="a"),
            _make_result(status=EOLStatus.UNKNOWN, source="b"),
        ]
        best = select_best_result(results)
        assert best.status == EOLStatus.UNKNOWN

    def test_empty_results(self):
        best = select_best_result([])
        assert best.status == EOLStatus.NOT_FOUND


class TestDatelessSelection:
    """When no dated results exist, select among dateless by priority then confidence."""

    def test_dateless_priority_then_confidence(self):
        a = _make_result(status=EOLStatus.EOL, priority=20, confidence=70)
        b = _make_result(status=EOLStatus.EOL, priority=40, confidence=90)

        best = select_best_result([b, a])
        assert best.checker_priority == 20

    def test_dateless_confidence_breaks_tie(self):
        a = _make_result(status=EOLStatus.ACTIVE, priority=40, confidence=90)
        b = _make_result(status=EOLStatus.ACTIVE, priority=40, confidence=60)

        best = select_best_result([b, a])
        assert best.confidence == 90


class TestCleanIntelItemForArk:
    """Test the Intel item string cleaner for ARK search terms."""

    # --- CPU: Scalable Xeon patterns ---

    def test_silver_xeon_reversed(self):
        assert _clean_intel_item_for_ark("4110 SILVER XEON") == (
            "Intel Xeon Silver 4110 Processor"
        )

    def test_gold_xeon_reversed(self):
        assert _clean_intel_item_for_ark("6132 GOLD XEON") == (
            "Intel Xeon Gold 6132 Processor"
        )

    def test_gold_xeon_with_suffix(self):
        assert _clean_intel_item_for_ark("6132 GOLD XEON 20C CPU") == (
            "Intel Xeon Gold 6132 Processor"
        )

    def test_intel_prefix_gold_xeon(self):
        assert _clean_intel_item_for_ark("INTEL 6132 GOLD XEON") == (
            "Intel Xeon Gold 6132 Processor"
        )

    def test_xeon_model_tier(self):
        assert _clean_intel_item_for_ark("XEON 6226R GOLD") == (
            "Intel Xeon Gold 6226R Processor"
        )

    def test_already_correct_format(self):
        assert _clean_intel_item_for_ark("INTEL XEON SILVER 4310") == (
            "Intel Xeon Silver 4310 Processor"
        )

    def test_bare_tier_model(self):
        assert _clean_intel_item_for_ark("SILVER 4310") == (
            "Intel Xeon Silver 4310 Processor"
        )

    # --- CPU: E-series ---

    def test_e3_with_version(self):
        assert _clean_intel_item_for_ark("E3-1230 V5") == (
            "Intel Xeon E3-1230 V5 Processor"
        )

    def test_e2_series(self):
        assert _clean_intel_item_for_ark("INTEL XEON E-2276G") == (
            "Intel Xeon E-2276G Processor"
        )

    def test_e2_bare(self):
        assert _clean_intel_item_for_ark("E-2136") == (
            "Intel Xeon E-2136 Processor"
        )

    def test_e5_series(self):
        assert _clean_intel_item_for_ark("E5-2683V4") == (
            "Intel Xeon E5-2683V4 Processor"
        )

    # --- SSD patterns ---

    def test_ssd_d3_with_capacity(self):
        assert _clean_intel_item_for_ark("960GB INT D3-S4510 960GB SSD") == (
            "Intel SSD D3-S4510"
        )

    def test_ssd_p4_series(self):
        assert _clean_intel_item_for_ark("2TB INT P4510 U.2") == (
            "Intel SSD DC P4510"
        )

    def test_ssd_s3_series(self):
        assert _clean_intel_item_for_ark("480GB INT S3510") == (
            "Intel SSD DC S3510"
        )

    def test_ssd_520_series(self):
        assert _clean_intel_item_for_ark("480GB INT 520") == (
            "Intel SSD 520 Series"
        )

    def test_ssd_660p(self):
        assert _clean_intel_item_for_ark("1TB INT 660P") == (
            "Intel SSD 660P Series"
        )

    # --- NIC patterns ---

    def test_nic_x722(self):
        assert _clean_intel_item_for_ark("INT X722-DA4 10GB/S QUAD") == (
            "Intel Ethernet X722-DA4"
        )

    def test_nic_x520(self):
        assert _clean_intel_item_for_ark("INT X520-DA2") == (
            "Intel Ethernet X520-DA2"
        )

    def test_nic_i350(self):
        assert _clean_intel_item_for_ark("INTEL I350-T4") == (
            "Intel Ethernet I350-T4"
        )

    # --- RAID ---

    def test_raid_expander(self):
        assert _clean_intel_item_for_ark("INT RAID EXPANDER RES2SV240") == (
            "Intel RAID Expander RES2SV240"
        )

    # --- Edge cases ---

    def test_capacity_prefix_stripped(self):
        assert _clean_intel_item_for_ark("1.2TB INT D3-S4510") == (
            "Intel SSD D3-S4510"
        )

    def test_fallback_adds_intel_prefix(self):
        result = _clean_intel_item_for_ark("SOME UNKNOWN MODEL")
        assert result.startswith("Intel ")
