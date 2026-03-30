"""Tests for checker registry."""

from eol_tool.checker import BaseChecker
from eol_tool.registry import get_checker, list_checkers


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
