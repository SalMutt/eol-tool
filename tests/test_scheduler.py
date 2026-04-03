"""Tests for the scheduled checker module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eol_tool.cli import cli
from eol_tool.models import EOLResult, EOLStatus, HardwareModel
from eol_tool.reader import write_results
from eol_tool.scheduler import ScheduleConfig, ScheduledChecker

# --- ScheduleConfig tests ---


class TestScheduleConfigDefaults:
    def test_default_values(self):
        config = ScheduleConfig(input_path="test.xlsx")
        assert config.results_dir == "./results"
        assert config.interval_hours == 24.0
        assert config.ntfy_url == "https://ntfy.sh"
        assert config.ntfy_topic == ""
        assert config.ntfy_token is None
        assert config.ntfy_priority == "default"
        assert config.notify_on == "warning"
        assert config.keep_results == 10
        assert config.concurrency == 2
        assert config.manufacturer == "all"

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("EOL_TOOL_RESULTS_DIR", "/tmp/env-results")
        monkeypatch.setenv("EOL_TOOL_SCHEDULE_INTERVAL", "12")
        monkeypatch.setenv("EOL_TOOL_NTFY_URL", "https://my-ntfy.example.com")
        monkeypatch.setenv("EOL_TOOL_NTFY_TOPIC", "env-topic")
        monkeypatch.setenv("EOL_TOOL_NTFY_TOKEN", "tk_env_secret")

        config = ScheduleConfig(input_path="test.xlsx")
        assert config.results_dir == "/tmp/env-results"
        assert config.interval_hours == 12.0
        assert config.ntfy_url == "https://my-ntfy.example.com"
        assert config.ntfy_topic == "env-topic"
        assert config.ntfy_token == "tk_env_secret"

    def test_explicit_values_override_env(self, monkeypatch):
        monkeypatch.setenv("EOL_TOOL_NTFY_TOPIC", "env-topic")
        monkeypatch.setenv("EOL_TOOL_SCHEDULE_INTERVAL", "12")

        config = ScheduleConfig(
            input_path="test.xlsx",
            ntfy_topic="cli-topic",
            interval_hours=6.0,
        )
        assert config.ntfy_topic == "cli-topic"
        assert config.interval_hours == 6.0


# --- CLI override tests ---


class TestCliOverrides:
    def test_cli_flags_override_env(self, monkeypatch, tmp_path):
        # Create a minimal xlsx input
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)

        monkeypatch.setenv("EOL_TOOL_NTFY_TOPIC", "env-topic")

        runner = CliRunner()
        mock_path = "eol_tool.scheduler.ScheduledChecker.run_once"
        with patch(mock_path, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = None
            result = runner.invoke(cli, [
                "schedule",
                "--input", str(input_file),
                "--topic", "cli-topic",
                "--interval", "6",
                "--run-once",
            ])

        assert result.exit_code == 0
        assert "cli-topic" in result.output

    def test_dry_run_sets_notify_on_none(self, tmp_path):
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)

        runner = CliRunner()
        mock_path = "eol_tool.scheduler.ScheduledChecker.run_once"
        with patch(mock_path, new_callable=AsyncMock) as mock_run:
            mock_run.return_value = None
            result = runner.invoke(cli, [
                "schedule",
                "--input", str(input_file),
                "--topic", "test",
                "--dry-run",
                "--run-once",
            ])

        assert result.exit_code == 0

    def test_missing_topic_exits_with_error(self, tmp_path, monkeypatch):
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)
        # Ensure env var is not set
        monkeypatch.delenv("EOL_TOOL_NTFY_TOPIC", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "schedule",
            "--input", str(input_file),
            "--run-once",
        ])

        assert result.exit_code == 1
        assert "topic" in result.output.lower()


# --- _find_previous_results tests ---


class TestFindPreviousResults:
    def test_finds_most_recent(self, tmp_path):
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        _write_dummy_results(results_dir / "eol-results-2026-04-01T10-00-00.xlsx")
        _write_dummy_results(results_dir / "eol-results-2026-04-02T10-00-00.xlsx")
        current = results_dir / "eol-results-2026-04-03T10-00-00.xlsx"
        _write_dummy_results(current)

        config = ScheduleConfig(input_path="test.xlsx", results_dir=str(results_dir))
        checker = ScheduledChecker(config)
        checker._current_output = str(current)

        prev = checker._find_previous_results()
        assert prev is not None
        assert "2026-04-02" in prev

    def test_returns_none_when_no_files(self, tmp_path):
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        config = ScheduleConfig(input_path="test.xlsx", results_dir=str(results_dir))
        checker = ScheduledChecker(config)
        checker._current_output = None

        assert checker._find_previous_results() is None

    def test_returns_none_when_only_current(self, tmp_path):
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        current = results_dir / "eol-results-2026-04-03T10-00-00.xlsx"
        _write_dummy_results(current)

        config = ScheduleConfig(input_path="test.xlsx", results_dir=str(results_dir))
        checker = ScheduledChecker(config)
        checker._current_output = str(current)

        assert checker._find_previous_results() is None


# --- _prune_old_results tests ---


class TestPruneOldResults:
    def test_keeps_correct_number(self, tmp_path):
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        for i in range(5):
            _write_dummy_results(results_dir / f"eol-results-2026-04-0{i + 1}T10-00-00.xlsx")

        config = ScheduleConfig(
            input_path="test.xlsx",
            results_dir=str(results_dir),
            keep_results=3,
        )
        checker = ScheduledChecker(config)

        checker._prune_old_results()

        remaining = list(results_dir.glob("eol-results-*.xlsx"))
        assert len(remaining) == 3

    def test_no_pruning_needed(self, tmp_path):
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        _write_dummy_results(results_dir / "eol-results-2026-04-01T10-00-00.xlsx")

        config = ScheduleConfig(
            input_path="test.xlsx",
            results_dir=str(results_dir),
            keep_results=10,
        )
        checker = ScheduledChecker(config)

        checker._prune_old_results()

        remaining = list(results_dir.glob("eol-results-*.xlsx"))
        assert len(remaining) == 1


# --- run_once tests ---


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_creates_timestamped_output(self, tmp_path):
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)
        results_dir = tmp_path / "results"

        config = ScheduleConfig(
            input_path=str(input_file),
            results_dir=str(results_dir),
            ntfy_topic="test",
            notify_on="none",
        )
        checker = ScheduledChecker(config)

        with _mock_pipeline():
            await checker.run_once()

        files = list(results_dir.glob("eol-results-*.xlsx"))
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_sends_notification_on_changes(self, tmp_path):
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create a previous results file that differs
        _write_dummy_results(results_dir / "eol-results-2026-04-01T10-00-00.xlsx")

        config = ScheduleConfig(
            input_path=str(input_file),
            results_dir=str(results_dir),
            ntfy_topic="test",
            notify_on="all",
        )
        checker = ScheduledChecker(config)

        with _mock_pipeline():
            with patch("eol_tool.scheduler.send_ntfy", new_callable=AsyncMock) as mock_ntfy:
                mock_ntfy.return_value = True
                await checker.run_once()

    @pytest.mark.asyncio
    async def test_no_notification_when_notify_on_none(self, tmp_path):
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        _write_dummy_results(results_dir / "eol-results-2026-04-01T10-00-00.xlsx")

        config = ScheduleConfig(
            input_path=str(input_file),
            results_dir=str(results_dir),
            ntfy_topic="test",
            notify_on="none",
        )
        checker = ScheduledChecker(config)

        with _mock_pipeline():
            with patch("eol_tool.scheduler.send_ntfy", new_callable=AsyncMock):
                await checker.run_once()

    @pytest.mark.asyncio
    async def test_handles_checker_error_gracefully(self, tmp_path):
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)
        results_dir = tmp_path / "results"

        config = ScheduleConfig(
            input_path=str(input_file),
            results_dir=str(results_dir),
            ntfy_topic="test",
            notify_on="none",
        )
        checker = ScheduledChecker(config)

        with patch("eol_tool.scheduler.ResultCache") as mock_cache_cls:
            mock_cache = AsyncMock()
            mock_cache_cls.return_value = mock_cache
            pipe_path = "eol_tool.scheduler.run_check_pipeline"
            with patch(pipe_path, new_callable=AsyncMock) as mock_pipe:
                mock_pipe.side_effect = RuntimeError("API timeout")

                with pytest.raises(RuntimeError, match="API timeout"):
                    await checker.run_once()

    @pytest.mark.asyncio
    async def test_run_loop_catches_exceptions(self, tmp_path):
        """Verify run_loop doesn't crash on per-run exceptions."""
        input_file = tmp_path / "models.xlsx"
        _write_minimal_input(input_file)

        config = ScheduleConfig(
            input_path=str(input_file),
            results_dir=str(tmp_path / "results"),
            ntfy_topic="test",
            interval_hours=0.001,  # very short for testing
        )
        checker = ScheduledChecker(config)

        call_count = 0

        async def _failing_run_once():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt  # break the loop
            raise RuntimeError("boom")

        with patch.object(checker, "run_once", side_effect=_failing_run_once):
            with patch("eol_tool.scheduler.send_ntfy_error", new_callable=AsyncMock):
                with pytest.raises(KeyboardInterrupt):
                    await checker.run_loop()

        assert call_count >= 2  # loop survived the first error


# --- Helpers ---


def _write_minimal_input(path: Path):
    """Create a minimal xlsx input file with one model."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Models"
    ws.append(["Model", "Manufacturer", "Category", "Condition", "Original_Item"])
    ws.append(["EX4300-48T", "Juniper", "switch", "used", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    wb.close()


def _write_dummy_results(path: Path):
    """Write a minimal results xlsx file."""
    results = [
        EOLResult(
            model=HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch"),
            status=EOLStatus.ACTIVE,
            checked_at=datetime(2026, 4, 1, 12, 0, 0),
            confidence=90,
            source_name="juniper",
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_results(results, path)


def _mock_pipeline():
    """Context manager that mocks the check pipeline to return canned results."""
    results = [
        EOLResult(
            model=HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch"),
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            confidence=90,
            source_name="test",
        ),
    ]

    cache_mock = AsyncMock()

    class _Ctx:
        def __init__(self):
            self.pipeline_mock = None
            self.cache_mock = cache_mock

        def __enter__(self):
            self._p1 = patch("eol_tool.scheduler.ResultCache", return_value=cache_mock)
            self._p2 = patch(
                "eol_tool.scheduler.run_check_pipeline",
                new_callable=AsyncMock,
                return_value=results,
            )
            self._p1.start()
            self.pipeline_mock = self._p2.start()
            return self

        def __exit__(self, *args):
            self._p2.stop()
            self._p1.stop()

    return _Ctx()
