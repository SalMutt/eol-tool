"""Tests for the ntfy notification module."""

from datetime import datetime

import pytest

from eol_tool.diff import DiffEntry, DiffResult, DiffSummary
from eol_tool.notifier import _classify_diff_severity, _should_notify, send_ntfy, send_ntfy_error
from eol_tool.scheduler import ScheduleConfig


def _make_config(**kwargs):
    defaults = dict(
        input_path="test.xlsx",
        ntfy_url="https://ntfy.sh",
        ntfy_topic="test-topic",
        ntfy_token=None,
        notify_on="warning",
    )
    defaults.update(kwargs)
    return ScheduleConfig(**defaults)


def _make_diff(severities: list[str], total: int | None = None) -> DiffResult:
    changes = []
    for sev in severities:
        changes.append(
            DiffEntry(
                model="TEST-MODEL",
                manufacturer="TestMfr",
                category="switch",
                change_type="status_change",
                previous_status="active",
                current_status="eol",
                severity=sev,
                description=f"Test {sev} change",
            )
        )
    return DiffResult(
        timestamp=datetime.now(),
        previous_file="prev.xlsx",
        current_file="curr.xlsx",
        previous_count=10,
        current_count=10,
        summary=DiffSummary(total_changes=total if total is not None else len(changes)),
        changes=changes,
    )


class TestClassifyDiffSeverity:
    def test_critical_when_critical_present(self):
        diff = _make_diff(["info", "critical", "warning"])
        assert _classify_diff_severity(diff) == "critical"

    def test_warning_when_no_critical(self):
        diff = _make_diff(["info", "warning"])
        assert _classify_diff_severity(diff) == "warning"

    def test_info_when_only_info(self):
        diff = _make_diff(["info"])
        assert _classify_diff_severity(diff) == "info"

    def test_none_when_no_changes(self):
        diff = _make_diff([], total=0)
        assert _classify_diff_severity(diff) == "none"


class TestShouldNotify:
    def test_none_never_sends(self):
        assert _should_notify("critical", "none") is False

    def test_all_always_sends(self):
        assert _should_notify("none", "all") is True

    def test_critical_only_sends_on_critical(self):
        assert _should_notify("critical", "critical") is True
        assert _should_notify("warning", "critical") is False
        assert _should_notify("info", "critical") is False

    def test_warning_sends_on_critical_and_warning(self):
        assert _should_notify("critical", "warning") is True
        assert _should_notify("warning", "warning") is True
        assert _should_notify("info", "warning") is False


class TestSendNtfy:
    @pytest.mark.asyncio
    async def test_builds_correct_request_for_critical(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(notify_on="all")
        diff = _make_diff(["critical"])

        result = await send_ntfy(config, diff)

        assert result is True
        request = httpx_mock.get_request()
        assert request.url == "https://ntfy.sh/test-topic"
        assert request.headers["Title"] == "EOL Check: 1 changes detected"
        assert request.headers["Priority"] == "5"
        assert "rotating_light" in request.headers["Tags"]

    @pytest.mark.asyncio
    async def test_warning_priority_and_tags(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(notify_on="all")
        diff = _make_diff(["warning"])

        await send_ntfy(config, diff)

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "3"
        assert request.headers["Tags"] == "warning"

    @pytest.mark.asyncio
    async def test_info_priority_and_tags(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(notify_on="all")
        diff = _make_diff(["info"])

        await send_ntfy(config, diff)

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "2"
        assert request.headers["Tags"] == "information_source"

    @pytest.mark.asyncio
    async def test_no_changes_min_priority(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(notify_on="all")
        diff = _make_diff([], total=0)

        await send_ntfy(config, diff)

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "1"
        assert request.headers["Tags"] == "white_check_mark"
        assert "no changes" in request.headers["Title"]

    @pytest.mark.asyncio
    async def test_notify_on_critical_skips_warning(self, httpx_mock):
        config = _make_config(notify_on="critical")
        diff = _make_diff(["warning"])

        result = await send_ntfy(config, diff)

        assert result is False
        assert httpx_mock.get_request() is None

    @pytest.mark.asyncio
    async def test_token_adds_authorization(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(ntfy_token="tk_secret123", notify_on="all")
        diff = _make_diff(["info"])

        await send_ntfy(config, diff)

        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer tk_secret123"

    @pytest.mark.asyncio
    async def test_no_token_no_auth_header(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(notify_on="all")
        diff = _make_diff(["info"])

        await send_ntfy(config, diff)

        request = httpx_mock.get_request()
        assert "Authorization" not in request.headers

    @pytest.mark.asyncio
    async def test_http_failure_returns_false(self, httpx_mock):
        httpx_mock.add_response(status_code=500)
        config = _make_config(notify_on="all")
        diff = _make_diff(["critical"])

        result = await send_ntfy(config, diff)

        assert result is False


class TestSendNtfyError:
    @pytest.mark.asyncio
    async def test_sends_error_notification(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config()

        result = await send_ntfy_error(config, "Pipeline crashed: timeout")

        assert result is True
        request = httpx_mock.get_request()
        assert request.headers["Title"] == "EOL Check Failed"
        assert request.headers["Priority"] == "4"
        assert request.headers["Tags"] == "x"
        assert b"Pipeline crashed: timeout" in request.content

    @pytest.mark.asyncio
    async def test_error_with_token(self, httpx_mock):
        httpx_mock.add_response(status_code=200)
        config = _make_config(ntfy_token="tk_err")

        await send_ntfy_error(config, "error")

        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer tk_err"

    @pytest.mark.asyncio
    async def test_error_http_failure_returns_false(self, httpx_mock):
        httpx_mock.add_response(status_code=403)
        config = _make_config()

        result = await send_ntfy_error(config, "some error")

        assert result is False
