# Rate Limit Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exponential backoff with jitter retry to all checkers that make HTTP calls, making the tool resilient to transient rate limits and network hiccups.

**Architecture:** A shared `with_retry` async utility in `src/eol_tool/retry.py` wraps callables with exponential backoff + jitter. `BaseChecker._fetch()` is refactored to use it for httpx calls. Playwright-based checkers (Intel ARK, Cisco) wrap their top-level scrape methods. Retry config is readable from env vars with per-checker overrides.

**Tech Stack:** Python asyncio, httpx, playwright (existing deps). No new dependencies.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/eol_tool/retry.py` | Create | `RetryConfig`, `RetryExhausted`, `with_retry()` utility |
| `tests/test_retry.py` | Create | 14 test cases for retry utility |
| `src/eol_tool/checker.py` | Modify | Replace inline retry in `_fetch()` with `with_retry()` |
| `src/eol_tool/checkers/intel_ark.py` | Modify | Wrap `_playwright_lookup` in `with_retry()` |
| `src/eol_tool/checkers/cisco.py` | Modify | Wrap `_scrape_bulletin` in `with_retry()` |
| `.env.example` | Modify | Add `EOL_TOOL_RETRY_MAX` and `EOL_TOOL_RETRY_BASE_DELAY` |

**Not modified** (no HTTP calls): `supermicro.py`, `tech_generation.py`, `manual.py`, `generic_optics.py`, all brand checkers (samsung, seagate, etc.).

**endoflife_date.py** and **juniper.py** already use `BaseChecker._fetch()`, so they get retry for free when we refactor `_fetch()`.

---

### Task 1: Create retry utility with TDD — core happy path

**Files:**
- Create: `tests/test_retry.py`
- Create: `src/eol_tool/retry.py`

- [ ] **Step 1: Write test file with first 4 tests (happy path + basic retry)**

```python
"""Tests for the retry utility."""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from eol_tool.retry import RetryConfig, RetryExhausted, with_retry


@pytest.mark.asyncio
async def test_succeeds_on_first_attempt():
    """No retry needed when the function succeeds immediately."""
    func = AsyncMock(return_value="ok")
    result = await with_retry(func, config=RetryConfig())
    assert result == "ok"
    assert func.await_count == 1


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds():
    """Retries on HTTP 429 and succeeds on second attempt."""
    response_429 = httpx.Response(429, request=httpx.Request("GET", "http://test"))
    response_ok = httpx.Response(200, request=httpx.Request("GET", "http://test"))

    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPStatusError(
                "rate limited", request=response_429.request, response=response_429
            )
        return response_ok

    with patch("eol_tool.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(func, config=RetryConfig())
    assert result.status_code == 200
    assert call_count == 2


@pytest.mark.asyncio
async def test_retries_on_500_then_succeeds():
    """Retries on HTTP 500 and succeeds on second attempt."""
    response_500 = httpx.Response(500, request=httpx.Request("GET", "http://test"))
    response_ok = httpx.Response(200, request=httpx.Request("GET", "http://test"))

    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPStatusError(
                "server error", request=response_500.request, response=response_500
            )
        return response_ok

    with patch("eol_tool.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(func, config=RetryConfig())
    assert result.status_code == 200
    assert call_count == 2


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds():
    """Retries on httpx.TimeoutException and succeeds on retry."""
    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.TimeoutException("timed out")
        return "recovered"

    with patch("eol_tool.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(func, config=RetryConfig())
    assert result == "recovered"
    assert call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eol_tool.retry'`

- [ ] **Step 3: Write the retry module**

```python
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
        """Create config from environment variables with optional overrides."""
        max_retries = int(os.environ.get("EOL_TOOL_RETRY_MAX", "3"))
        base_delay = float(os.environ.get("EOL_TOOL_RETRY_BASE_DELAY", "2.0"))
        return cls(max_retries=max_retries, base_delay=base_delay, **overrides)


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

    # Playwright TimeoutError (string-based check to avoid import dependency)
    if "TimeoutError" in type(exc).__name__ and config.retry_on_timeout:
        return True, "playwright timeout"

    return False, ""


async def with_retry(
    func: Callable[..., Awaitable[T]],
    config: RetryConfig | None = None,
    log: logging.Logger | None = None,
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
                cfg.base_delay * (cfg.backoff_factor ** attempt),
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
            await asyncio.sleep(jitter)

    # Should not be reached, but satisfy type checker
    raise RetryExhausted(last_error=last_error, last_status=last_status, attempts=cfg.max_retries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retry.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/eol_tool/retry.py tests/test_retry.py
git commit -m "feat: add retry utility with exponential backoff and jitter"
```

---

### Task 2: Retry utility TDD — error paths and edge cases

**Files:**
- Modify: `tests/test_retry.py`

- [ ] **Step 1: Add tests for no-retry-on-404, no-retry-on-400, exhaustion, delays, jitter, max_delay, logging, and env config**

Append to `tests/test_retry.py`:

```python
@pytest.mark.asyncio
async def test_no_retry_on_404():
    """404 fails immediately without retry."""
    response_404 = httpx.Response(404, request=httpx.Request("GET", "http://test"))

    func = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "not found", request=response_404.request, response=response_404
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await with_retry(func, config=RetryConfig())
    assert func.await_count == 1


@pytest.mark.asyncio
async def test_no_retry_on_400():
    """400 fails immediately without retry."""
    response_400 = httpx.Response(400, request=httpx.Request("GET", "http://test"))

    func = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "bad request", request=response_400.request, response=response_400
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        await with_retry(func, config=RetryConfig())
    assert func.await_count == 1


@pytest.mark.asyncio
async def test_retry_exhausted_after_max_retries():
    """RetryExhausted raised after all retries fail."""
    response_429 = httpx.Response(429, request=httpx.Request("GET", "http://test"))

    func = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "rate limited", request=response_429.request, response=response_429
        )
    )

    config = RetryConfig(max_retries=2)
    with patch("eol_tool.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RetryExhausted) as exc_info:
            await with_retry(func, config=config)
    assert exc_info.value.attempts == 3  # initial + 2 retries
    assert exc_info.value.last_status == 429
    assert func.await_count == 3


@pytest.mark.asyncio
async def test_exponential_delay_increases():
    """Delays increase exponentially between retries."""
    response_500 = httpx.Response(500, request=httpx.Request("GET", "http://test"))

    func = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "error", request=response_500.request, response=response_500
        )
    )

    config = RetryConfig(max_retries=3, base_delay=2.0, backoff_factor=2.0)
    sleep_calls = []

    async def mock_sleep(duration):
        sleep_calls.append(duration)

    with patch("eol_tool.retry.asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(RetryExhausted):
            await with_retry(func, config=config)

    # 3 retries means 3 sleeps. Base delays: 2, 4, 8 (with jitter *0.5-1.5)
    assert len(sleep_calls) == 3
    assert sleep_calls[0] >= 1.0  # 2.0 * 0.5
    assert sleep_calls[0] <= 3.0  # 2.0 * 1.5
    assert sleep_calls[1] >= 2.0  # 4.0 * 0.5
    assert sleep_calls[1] <= 6.0  # 4.0 * 1.5
    assert sleep_calls[2] >= 4.0  # 8.0 * 0.5
    assert sleep_calls[2] <= 12.0  # 8.0 * 1.5


@pytest.mark.asyncio
async def test_jitter_adds_randomness():
    """Jitter produces non-deterministic delays."""
    response_500 = httpx.Response(500, request=httpx.Request("GET", "http://test"))

    config = RetryConfig(max_retries=1, base_delay=10.0, backoff_factor=1.0)
    delays = []

    for _ in range(10):
        sleep_calls = []

        async def mock_sleep(duration):
            sleep_calls.append(duration)

        func = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "error", request=response_500.request, response=response_500
            )
        )

        with patch("eol_tool.retry.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(RetryExhausted):
                await with_retry(func, config=config)
        delays.append(sleep_calls[0])

    # With jitter, not all delays should be identical
    unique_delays = set(delays)
    assert len(unique_delays) > 1


@pytest.mark.asyncio
async def test_max_delay_caps_backoff():
    """Delay never exceeds max_delay (before jitter)."""
    response_500 = httpx.Response(500, request=httpx.Request("GET", "http://test"))

    func = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "error", request=response_500.request, response=response_500
        )
    )

    config = RetryConfig(
        max_retries=3, base_delay=10.0, backoff_factor=10.0, max_delay=15.0
    )
    sleep_calls = []

    async def mock_sleep(duration):
        sleep_calls.append(duration)

    with patch("eol_tool.retry.asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(RetryExhausted):
            await with_retry(func, config=config)

    # max_delay=15, with jitter *1.5 max = 22.5
    for d in sleep_calls:
        assert d <= 22.5


@pytest.mark.asyncio
async def test_retry_logging(caplog):
    """Retry logs INFO messages with attempt count and reason."""
    response_429 = httpx.Response(429, request=httpx.Request("GET", "http://test"))

    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise httpx.HTTPStatusError(
                "rate limited", request=response_429.request, response=response_429
            )
        return "ok"

    config = RetryConfig(max_retries=3)
    with patch("eol_tool.retry.asyncio.sleep", new_callable=AsyncMock):
        import logging
        with caplog.at_level(logging.INFO, logger="eol_tool.retry"):
            await with_retry(func, config=config)

    assert any("Retry 1/3" in m and "HTTP 429" in m for m in caplog.messages)
    assert any("Retry 2/3" in m and "HTTP 429" in m for m in caplog.messages)


def test_retry_config_from_env():
    """RetryConfig reads from env vars."""
    with patch.dict(os.environ, {
        "EOL_TOOL_RETRY_MAX": "5",
        "EOL_TOOL_RETRY_BASE_DELAY": "3.5",
    }):
        config = RetryConfig.from_env()
    assert config.max_retries == 5
    assert config.base_delay == 3.5
    assert config.backoff_factor == 2.0  # default unchanged


def test_retry_config_from_env_with_overrides():
    """RetryConfig.from_env allows local overrides."""
    with patch.dict(os.environ, {
        "EOL_TOOL_RETRY_MAX": "5",
    }):
        config = RetryConfig.from_env(base_delay=10.0, max_retries=2)
    assert config.max_retries == 2  # override wins
    assert config.base_delay == 10.0  # override wins


@pytest.mark.asyncio
async def test_retries_on_502_503_504():
    """Retries on 502, 503, 504 status codes."""
    for status_code in (502, 503, 504):
        response_err = httpx.Response(
            status_code, request=httpx.Request("GET", "http://test")
        )
        response_ok = httpx.Response(200, request=httpx.Request("GET", "http://test"))

        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "error", request=response_err.request, response=response_err
                )
            return response_ok

        with patch("eol_tool.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await with_retry(func, config=RetryConfig())
        assert result.status_code == 200
        call_count = 0
```

- [ ] **Step 2: Run all retry tests**

Run: `python -m pytest tests/test_retry.py -v`
Expected: 14 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_retry.py
git commit -m "test: add comprehensive retry utility test coverage"
```

---

### Task 3: Integrate retry into BaseChecker._fetch()

**Files:**
- Modify: `src/eol_tool/checker.py` (lines 1-91)

- [ ] **Step 1: Refactor `_fetch()` to use `with_retry`**

Replace the `_fetch` method in `src/eol_tool/checker.py` (lines 65-91). The new version delegates retry logic to `with_retry()` and removes the inline for-loop retry.

Add import at top of `checker.py`:

```python
from .retry import RetryConfig, with_retry
```

Replace the `_fetch` method (lines 65-91) with:

```python
    async def _fetch(self, url: str, **kwargs) -> httpx.Response:
        """Rate-limited HTTP GET with retry."""
        assert self._client is not None, "Use checker as async context manager"
        logger.info("Fetching %s...", url)

        config = RetryConfig.from_env()

        async def _do_fetch() -> httpx.Response:
            response = await self._client.get(url, **kwargs)
            response.raise_for_status()
            return response

        response = await with_retry(_do_fetch, config=config, log=logger)
        logger.info("Fetched %s (%s)", url, response.status_code)
        return response
```

Note: the semaphore-based rate limiting stays in `check_batch()` (line 49), so `_fetch` no longer acquires it (the old code double-acquired via `_limited_check` + `_fetch`, which was a bug). Callers that need rate limiting already wrap via `check_batch()._limited_check()`.

- [ ] **Step 2: Run existing tests to verify nothing broke**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: all existing tests pass (1137+)

- [ ] **Step 3: Commit**

```bash
git add src/eol_tool/checker.py
git commit -m "refactor: use shared retry utility in BaseChecker._fetch"
```

---

### Task 4: Integrate retry into Intel ARK checker

**Files:**
- Modify: `src/eol_tool/checkers/intel_ark.py` (lines 207-269)

- [ ] **Step 1: Wrap `_playwright_lookup` in retry**

Add import at top of `intel_ark.py`:

```python
from ..retry import RetryConfig, RetryExhausted, with_retry
```

In the `check` method (around line 190), wrap the `_playwright_lookup` call. Replace the section:

```python
            data = await self._playwright_lookup(model_key)
```

with:

```python
            playwright_config = RetryConfig.from_env(
                max_retries=2, base_delay=5.0,
            )

            async def _do_lookup():
                result = await self._playwright_lookup(model_key)
                if result and result.get("result_status") == "timeout":
                    raise TimeoutError(f"Playwright timeout for {model_key}")
                return result

            try:
                data = await with_retry(_do_lookup, config=playwright_config, log=logger)
            except RetryExhausted:
                logger.warning("Intel ARK retries exhausted for %s", model_key)
                data = {"result_status": "timeout"}
            except TimeoutError:
                data = {"result_status": "timeout"}
```

The existing `_playwright_lookup` already creates and closes its own page per call (line 211, 272), so each retry gets a fresh page — no stale state.

- [ ] **Step 2: Run existing tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add src/eol_tool/checkers/intel_ark.py
git commit -m "feat: add retry with backoff to Intel ARK Playwright lookups"
```

---

### Task 5: Integrate retry into Cisco checker

**Files:**
- Modify: `src/eol_tool/checkers/cisco.py` (lines 196-235)

- [ ] **Step 1: Wrap `_scrape_bulletin` in retry**

Add import at top of `cisco.py`:

```python
from ..retry import RetryConfig, RetryExhausted, with_retry
```

In the `check` method (around line 212-233), replace the Playwright scraping section. Replace:

```python
        if PLAYWRIGHT_AVAILABLE and self._browser and not self._checker_disabled:
            try:
                bulletin_data = await asyncio.wait_for(
                    self._scrape_bulletin(normalized),
                    timeout=_SCRAPE_TIMEOUT_SECONDS,
                )
                if bulletin_data and (
                    bulletin_data.get("eol_date") or bulletin_data.get("eos_date")
                ):
                    conn = _init_cache_db()
                    try:
                        _set_cached(conn, normalized, bulletin_data)
                    finally:
                        conn.close()
                    return _cached_to_result(model, bulletin_data)
            except asyncio.TimeoutError:
                logger.warning(
                    "Cisco lookup for %s exceeded %ds timeout, using static rules",
                    normalized,
                    _SCRAPE_TIMEOUT_SECONDS,
                )
```

with:

```python
        if PLAYWRIGHT_AVAILABLE and self._browser and not self._checker_disabled:
            playwright_config = RetryConfig.from_env(
                max_retries=2, base_delay=5.0,
            )

            async def _do_scrape():
                return await asyncio.wait_for(
                    self._scrape_bulletin(normalized),
                    timeout=_SCRAPE_TIMEOUT_SECONDS,
                )

            try:
                bulletin_data = await with_retry(
                    _do_scrape, config=playwright_config, log=logger,
                )
                if bulletin_data and (
                    bulletin_data.get("eol_date") or bulletin_data.get("eos_date")
                ):
                    conn = _init_cache_db()
                    try:
                        _set_cached(conn, normalized, bulletin_data)
                    finally:
                        conn.close()
                    return _cached_to_result(model, bulletin_data)
            except (RetryExhausted, asyncio.TimeoutError):
                logger.warning(
                    "Cisco lookup for %s failed after retries, using static rules",
                    normalized,
                )
```

The existing `_scrape_bulletin` already creates/closes its own page per call (line 247, 319), so retries are safe.

- [ ] **Step 2: Run existing tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add src/eol_tool/checkers/cisco.py
git commit -m "feat: add retry with backoff to Cisco Playwright scraping"
```

---

### Task 6: Add env config to .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Append retry config lines to `.env.example`**

Add at the end of `.env.example`:

```
# Retry settings for HTTP calls
# EOL_TOOL_RETRY_MAX=3
# EOL_TOOL_RETRY_BASE_DELAY=2.0
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add retry config to .env.example"
```

---

### Task 7: Add CLI retry summary feedback

**Files:**
- Modify: `src/eol_tool/retry.py`
- Modify: `src/eol_tool/cli.py`
- Modify: `tests/test_retry.py`

The spec requires that after a check completes, if any retries occurred, the CLI shows a summary like:
"Note: 3 models required retries (2 Intel ARK timeouts, 1 endoflife.date 429)"

The per-retry INFO log messages (e.g., "[intel-ark] Retry 1/3 for E-2136 after timeout (waiting 4s)") are already handled by `with_retry`'s `log.info()` call added in Task 1.

For the summary, we need a simple module-level counter.

- [ ] **Step 1: Add retry event tracking to `retry.py`**

Add to `src/eol_tool/retry.py`, after the imports:

```python
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
```

Then in the `with_retry` function, after the `log.info("Retry %d/%d ...")` line, add:

```python
            record_retry_event(log.name.split(".")[-1], reason)
```

- [ ] **Step 2: Add test for retry summary**

Append to `tests/test_retry.py`:

```python
from eol_tool.retry import clear_retry_events, get_retry_summary, record_retry_event


def test_retry_summary_tracking():
    """Retry events are tracked and summarized."""
    clear_retry_events()
    record_retry_event("intel-ark", "timeout")
    record_retry_event("intel-ark", "timeout")
    record_retry_event("endoflife_date", "HTTP 429")
    summary = get_retry_summary()
    assert summary is not None
    assert "3 retries" in summary
    assert "intel-ark timeout" in summary
    assert "endoflife_date HTTP 429" in summary
    clear_retry_events()
    assert get_retry_summary() is None
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_retry.py::test_retry_summary_tracking -v`
Expected: PASS

- [ ] **Step 4: Add summary to CLI output**

In `src/eol_tool/cli.py`, add import:

```python
from .retry import clear_retry_events, get_retry_summary
```

In the `_run_with_progress` function, add `clear_retry_events()` at the top (before the pipeline runs), and after results are collected (before the return), add:

```python
        retry_summary = get_retry_summary()
        if retry_summary:
            click.echo(f"  {retry_summary}")
```

- [ ] **Step 5: Run full tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/eol_tool/retry.py src/eol_tool/cli.py tests/test_retry.py
git commit -m "feat: add CLI retry summary feedback"
```

---

### Task 8: Run full test suite and lint

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: all tests pass (1137 existing + 15 new = 1152+)

- [ ] **Step 2: Run ruff**

Run: `ruff check src/eol_tool/retry.py tests/test_retry.py src/eol_tool/checker.py src/eol_tool/checkers/intel_ark.py src/eol_tool/checkers/cisco.py`
Expected: clean (no issues)

- [ ] **Step 3: Fix any lint issues if needed, then final commit**

```bash
git add -A
git commit -m "chore: final lint cleanup for retry integration"
```
