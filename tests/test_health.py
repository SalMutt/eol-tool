"""Tests for scraper health tracking."""

import pytest

from eol_tool.health import CheckerHealth


@pytest.fixture
def health():
    h = CheckerHealth()
    yield h
    h.reset()


def test_record_success_increments_counters(health):
    health.record_success("Intel ARK", "X520-DA2", 150.0)
    data = health.get_health()
    c = data["checkers"]["Intel ARK"]
    assert c["total_checks"] == 1
    assert c["successes"] == 1
    assert c["failures"] == 0


def test_record_failure_increments_failure_and_stores_error(health):
    health.record_failure("Intel ARK", "X520-DA2", "Timeout 20000ms exceeded", 5000.0)
    data = health.get_health()
    c = data["checkers"]["Intel ARK"]
    assert c["failures"] == 1
    assert c["last_error"] == "Timeout 20000ms exceeded"
    assert c["last_failure"] is not None


def test_record_not_found_tracked_separately(health):
    health.record_success("Cisco EOL Bulletins", "WS-C3750", 200.0)
    health.record_not_found("Cisco EOL Bulletins", "UNKNOWN-MODEL", 50.0)
    data = health.get_health()
    c = data["checkers"]["Cisco EOL Bulletins"]
    assert c["not_found"] == 1
    assert c["failures"] == 0
    assert c["successes"] == 1
    assert c["total_checks"] == 2


def test_get_health_returns_expected_structure(health):
    health.record_success("Intel ARK", "X520-DA2", 100.0)
    data = health.get_health()
    assert "checkers" in data
    assert "overall_status" in data
    assert "total_checks" in data
    assert "total_failures" in data
    assert "uptime_seconds" in data
    assert "last_full_check" in data
    c = data["checkers"]["Intel ARK"]
    for key in [
        "status", "total_checks", "successes", "failures", "not_found",
        "success_rate", "avg_response_ms", "last_success", "last_failure",
        "last_error", "retry_count",
    ]:
        assert key in c, f"Missing key: {key}"


def test_status_healthy_when_high_success_rate(health):
    for i in range(10):
        health.record_success("Intel ARK", f"model-{i}", 100.0)
    health.record_failure("Intel ARK", "model-bad", "error", 100.0)
    data = health.get_health()
    # 10/11 = 90.9% >= 90 -> healthy
    assert data["checkers"]["Intel ARK"]["status"] == "healthy"


def test_status_degraded_when_medium_success_rate(health):
    for i in range(6):
        health.record_success("Intel ARK", f"model-{i}", 100.0)
    for i in range(4):
        health.record_failure("Intel ARK", f"fail-{i}", "error", 100.0)
    data = health.get_health()
    # 6/10 = 60% -> degraded
    assert data["checkers"]["Intel ARK"]["status"] == "degraded"


def test_status_down_when_low_success_rate(health):
    health.record_success("Intel ARK", "model-ok", 100.0)
    for i in range(9):
        health.record_failure("Intel ARK", f"fail-{i}", "error", 100.0)
    data = health.get_health()
    # 1/10 = 10% < 50 -> down
    assert data["checkers"]["Intel ARK"]["status"] == "down"


def test_status_idle_when_no_checks(health):
    data = health.get_health()
    assert data["overall_status"] == "idle"
    assert data["checkers"] == {}


def test_overall_status_reflects_worst(health):
    # healthy checker
    for i in range(10):
        health.record_success("Manual Overrides", f"m-{i}", 1.0)
    # degraded checker
    for i in range(3):
        health.record_success("Intel ARK", f"m-{i}", 100.0)
    for i in range(3):
        health.record_failure("Intel ARK", f"f-{i}", "err", 100.0)
    data = health.get_health()
    # Manual Overrides is healthy, Intel ARK is degraded -> overall degraded
    assert data["overall_status"] == "degraded"


def test_reset_clears_all_metrics(health):
    health.record_success("Intel ARK", "X520", 100.0)
    health.record_failure("Cisco EOL Bulletins", "WS", "err", 50.0)
    health.reset()
    data = health.get_health()
    assert data["checkers"] == {}
    assert data["total_checks"] == 0
    assert data["total_failures"] == 0
    assert data["last_full_check"] is None


def test_elapsed_ms_averaging(health):
    health.record_success("Intel ARK", "m1", 100.0)
    health.record_success("Intel ARK", "m2", 200.0)
    health.record_success("Intel ARK", "m3", 300.0)
    data = health.get_health()
    assert data["checkers"]["Intel ARK"]["avg_response_ms"] == 200.0


def test_retry_count_tracked(health):
    health.record_retry("Intel ARK")
    health.record_retry("Intel ARK")
    health.record_retry("Intel ARK")
    # Also record a check so the checker appears
    health.record_success("Intel ARK", "m1", 100.0)
    data = health.get_health()
    assert data["checkers"]["Intel ARK"]["retry_count"] == 3


def test_success_rate_calculation(health):
    for i in range(3):
        health.record_success("Cisco EOL Bulletins", f"m-{i}", 100.0)
    health.record_failure("Cisco EOL Bulletins", "f-1", "err", 100.0)
    data = health.get_health()
    assert data["checkers"]["Cisco EOL Bulletins"]["success_rate"] == 75.0


def test_multiple_checkers_independent(health):
    health.record_success("Intel ARK", "m1", 100.0)
    health.record_failure("Cisco EOL Bulletins", "m2", "err", 200.0)
    data = health.get_health()
    assert data["checkers"]["Intel ARK"]["status"] == "healthy"
    assert data["checkers"]["Cisco EOL Bulletins"]["status"] == "down"
    assert data["total_checks"] == 2
    assert data["total_failures"] == 1


def test_uptime_seconds_positive(health):
    data = health.get_health()
    assert data["uptime_seconds"] >= 0


def test_last_full_check_updated_on_record(health):
    health.record_success("Intel ARK", "m1", 100.0)
    data = health.get_health()
    assert data["last_full_check"] is not None


def test_healthy_when_zero_failures(health):
    """Even with only 1 check, 0 failures means healthy."""
    health.record_success("Intel ARK", "m1", 100.0)
    data = health.get_health()
    assert data["checkers"]["Intel ARK"]["status"] == "healthy"
