"""Scraper health tracking for EOL checkers."""

import time
from datetime import datetime, timezone
from threading import Lock

_CHECKER_DISPLAY_NAMES: dict[str, str] = {
    "IntelARKChecker": "Intel ARK",
    "IntelChecker": "Intel",
    "CiscoChecker": "Cisco EOL Bulletins",
    "EndOfLifeDateChecker": "endoflife.date API",
    "JuniperChecker": "Juniper EOL Pages",
    "SupermicroChecker": "Supermicro EOL",
    "TechGenerationChecker": "Tech Generation Rules",
    "ManualChecker": "Manual Overrides",
    "GenericOpticsChecker": "Generic Optics",
    "AMDChecker": "AMD",
    "DellChecker": "Dell",
    "SamsungChecker": "Samsung",
    "SeagateChecker": "Seagate",
    "MicronChecker": "Micron",
    "WDChecker": "WD",
    "BroadcomChecker": "Broadcom",
    "AristaChecker": "Arista",
    "KingstonChecker": "Kingston",
    "GigabyteChecker": "Gigabyte",
    "ASRockChecker": "ASRock",
    "DynatronChecker": "Dynatron",
    "ToshibaChecker": "Toshiba",
    "TranscendChecker": "Transcend",
    "MushkinChecker": "Mushkin",
    "KIOXIAChecker": "KIOXIA",
    "SolidigmChecker": "Solidigm",
    "PNYChecker": "PNY",
    "OCZChecker": "OCZ",
}


def checker_display_name(class_name: str) -> str:
    """Map a checker class name to its human-readable display name."""
    return _CHECKER_DISPLAY_NAMES.get(class_name, class_name)


class _CheckerMetrics:
    __slots__ = (
        "total_checks", "successes", "failures", "not_found",
        "retry_count", "total_ms", "last_success", "last_failure", "last_error",
    )

    def __init__(self) -> None:
        self.total_checks: int = 0
        self.successes: int = 0
        self.failures: int = 0
        self.not_found: int = 0
        self.retry_count: int = 0
        self.total_ms: float = 0.0
        self.last_success: datetime | None = None
        self.last_failure: datetime | None = None
        self.last_error: str | None = None


class CheckerHealth:
    """Track per-checker health metrics in memory (resets on restart)."""

    def __init__(self) -> None:
        self._metrics: dict[str, _CheckerMetrics] = {}
        self._lock = Lock()
        self._start_time = time.monotonic()
        self._last_check_time: datetime | None = None

    def _get_metrics(self, checker_name: str) -> _CheckerMetrics:
        if checker_name not in self._metrics:
            self._metrics[checker_name] = _CheckerMetrics()
        return self._metrics[checker_name]

    def record_success(self, checker_name: str, model: str, elapsed_ms: float) -> None:
        """Record a successful check."""
        with self._lock:
            m = self._get_metrics(checker_name)
            m.total_checks += 1
            m.successes += 1
            m.total_ms += elapsed_ms
            m.last_success = datetime.now(timezone.utc)
            self._last_check_time = datetime.now(timezone.utc)

    def record_failure(
        self, checker_name: str, model: str, error: str, elapsed_ms: float,
    ) -> None:
        """Record a failed check (exception, timeout, or unexpected response)."""
        with self._lock:
            m = self._get_metrics(checker_name)
            m.total_checks += 1
            m.failures += 1
            m.total_ms += elapsed_ms
            m.last_failure = datetime.now(timezone.utc)
            m.last_error = str(error)
            self._last_check_time = datetime.now(timezone.utc)

    def record_not_found(self, checker_name: str, model: str, elapsed_ms: float) -> None:
        """Record a NOT_FOUND result (not an error, but useful for tracking)."""
        with self._lock:
            m = self._get_metrics(checker_name)
            m.total_checks += 1
            m.not_found += 1
            m.total_ms += elapsed_ms
            self._last_check_time = datetime.now(timezone.utc)

    def record_retry(self, checker_name: str) -> None:
        """Increment the retry count for a checker."""
        with self._lock:
            m = self._get_metrics(checker_name)
            m.retry_count += 1

    def _checker_status(self, m: _CheckerMetrics) -> str:
        if m.total_checks == 0:
            return "idle"
        success_rate = (m.successes / m.total_checks) * 100
        if success_rate >= 90 or m.failures == 0:
            return "healthy"
        if success_rate >= 50:
            return "degraded"
        return "down"

    def get_health(self) -> dict:
        """Return health data for all checkers."""
        with self._lock:
            checkers: dict[str, dict] = {}
            total_checks = 0
            total_failures = 0
            status_priority = {"idle": 0, "healthy": 1, "degraded": 2, "down": 3}
            worst = "idle"

            for name, m in self._metrics.items():
                total_checks += m.total_checks
                total_failures += m.failures

                status = self._checker_status(m)
                if status_priority.get(status, 0) > status_priority.get(worst, 0):
                    worst = status

                checkers[name] = {
                    "status": status,
                    "total_checks": m.total_checks,
                    "successes": m.successes,
                    "failures": m.failures,
                    "not_found": m.not_found,
                    "success_rate": round(
                        (m.successes / m.total_checks) * 100, 1,
                    ) if m.total_checks > 0 else 0,
                    "avg_response_ms": round(
                        m.total_ms / m.total_checks, 1,
                    ) if m.total_checks > 0 else 0,
                    "last_success": m.last_success.isoformat() if m.last_success else None,
                    "last_failure": m.last_failure.isoformat() if m.last_failure else None,
                    "last_error": m.last_error,
                    "retry_count": m.retry_count,
                }

            return {
                "checkers": checkers,
                "overall_status": worst,
                "total_checks": total_checks,
                "total_failures": total_failures,
                "uptime_seconds": round(time.monotonic() - self._start_time),
                "last_full_check": (
                    self._last_check_time.isoformat()
                    if self._last_check_time else None
                ),
            }

    def reset(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()
            self._start_time = time.monotonic()
            self._last_check_time = None


_health = CheckerHealth()


def get_checker_health() -> CheckerHealth:
    """Return the module-level health tracker singleton."""
    return _health
