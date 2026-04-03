"""Tests for the retry utility."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from eol_tool.retry import RetryConfig, with_retry


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
