"""Tests for CLI commands."""

from datetime import datetime
from pathlib import Path

import openpyxl
from click.testing import CliRunner

from eol_tool.checker import BaseChecker
from eol_tool.cli import cli
from eol_tool.models import EOLResult, EOLStatus, HardwareModel


class _FakeChecker(BaseChecker):
    manufacturer_name = "testmfr"
    rate_limit = 10

    async def check(self, model: HardwareModel) -> EOLResult:
        return EOLResult(
            model=model,
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            source_name="fake",
            confidence=90,
        )


def _write_test_xlsx(path: Path, rows: list[tuple[str, str, str]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Models"
    ws.append(["Model", "Manufacturer", "Category", "Condition", "Original_Item"])
    for model, mfr, cat in rows:
        ws.append([model, mfr, cat, "", ""])
    wb.save(path)
    wb.close()


def _write_results_xlsx(path: Path, results_data):
    """Write a results xlsx for diff/retry tests."""
    from eol_tool.reader import write_results

    now = datetime(2025, 6, 1, 12, 0, 0)
    results = []
    for model, mfr, cat, status in results_data:
        results.append(
            EOLResult(
                model=HardwareModel(model=model, manufacturer=mfr, category=cat),
                status=status,
                checked_at=now,
                confidence=80,
            )
        )
    write_results(results, path)


class TestTopLevelHelp:
    def test_help_returns_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_help_shows_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "check" in result.output
        assert "list-checkers" in result.output
        assert "cache" in result.output


class TestCheckHelp:
    def test_check_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        for opt in ("--retry-unknowns", "--diff", "--show-filtered", "--dry-run"):
            assert opt in result.output


class TestDiffHelp:
    def test_diff_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diff", "--help"])
        assert result.exit_code == 0
        for opt in ("--previous", "--current", "--format", "--verbose", "--output"):
            assert opt in result.output


class TestScheduleHelp:
    def test_schedule_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["schedule", "--help"])
        assert result.exit_code == 0
        for opt in ("--topic", "--interval", "--notify-on", "--run-once"):
            assert opt in result.output


class TestNotifyHelp:
    def test_notify_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["notify", "--help"])
        assert result.exit_code == 0
        for opt in ("--topic", "--message", "--priority"):
            assert opt in result.output


class TestListCheckers:
    def test_returns_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["list-checkers"])
        assert result.exit_code == 0

    def test_lists_checker_names(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["list-checkers"])
        # Should list at least the manual and fallback checkers
        assert "__manual__" in result.output or "__fallback__" in result.output


class TestCacheStats:
    def test_cache_stats_returns_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cache", "stats"])
        assert result.exit_code == 0
        assert "Total cached results" in result.output


class TestCheckDryRun:
    def test_dry_run_prints_summary(self, tmp_path):
        input_path = tmp_path / "input.xlsx"
        _write_test_xlsx(input_path, [
            ("EX4300-48T", "Juniper", "switch"),
            ("E5-2680V4", "Intel", "cpu"),
        ])
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "--input", str(input_path), "--dry-run"])
        assert result.exit_code == 0
        assert "Loaded 2 models" in result.output
        assert "--dry-run" in result.output

    def test_dry_run_shows_manufacturers(self, tmp_path):
        input_path = tmp_path / "input.xlsx"
        _write_test_xlsx(input_path, [
            ("EX4300-48T", "Juniper", "switch"),
            ("E5-2680V4", "Intel", "cpu"),
        ])
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "--input", str(input_path), "--dry-run"])
        assert "Manufacturers" in result.output
        assert "Juniper" in result.output
        assert "Intel" in result.output


class TestCheckRequiresInput:
    def test_check_without_input_errors(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check"])
        assert result.exit_code != 0
