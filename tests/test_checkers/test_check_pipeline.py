"""Tests for the check pipeline result selection logic."""

from datetime import date, datetime

from eol_tool.check_pipeline import select_best_result
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
