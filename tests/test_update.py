"""Tests for the update CLI command and source cache functionality."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eol_tool.cache import ResultCache
from eol_tool.checkers.endoflife_date import EndOfLifeDateChecker
from eol_tool.checkers.juniper import JuniperChecker
from eol_tool.cli import cli


@pytest.fixture
async def cache(tmp_path):
    c = ResultCache(db_path=tmp_path / "test.db")
    yield c
    await c.close()


# ===================================================================
# Source cache (ResultCache methods)
# ===================================================================


class TestSourceCache:
    async def test_set_and_get_source(self, cache):
        await cache.set_source("endoflife.date", '["product1","product2"]', 2)
        entry = await cache.get_source("endoflife.date")
        assert entry is not None
        assert entry["item_count"] == 2
        assert json.loads(entry["data"]) == ["product1", "product2"]
        assert isinstance(entry["fetched_at"], datetime)

    async def test_get_source_not_found(self, cache):
        entry = await cache.get_source("nonexistent")
        assert entry is None

    async def test_set_source_overwrites(self, cache):
        await cache.set_source("test-source", '["a"]', 1)
        await cache.set_source("test-source", '["a","b","c"]', 3)
        entry = await cache.get_source("test-source")
        assert entry["item_count"] == 3

    async def test_source_stats_empty(self, cache):
        stats = await cache.source_stats()
        assert stats == []

    async def test_source_stats_multiple(self, cache):
        await cache.set_source("endoflife.date", "[]", 287)
        await cache.set_source("juniper-eol", "[]", 48)
        await cache.set_source("supermicro-eol", "[]", 96)
        stats = await cache.source_stats()
        assert len(stats) == 3
        by_source = {s["source"]: s for s in stats}
        assert by_source["endoflife.date"]["item_count"] == 287
        assert by_source["juniper-eol"]["item_count"] == 48
        assert by_source["supermicro-eol"]["item_count"] == 96

    async def test_source_stats_with_multiple_keys(self, cache):
        await cache.set_source("cisco-eol", '[]', 10, key="listing")
        await cache.set_source("cisco-eol", '[]', 5, key="bulletins")
        stats = await cache.source_stats()
        assert len(stats) == 1
        assert stats[0]["source"] == "cisco-eol"
        assert stats[0]["item_count"] == 15  # SUM of both keys


# ===================================================================
# refresh_cache classmethods
# ===================================================================


def _mock_response(data, text=None, status_code=200):
    """Create a mock httpx.Response."""
    from unittest.mock import MagicMock

    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data
    resp.text = text or json.dumps(data)
    return resp


class TestEndOfLifeDateRefresh:
    async def test_refresh_cache(self, cache):
        products = ["nginx", "redis", "python", "nodejs", "linux"]
        mock_resp = _mock_response(products)

        with patch("eol_tool.checkers.endoflife_date.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            count = await EndOfLifeDateChecker.refresh_cache(cache)

        assert count == 5
        entry = await cache.get_source("endoflife.date")
        assert entry is not None
        assert entry["item_count"] == 5
        assert json.loads(entry["data"]) == products


class TestJuniperRefresh:
    async def test_refresh_cache(self, cache):
        # Minimal HTML that parse_listing_families can parse
        html = """<html><script>
        {"selector": "sw-eol-list", "properties": {"list": [
            {"items": [{"items": [
                {"label": "EX Series", "url": "/eol/ex"},
                {"label": "SRX Series", "url": "/eol/srx"}
            ]}]}
        ]}}
        </script></html>"""
        mock_resp = _mock_response(None, text=html)

        with patch("eol_tool.checkers.juniper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            count = await JuniperChecker.refresh_cache(cache)

        assert count == 2
        entry = await cache.get_source("juniper-eol")
        assert entry is not None
        assert entry["item_count"] == 2


# ===================================================================
# CLI update command
# ===================================================================


class TestUpdateCommand:
    def test_update_all_sources(self, tmp_path):
        """Update all sources with mocked HTTP."""
        runner = CliRunner()

        with (
            patch.object(
                EndOfLifeDateChecker, "refresh_cache",
                new=AsyncMock(return_value=287),
            ),
            patch.object(
                JuniperChecker, "refresh_cache",
                new=AsyncMock(return_value=48),
            ),
            patch("eol_tool.cache.ResultCache.__init__", return_value=None),
            patch("eol_tool.cache.ResultCache.close", new_callable=AsyncMock),
        ):
            result = runner.invoke(cli, ["update"])

        assert result.exit_code == 0
        assert "Refreshing endoflife.date... done (287 products cached)" in result.output
        assert "Refreshing juniper... done (48 products cached)" in result.output
        assert "supermicro" not in result.output
        assert "cisco" not in result.output
        assert "All sources updated. Cache fresh as of" in result.output

    def test_update_single_source(self, tmp_path):
        """Update a specific source only."""
        runner = CliRunner()

        with (
            patch.object(
                JuniperChecker, "refresh_cache",
                new=AsyncMock(return_value=48),
            ),
            patch("eol_tool.cache.ResultCache.__init__", return_value=None),
            patch("eol_tool.cache.ResultCache.close", new_callable=AsyncMock),
        ):
            result = runner.invoke(cli, ["update", "--source", "juniper"])

        assert result.exit_code == 0
        assert "Refreshing juniper... done (48 products cached)" in result.output
        assert "endoflife.date" not in result.output
        assert "supermicro" not in result.output
        assert "cisco" not in result.output

    def test_update_handles_failure(self, tmp_path):
        """Gracefully handle a source that fails to refresh."""
        runner = CliRunner()

        with (
            patch.object(
                EndOfLifeDateChecker, "refresh_cache",
                new=AsyncMock(side_effect=Exception("Connection timed out")),
            ),
            patch("eol_tool.cache.ResultCache.__init__", return_value=None),
            patch("eol_tool.cache.ResultCache.close", new_callable=AsyncMock),
        ):
            result = runner.invoke(cli, ["update", "--source", "endoflife.date"])

        assert result.exit_code == 0
        assert "failed (Connection timed out)" in result.output

    def test_update_invalid_source(self):
        """Invalid --source value is rejected by click."""
        runner = CliRunner()
        result = runner.invoke(cli, ["update", "--source", "invalid"])
        assert result.exit_code != 0


# ===================================================================
# CLI cache stats with source info
# ===================================================================


class TestCacheStatsWithSources:
    def test_cache_stats_shows_source_info(self, tmp_path):
        """cache stats shows per-source cache age."""
        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # Pre-populate the source cache
        import asyncio

        async def _setup():
            c = ResultCache(db_path=db_path)
            await cache_set_helper(c)
            await c.close()

        async def cache_set_helper(c):
            await c.set_source("endoflife.date", "[]", 287)
            await c.set_source("juniper-eol", "[]", 48)

        asyncio.run(_setup())

        with patch("eol_tool.cache._DEFAULT_DB", db_path):
            result = runner.invoke(cli, ["cache", "stats"])

        assert result.exit_code == 0
        assert "endoflife.date: 287 products" in result.output
        assert "juniper-eol: 48 products" in result.output
