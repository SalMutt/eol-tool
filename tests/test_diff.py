"""Tests for the diff reporting module."""

import json
from datetime import date, datetime

import pytest
from click.testing import CliRunner

from eol_tool.cli import cli
from eol_tool.diff import compare_results, format_diff_json, format_diff_text, has_critical_changes
from eol_tool.models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory
from eol_tool.reader import write_results


def _make_v1_results() -> list[EOLResult]:
    now = datetime(2025, 6, 1, 12, 0, 0)
    return [
        EOLResult(
            model=HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch"),
            status=EOLStatus.ACTIVE,
            eol_date=None,
            checked_at=now,
            confidence=90,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="juniper",
        ),
        EOLResult(
            model=HardwareModel(model="PM883", manufacturer="Samsung", category="ssd"),
            status=EOLStatus.UNKNOWN,
            checked_at=now,
            confidence=50,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="samsung",
        ),
        EOLResult(
            model=HardwareModel(
                model="KSM64R52BD4", manufacturer="Kingston", category="memory",
            ),
            status=EOLStatus.UNKNOWN,
            checked_at=now,
            confidence=30,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="kingston",
        ),
        EOLResult(
            model=HardwareModel(model="XEON E5-2680V4", manufacturer="Intel", category="cpu"),
            status=EOLStatus.EOL,
            eol_date=date(2022, 10, 1),
            checked_at=now,
            confidence=95,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.INFORMATIONAL,
            source_name="intel",
        ),
        EOLResult(
            model=HardwareModel(model="MX204", manufacturer="Juniper", category="router"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=85,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="juniper",
        ),
        EOLResult(
            model=HardwareModel(model="WS-C3750X-48T", manufacturer="Cisco", category="switch"),
            status=EOLStatus.EOL,
            eol_date=date(2020, 7, 31),
            checked_at=now,
            confidence=95,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SECURITY,
            source_name="cisco",
        ),
        EOLResult(
            model=HardwareModel(model="ST4000NM0035", manufacturer="Seagate", category="hdd"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=70,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="seagate",
        ),
        EOLResult(
            model=HardwareModel(model="X11SPL-F", manufacturer="Supermicro", category="mainboard"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=80,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="supermicro",
        ),
        EOLResult(
            model=HardwareModel(model="PM1643A", manufacturer="Samsung", category="ssd"),
            status=EOLStatus.EOL,
            checked_at=now,
            confidence=85,
            eol_reason=EOLReason.COMMUNITY_DATA,
            risk_category=RiskCategory.SUPPORT,
            source_name="endoflife.date",
        ),
        EOLResult(
            model=HardwareModel(model="MTFDDAK960TDS", manufacturer="Micron", category="ssd"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=75,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="micron",
        ),
    ]


def _make_v2_results() -> list[EOLResult]:
    """Same 10 models but with specific changes:

    1. EX4300-48T: active -> eol (status change, critical)
    2. KSM64R52BD4: unknown -> active (status change, info)
    3. PM1643A: eol gains an eol_date (new_eol_date)
    4. XEON E5-2680V4: risk informational -> security (risk_escalation)
    5. MCX516A-CDAT (Mellanox): new model added
    6. MTFDDAK960TDS (Micron): removed
    """
    now = datetime(2025, 6, 15, 12, 0, 0)
    return [
        EOLResult(
            model=HardwareModel(model="EX4300-48T", manufacturer="Juniper", category="switch"),
            status=EOLStatus.EOL,
            eol_date=date(2025, 6, 1),
            checked_at=now,
            confidence=95,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SECURITY,
            source_name="juniper",
        ),
        EOLResult(
            model=HardwareModel(model="PM883", manufacturer="Samsung", category="ssd"),
            status=EOLStatus.UNKNOWN,
            checked_at=now,
            confidence=50,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="samsung",
        ),
        EOLResult(
            model=HardwareModel(
                model="KSM64R52BD4", manufacturer="Kingston", category="memory",
            ),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=80,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="kingston",
        ),
        EOLResult(
            model=HardwareModel(model="XEON E5-2680V4", manufacturer="Intel", category="cpu"),
            status=EOLStatus.EOL,
            eol_date=date(2022, 10, 1),
            checked_at=now,
            confidence=95,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SECURITY,
            source_name="intel",
        ),
        EOLResult(
            model=HardwareModel(model="MX204", manufacturer="Juniper", category="router"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=85,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="juniper",
        ),
        EOLResult(
            model=HardwareModel(model="WS-C3750X-48T", manufacturer="Cisco", category="switch"),
            status=EOLStatus.EOL,
            eol_date=date(2020, 7, 31),
            checked_at=now,
            confidence=95,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SECURITY,
            source_name="cisco",
        ),
        EOLResult(
            model=HardwareModel(model="ST4000NM0035", manufacturer="Seagate", category="hdd"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=70,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="seagate",
        ),
        EOLResult(
            model=HardwareModel(model="X11SPL-F", manufacturer="Supermicro", category="mainboard"),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=80,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="supermicro",
        ),
        EOLResult(
            model=HardwareModel(model="PM1643A", manufacturer="Samsung", category="ssd"),
            status=EOLStatus.EOL,
            eol_date=date(2024, 12, 31),
            checked_at=now,
            confidence=90,
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SUPPORT,
            source_name="endoflife.date",
        ),
        EOLResult(
            model=HardwareModel(
                model="MCX516A-CDAT", manufacturer="Mellanox", category="network",
            ),
            status=EOLStatus.ACTIVE,
            checked_at=now,
            confidence=80,
            eol_reason=EOLReason.NONE,
            risk_category=RiskCategory.NONE,
            source_name="endoflife.date",
        ),
    ]


@pytest.fixture(scope="session")
def diff_fixtures(tmp_path_factory):
    """Create v1 and v2 test xlsx files for diff comparison."""
    tmpdir = tmp_path_factory.mktemp("diff_fixtures")
    v1_path = tmpdir / "results_v1.xlsx"
    v2_path = tmpdir / "results_v2.xlsx"
    write_results(_make_v1_results(), v1_path)
    write_results(_make_v2_results(), v2_path)
    return v1_path, v2_path


@pytest.fixture(scope="session")
def diff_result(diff_fixtures):
    """Pre-computed diff result for the v1 -> v2 comparison."""
    v1, v2 = diff_fixtures
    return compare_results(str(v1), str(v2))


class TestCompareResultsDetection:
    """Tests that compare_results detects all expected changes."""

    def test_detects_all_six_changes(self, diff_result):
        assert diff_result.summary.total_changes == 6

    def test_active_to_eol_counted(self, diff_result):
        assert diff_result.summary.active_to_eol == 1

    def test_unknown_to_active_counted(self, diff_result):
        assert diff_result.summary.unknown_to_active == 1

    def test_new_eol_dates_counted(self, diff_result):
        assert diff_result.summary.new_eol_dates == 1

    def test_risk_escalations_counted(self, diff_result):
        assert diff_result.summary.risk_escalations == 1

    def test_new_models_counted(self, diff_result):
        assert diff_result.summary.new_models == 1

    def test_removed_models_counted(self, diff_result):
        assert diff_result.summary.removed_models == 1

    def test_previous_count(self, diff_result):
        assert diff_result.previous_count == 10

    def test_current_count(self, diff_result):
        assert diff_result.current_count == 10


class TestSeverityAssignment:
    """Tests that severity is assigned correctly per the rules."""

    def test_active_to_eol_is_critical(self, diff_result):
        active_eol = [
            e for e in diff_result.changes
            if e.change_type == "status_change" and e.previous_status == "active"
            and e.current_status == "eol"
        ]
        assert len(active_eol) == 1
        assert active_eol[0].severity == "critical"
        assert active_eol[0].model == "EX4300-48T"

    def test_risk_to_security_is_critical(self, diff_result):
        escalations = [
            e for e in diff_result.changes
            if e.change_type == "risk_escalation" and e.current_risk == "security"
        ]
        assert len(escalations) == 1
        assert escalations[0].severity == "critical"

    def test_unknown_to_active_is_info(self, diff_result):
        ua = [
            e for e in diff_result.changes
            if e.change_type == "status_change" and e.previous_status == "unknown"
            and e.current_status == "active"
        ]
        assert len(ua) == 1
        assert ua[0].severity == "info"

    def test_new_model_is_info(self, diff_result):
        new = [e for e in diff_result.changes if e.change_type == "new_model"]
        assert all(e.severity == "info" for e in new)

    def test_removed_model_is_info(self, diff_result):
        removed = [e for e in diff_result.changes if e.change_type == "removed_model"]
        assert all(e.severity == "info" for e in removed)

    def test_changes_sorted_critical_first(self, diff_result):
        severities = [e.severity for e in diff_result.changes]
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        numeric = [severity_order[s] for s in severities]
        assert numeric == sorted(numeric)


class TestFormatDiffText:
    """Tests for the text formatter."""

    def test_contains_critical_label(self, diff_result):
        text = format_diff_text(diff_result)
        assert "CRITICAL" in text

    def test_contains_expected_model(self, diff_result):
        text = format_diff_text(diff_result)
        assert "EX4300-48T" in text

    def test_contains_change_count(self, diff_result):
        text = format_diff_text(diff_result)
        assert "6 changes detected" in text

    def test_compact_under_500_chars(self, diff_result):
        text = format_diff_text(diff_result, verbose=False)
        assert len(text) < 500

    def test_verbose_longer_than_compact(self, diff_result):
        compact = format_diff_text(diff_result, verbose=False)
        verbose = format_diff_text(diff_result, verbose=True)
        assert len(verbose) > len(compact)

    def test_contains_summary_line(self, diff_result):
        text = format_diff_text(diff_result)
        assert "Summary:" in text


class TestFormatDiffJson:
    """Tests for the JSON formatter."""

    def test_produces_valid_json(self, diff_result):
        raw = format_diff_json(diff_result)
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_json_has_expected_keys(self, diff_result):
        parsed = json.loads(format_diff_json(diff_result))
        assert "summary" in parsed
        assert "changes" in parsed
        assert "timestamp" in parsed
        assert "previous_file" in parsed
        assert "current_file" in parsed

    def test_json_roundtrip(self, diff_result):
        from eol_tool.diff import DiffResult

        raw = format_diff_json(diff_result)
        restored = DiffResult.model_validate_json(raw)
        assert restored.summary.total_changes == diff_result.summary.total_changes
        assert len(restored.changes) == len(diff_result.changes)


class TestEmptyDiff:
    """Tests for comparing identical files."""

    def test_identical_files_zero_changes(self, diff_fixtures):
        v1, _ = diff_fixtures
        result = compare_results(str(v1), str(v1))
        assert result.summary.total_changes == 0
        assert len(result.changes) == 0

    def test_empty_diff_text(self, diff_fixtures):
        v1, _ = diff_fixtures
        result = compare_results(str(v1), str(v1))
        text = format_diff_text(result)
        assert "No changes detected" in text


class TestHasCriticalChanges:
    """Tests for the critical change detection helper."""

    def test_returns_true_when_critical(self, diff_result):
        assert has_critical_changes(diff_result) is True

    def test_returns_false_when_no_critical(self, diff_fixtures):
        v1, _ = diff_fixtures
        result = compare_results(str(v1), str(v1))
        assert has_critical_changes(result) is False


class TestCliDiffCommand:
    """Tests for the CLI diff command."""

    def test_diff_command_text_output(self, diff_fixtures):
        v1, v2 = diff_fixtures
        runner = CliRunner()
        result = runner.invoke(cli, ["diff", "--previous", str(v1), "--current", str(v2)])
        assert "changes detected" in result.output
        # Exit code 1 because there are critical changes
        assert result.exit_code == 1

    def test_diff_command_json_output(self, diff_fixtures):
        v1, v2 = diff_fixtures
        runner = CliRunner()
        result = runner.invoke(
            cli, ["diff", "--previous", str(v1), "--current", str(v2), "--format", "json"]
        )
        parsed = json.loads(result.output)
        assert parsed["summary"]["total_changes"] == 6
        assert result.exit_code == 1

    def test_diff_command_no_critical_exit_0(self, diff_fixtures):
        v1, _ = diff_fixtures
        runner = CliRunner()
        result = runner.invoke(cli, ["diff", "--previous", str(v1), "--current", str(v1)])
        assert result.exit_code == 0

    def test_diff_command_writes_to_file(self, diff_fixtures, tmp_path):
        v1, v2 = diff_fixtures
        out_file = tmp_path / "diff_output.txt"
        runner = CliRunner()
        runner.invoke(
            cli,
            ["diff", "--previous", str(v1), "--current", str(v2), "--output", str(out_file)],
        )
        assert out_file.exists()
        content = out_file.read_text()
        assert "changes detected" in content

    def test_diff_command_verbose(self, diff_fixtures):
        v1, v2 = diff_fixtures
        runner = CliRunner()
        result = runner.invoke(
            cli, ["diff", "--previous", str(v1), "--current", str(v2), "--verbose"]
        )
        assert "EX4300-48T" in result.output
