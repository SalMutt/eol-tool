"""Abstract base checker for EOL lookups."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

import httpx

from .models import EOLResult, EOLStatus, HardwareModel
from .retry import RetryConfig, with_retry

logger = logging.getLogger(__name__)


class BaseChecker(ABC):
    """Base class for vendor-specific EOL checkers."""

    manufacturer_name: ClassVar[str]
    rate_limit: ClassVar[int] = 5
    priority: ClassVar[int] = 50
    base_url: ClassVar[str] = ""

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
