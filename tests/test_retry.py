"""Tests for the retry utility."""

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from eol_tool.retry import (
    RetryConfig,
    RetryExhausted,
    clear_retry_events,
    get_retry_summary,
    record_retry_event,
    with_retry,
)


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
    with patch.dict(
        os.environ,
        {
            "EOL_TOOL_RETRY_MAX": "5",
            "EOL_TOOL_RETRY_BASE_DELAY": "3.5",
        },
    ):
        config = RetryConfig.from_env()
    assert config.max_retries == 5
    assert config.base_delay == 3.5
    assert config.backoff_factor == 2.0  # default unchanged


def test_retry_config_from_env_with_overrides():
    """RetryConfig.from_env allows local overrides."""
    with patch.dict(
        os.environ,
        {
            "EOL_TOOL_RETRY_MAX": "5",
        },
    ):
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
