"""Tests for result cache."""

from datetime import date, datetime, timedelta

import pytest

from eol_tool.cache import ResultCache
from eol_tool.models import EOLResult, EOLStatus, HardwareModel


@pytest.fixture
async def cache(tmp_path):
    c = ResultCache(db_path=tmp_path / "test.db")
    yield c
    await c.close()


def _make_result(
    model="EX4300-48T",
    manufacturer="Juniper",
    status=EOLStatus.EOL,
    checked_at=None,
):
    return EOLResult(
        model=HardwareModel(model=model, manufacturer=manufacturer, category="switch"),
        status=status,
        eol_date=date(2023, 6, 15),
        checked_at=checked_at or datetime.now(),
        confidence=90,
        source_name="test",
        source_url="https://example.com",
        notes="test note",
    )


class TestCacheGetSet:
    async def test_get_empty(self, cache):
        result = await cache.get("nonexistent", "nobody")
        assert result is None

    async def test_set_and_get(self, cache):
        r = _make_result()
        await cache.set(r)
        cached = await cache.get("EX4300-48T", "Juniper")
        assert cached is not None
        assert cached.status == EOLStatus.EOL
        assert cached.model.model == "EX4300-48T"
        assert cached.eol_date == date(2023, 6, 15)
        assert cached.confidence == 90

    async def test_overwrite(self, cache):
        r1 = _make_result(status=EOLStatus.UNKNOWN)
        await cache.set(r1)
        r2 = _make_result(status=EOLStatus.EOL)
        await cache.set(r2)
        cached = await cache.get("EX4300-48T", "Juniper")
        assert cached.status == EOLStatus.EOL

    async def test_expired_returns_none(self, cache):
        old = _make_result(checked_at=datetime.now() - timedelta(days=60))
        await cache.set(old)
        result = await cache.get("EX4300-48T", "Juniper", max_age_days=30)
        assert result is None

    async def test_not_expired(self, cache):
        recent = _make_result(checked_at=datetime.now() - timedelta(days=5))
        await cache.set(recent)
        result = await cache.get("EX4300-48T", "Juniper", max_age_days=30)
        assert result is not None

    async def test_different_manufacturers_separate(self, cache):
        await cache.set(_make_result(model="X", manufacturer="A"))
        await cache.set(_make_result(model="X", manufacturer="B"))
        a = await cache.get("X", "A")
        b = await cache.get("X", "B")
        assert a is not None
        assert b is not None


class TestCacheClear:
    async def test_clear_all(self, cache):
        await cache.set(_make_result(model="A", manufacturer="X"))
        await cache.set(_make_result(model="B", manufacturer="Y"))
        deleted = await cache.clear()
        assert deleted == 2
        assert await cache.get("A", "X") is None
        assert await cache.get("B", "Y") is None

    async def test_clear_by_manufacturer(self, cache):
        await cache.set(_make_result(model="A", manufacturer="X"))
        await cache.set(_make_result(model="B", manufacturer="Y"))
        deleted = await cache.clear(manufacturer="X")
        assert deleted == 1
        assert await cache.get("A", "X") is None
        assert await cache.get("B", "Y") is not None


class TestCacheStats:
    async def test_empty_stats(self, cache):
        s = await cache.stats()
        assert s["total"] == 0
        assert s["by_status"] == {}
        assert s["by_manufacturer"] == {}

    async def test_stats_counts(self, cache):
        await cache.set(_make_result(model="A", manufacturer="X", status=EOLStatus.EOL))
        await cache.set(_make_result(model="B", manufacturer="X", status=EOLStatus.ACTIVE))
        await cache.set(_make_result(model="C", manufacturer="Y", status=EOLStatus.EOL))
        s = await cache.stats()
        assert s["total"] == 3
        assert s["by_status"]["eol"] == 2
        assert s["by_status"]["active"] == 1
        assert s["by_manufacturer"]["X"] == 2
        assert s["by_manufacturer"]["Y"] == 1
