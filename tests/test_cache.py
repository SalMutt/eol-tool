"""Tests for result cache."""

from datetime import date, datetime, timedelta

import pytest

from eol_tool.cache import ResultCache
from eol_tool.models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory


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


class TestCacheNewFields:
    async def test_persists_eol_reason_risk_date_source(self, cache):
        r = EOLResult(
            model=HardwareModel(model="TEST-1", manufacturer="Acme", category="switch"),
            status=EOLStatus.EOL,
            eol_date=date(2024, 1, 1),
            checked_at=datetime.now(),
            confidence=95,
            source_name="test",
            source_url="https://example.com",
            notes="",
            eol_reason=EOLReason.MANUFACTURER_DECLARED,
            risk_category=RiskCategory.SECURITY,
            date_source="vendor_page",
        )
        await cache.set(r)
        cached = await cache.get("TEST-1", "Acme")
        assert cached is not None
        assert cached.eol_reason == EOLReason.MANUFACTURER_DECLARED
        assert cached.risk_category == RiskCategory.SECURITY
        assert cached.date_source == "vendor_page"

    async def test_defaults_for_missing_fields(self, cache):
        r = EOLResult(
            model=HardwareModel(model="TEST-2", manufacturer="Acme", category="switch"),
            status=EOLStatus.ACTIVE,
            checked_at=datetime.now(),
            confidence=50,
            source_name="test",
        )
        await cache.set(r)
        cached = await cache.get("TEST-2", "Acme")
        assert cached is not None
        assert cached.eol_reason == EOLReason.NONE
        assert cached.risk_category == RiskCategory.NONE
        assert cached.date_source == "none"

    async def test_migration_adds_columns_to_old_schema(self, tmp_path):
        """Simulate an old database without the new columns."""
        import aiosqlite

        db_path = tmp_path / "old.db"
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("""
                CREATE TABLE results (
                    model TEXT NOT NULL,
                    manufacturer TEXT NOT NULL,
                    status TEXT NOT NULL,
                    eol_date TEXT,
                    eos_date TEXT,
                    source_url TEXT,
                    source_name TEXT,
                    checked_at TEXT NOT NULL,
                    confidence INTEGER DEFAULT 0,
                    notes TEXT,
                    PRIMARY KEY (model, manufacturer)
                )
            """)
            await db.execute("""
                CREATE TABLE source_cache (
                    source TEXT NOT NULL,
                    key TEXT NOT NULL,
                    data TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    item_count INTEGER DEFAULT 0,
                    PRIMARY KEY (source, key)
                )
            """)
            await db.commit()

        cache = ResultCache(db_path=db_path)
        try:
            r = EOLResult(
                model=HardwareModel(model="OLD-1", manufacturer="Acme", category="switch"),
                status=EOLStatus.EOL,
                checked_at=datetime.now(),
                confidence=80,
                source_name="test",
                eol_reason=EOLReason.COMMUNITY_DATA,
                risk_category=RiskCategory.SUPPORT,
                date_source="api",
            )
            await cache.set(r)
            cached = await cache.get("OLD-1", "Acme")
            assert cached is not None
            assert cached.eol_reason == EOLReason.COMMUNITY_DATA
            assert cached.risk_category == RiskCategory.SUPPORT
            assert cached.date_source == "api"
        finally:
            await cache.close()

    async def test_migration_on_new_db_no_error(self, tmp_path):
        """Opening a fresh database twice should not fail (columns already exist)."""
        db_path = tmp_path / "new.db"
        cache1 = ResultCache(db_path=db_path)
        await cache1.set(
            EOLResult(
                model=HardwareModel(model="X", manufacturer="Y", category="z"),
                status=EOLStatus.ACTIVE,
                checked_at=datetime.now(),
                source_name="test",
            )
        )
        await cache1.close()

        cache2 = ResultCache(db_path=db_path)
        try:
            cached = await cache2.get("X", "Y")
            assert cached is not None
        finally:
            await cache2.close()
