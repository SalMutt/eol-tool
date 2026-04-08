"""Tests for CLI logging configuration."""

import logging

from click.testing import CliRunner

from eol_tool.cli import cli


def test_default_log_level_is_warning():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-checkers"])
    assert result.exit_code == 0
    root = logging.getLogger()
    assert root.level == logging.WARNING


def test_log_level_debug():
    runner = CliRunner()
    result = runner.invoke(cli, ["--log-level", "debug", "list-checkers"])
    assert result.exit_code == 0
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_verbose_sets_info():
    runner = CliRunner()
    result = runner.invoke(cli, ["-v", "list-checkers"])
    assert result.exit_code == 0
    root = logging.getLogger()
    assert root.level == logging.INFO


def test_log_level_overrides_verbose():
    runner = CliRunner()
    result = runner.invoke(cli, ["-v", "--log-level", "error", "list-checkers"])
    assert result.exit_code == 0
    root = logging.getLogger()
    assert root.level == logging.ERROR
