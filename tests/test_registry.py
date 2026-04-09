"""Tests for checker registry."""

from eol_tool.checker import BaseChecker
from eol_tool.checkers.micron import MicronChecker
from eol_tool.registry import get_checker, get_checkers, list_checkers


class TestRegistry:
    def test_list_checkers_returns_dict(self):
        result = list_checkers()
        assert isinstance(result, dict)

    def test_get_checker_nonexistent(self):
        result = get_checker("nonexistent_vendor")
        assert result is None

    def test_template_not_registered(self):
        """The _template.py checker should not be auto-registered."""
        checkers = list_checkers()
        assert "template" not in checkers

    def test_all_checkers_are_subclasses(self):
        """All registered checkers should be BaseChecker subclasses."""
        for name, cls in list_checkers().items():
            assert issubclass(cls, BaseChecker)

    def test_get_checker_case_insensitive(self):
        """get_checker should be case-insensitive."""
        assert get_checker("NONEXISTENT") is None
        assert get_checker("Nonexistent") is None


class TestManufacturerAliases:
    def test_crucial_routes_to_micron(self):
        """Crucial models should be handled by the MicronChecker."""
        checker = get_checker("Crucial")
        assert checker is MicronChecker

    def test_crucial_in_get_checkers(self):
        checkers = get_checkers("Crucial")
        assert MicronChecker in checkers

    def test_micron_still_works(self):
        checker = get_checker("Micron")
        assert checker is MicronChecker
