"""Abstract base checker for EOL lookups."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

import httpx

from .models import EOLResult, EOLStatus, HardwareModel

logger = logging.getLogger(__name__)


class BaseChecker(ABC):
    """Base class for vendor-specific EOL checkers."""

    manufacturer_name: ClassVar[str]
    rate_limit: ClassVar[int] = 5
    priority: ClassVar[int] = 50
    base_url: ClassVar[str] = ""
    _response_cache: ClassVar[dict[str, httpx.Response]] = {}

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.rate_limit)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseChecker":
        self._client = httpx.AsyncClient(
            http2=True,
            timeout=10.0,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def check(self, model: HardwareModel) -> EOLResult:
        """Check EOL status for a single hardware model."""
        ...

    async def check_batch(self, models: list[HardwareModel]) -> list[EOLResult]:
        """Check multiple models concurrently with rate limiting and error handling."""

        async def _limited_check(m: HardwareModel) -> EOLResult:
            try:
                async with self._semaphore:
                    return await self.check(m)
            except Exception as exc:
                logger.warning("Check failed for %s %s: %s", m.manufacturer, m.model, exc)
                return EOLResult(
                    model=m,
                    status=EOLStatus.UNKNOWN,
                    checked_at=datetime.now(),
                    source_name="",
                    notes=f"check-error: {exc}",
                )

        return list(await asyncio.gather(*[_limited_check(m) for m in models]))

    async def _fetch(self, url: str, **kwargs) -> httpx.Response:
        """Rate-limited HTTP GET with retries and URL-level caching."""
        if url in self._response_cache:
            return self._response_cache[url]
        assert self._client is not None, "Use checker as async context manager"
        logger.info("Fetching %s...", url)
        async with self._semaphore:
            for attempt in range(3):
                try:
                    response = await asyncio.wait_for(
                        self._client.get(url, **kwargs), timeout=15,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Hard timeout fetching %s after 15s", url)
                    raise httpx.TimeoutException(
                        f"Hard timeout after 15s: {url}"
                    )
                except httpx.TimeoutException:
                    logger.warning("Timeout fetching %s after 10s", url)
                    raise
                if response.status_code == 429 or response.status_code >= 500:
                    await asyncio.sleep(2**attempt)
                    continue
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.warning("Failed to fetch %s: %s", url, exc)
                    raise
                logger.info("Fetched %s (%s)", url, response.status_code)
                self._response_cache[url] = response
                return response
            logger.warning(
                "Failed to fetch %s: HTTP %s after retries",
                url, response.status_code,
            )
            response.raise_for_status()
            return response
