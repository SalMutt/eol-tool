"""Shared retry utility with exponential backoff and jitter."""

import asyncio
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

import httpx

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Module-level retry event tracker for CLI summary
_retry_events: list[tuple[str, str]] = []  # (source, reason)


def record_retry_event(source: str, reason: str) -> None:
    """Record a retry event for end-of-run summary."""
    _retry_events.append((source, reason))


def get_retry_summary() -> str | None:
    """Return a human-readable retry summary, or None if no retries occurred."""
    if not _retry_events:
        return None
    from collections import Counter
    counts = Counter(_retry_events)
    total = len(_retry_events)
    parts = [f"{count} {source} {reason}" for (source, reason), count in counts.most_common()]
    return f"Note: {total} retries occurred ({', '.join(parts)})"


def clear_retry_events() -> None:
    """Clear retry events (call at start of a new run)."""
    _retry_events.clear()


def _default_retry_on_status() -> set[int]:
    return {429, 500, 502, 503, 504}


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    retry_on_status: set[int] = field(default_factory=_default_retry_on_status)
    retry_on_timeout: bool = True

    @classmethod
    def from_env(cls, **overrides) -> "RetryConfig":
        """Create config from environment variables with optional overrides.

        Explicit keyword overrides take precedence over env vars.
        """
        defaults = {
            "max_retries": int(os.environ.get("EOL_TOOL_RETRY_MAX", "3")),
            "base_delay": float(os.environ.get("EOL_TOOL_RETRY_BASE_DELAY", "2.0")),
        }
        defaults.update(overrides)
        return cls(**defaults)


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        last_error: Exception | None = None,
        last_status: int | None = None,
        attempts: int = 0,
    ):
        self.last_error = last_error
        self.last_status = last_status
        self.attempts = attempts
        super().__init__(
            f"Retry exhausted after {attempts} attempts"
            + (f" (last status: {last_status})" if last_status else "")
            + (f" (last error: {last_error})" if last_error else "")
        )


def _is_retryable(exc: Exception, config: RetryConfig) -> tuple[bool, str]:
    """Check if an exception is retryable. Returns (retryable, reason)."""
    if isinstance(exc, httpx.TimeoutException):
        if config.retry_on_timeout:
            return True, "timeout"
        return False, ""

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in config.retry_on_status:
            return True, f"HTTP {status}"
        return False, ""

    # TimeoutError variants: Playwright TimeoutError, asyncio.TimeoutError, builtins
    if "TimeoutError" in type(exc).__name__ and config.retry_on_timeout:
        return True, "timeout"

    return False, ""


async def with_retry(
    func: Callable[..., Awaitable[T]],
    config: RetryConfig | None = None,
    log: logging.Logger | None = None,
    checker_name: str | None = None,
) -> T:
    """Execute func with exponential backoff retry.

    Retries on:
    - httpx.TimeoutException (if retry_on_timeout is True)
    - httpx.HTTPStatusError with status in retry_on_status
    - Playwright TimeoutError (if retry_on_timeout is True)

    Does NOT retry on: 404, 400, 401, 403, non-HTTP exceptions.
    """
    cfg = config or RetryConfig()
    log = log or logger
    last_error: Exception | None = None
    last_status: int | None = None

    for attempt in range(cfg.max_retries + 1):
        try:
            return await func()
        except Exception as exc:
            retryable, reason = _is_retryable(exc, cfg)
            if not retryable or attempt >= cfg.max_retries:
                if retryable:
                    last_error = exc
                    if isinstance(exc, httpx.HTTPStatusError):
                        last_status = exc.response.status_code
                    raise RetryExhausted(
                        last_error=last_error,
                        last_status=last_status,
                        attempts=attempt + 1,
                    ) from exc
                raise

            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError):
                last_status = exc.response.status_code

            delay = min(
                cfg.base_delay * (cfg.backoff_factor**attempt),
                cfg.max_delay,
            )
            jitter = delay * random.uniform(0.5, 1.5)
            log.info(
                "Retry %d/%d after %.1fs for %s",
                attempt + 1,
                cfg.max_retries,
                jitter,
                reason,
            )
            record_retry_event(checker_name or log.name.split(".")[-1], reason)
            if checker_name:
                from .health import get_checker_health

                get_checker_health().record_retry(checker_name)
            await asyncio.sleep(jitter)

    # Should not be reached, but satisfy type checker
    raise RetryExhausted(
        last_error=last_error,
        last_status=last_status,
        attempts=cfg.max_retries + 1,
    )
