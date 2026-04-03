"""Result cache using aiosqlite."""

from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite

from .models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory

_DEFAULT_DB = Path.home() / ".cache" / "eol-tool" / "results.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS results (
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
    eol_reason TEXT DEFAULT 'none',
    risk_category TEXT DEFAULT 'none',
    date_source TEXT DEFAULT 'none',
    PRIMARY KEY (model, manufacturer)
)
"""

_CREATE_SOURCE_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS source_cache (
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    data TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    item_count INTEGER DEFAULT 0,
    PRIMARY KEY (source, key)
)
"""


class ResultCache:
    """SQLite cache for EOL check results."""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db: aiosqlite.Connection | None = None

    async def _connect(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(str(self._db_path))
            await self._db.execute(_CREATE_TABLE)
            await self._db.execute(_CREATE_SOURCE_CACHE_TABLE)
            # Migrate old schema: add columns that may be missing
            for col, default in [
                ("eol_reason", "none"),
                ("risk_category", "none"),
                ("date_source", "none"),
            ]:
                try:
                    await self._db.execute(
                        f"ALTER TABLE results ADD COLUMN {col} TEXT DEFAULT '{default}'"
                    )
                except Exception:
                    pass  # column already exists
            await self._db.commit()
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def get(
        self, model: str, manufacturer: str, max_age_days: int = 30
    ) -> EOLResult | None:
        db = await self._connect()
        cursor = await db.execute(
            "SELECT * FROM results WHERE model = ? AND manufacturer = ?",
            (model, manufacturer),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        checked_at = datetime.fromisoformat(row[7])
        if datetime.now() - checked_at > timedelta(days=max_age_days):
            return None

        from datetime import date

        return EOLResult(
            model=HardwareModel(
                model=row[0], manufacturer=row[1], category="unknown"
            ),
            status=EOLStatus(row[2]),
            eol_date=date.fromisoformat(row[3]) if row[3] else None,
            eos_date=date.fromisoformat(row[4]) if row[4] else None,
            source_url=row[5] or "",
            source_name=row[6] or "",
            checked_at=checked_at,
            confidence=row[8] or 0,
            notes=row[9] or "",
            eol_reason=EOLReason(row[10]) if row[10] else EOLReason.NONE,
            risk_category=RiskCategory(row[11]) if row[11] else RiskCategory.NONE,
            date_source=row[12] or "none",
        )

    async def set(self, result: EOLResult) -> None:
        db = await self._connect()
        await db.execute(
            """INSERT OR REPLACE INTO results
               (model, manufacturer, status, eol_date, eos_date,
                source_url, source_name, checked_at, confidence, notes,
                eol_reason, risk_category, date_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.model.model,
                result.model.manufacturer,
                result.status.value,
                result.eol_date.isoformat() if result.eol_date else None,
                result.eos_date.isoformat() if result.eos_date else None,
                result.source_url,
                result.source_name,
                result.checked_at.isoformat(),
                result.confidence,
                result.notes,
                result.eol_reason.value,
                result.risk_category.value,
                result.date_source,
            ),
        )
        await db.commit()

    async def clear(self, manufacturer: str | None = None) -> int:
        db = await self._connect()
        if manufacturer:
            cursor = await db.execute(
                "DELETE FROM results WHERE manufacturer = ?", (manufacturer,)
            )
        else:
            cursor = await db.execute("DELETE FROM results")
        await db.commit()
        return cursor.rowcount

    async def stats(self) -> dict:
        db = await self._connect()
        result: dict = {}

        cursor = await db.execute(
            "SELECT status, COUNT(*) FROM results GROUP BY status"
        )
        result["by_status"] = dict(await cursor.fetchall())

        cursor = await db.execute(
            "SELECT manufacturer, COUNT(*) FROM results GROUP BY manufacturer"
        )
        result["by_manufacturer"] = dict(await cursor.fetchall())

        cursor = await db.execute("SELECT COUNT(*) FROM results")
        row = await cursor.fetchone()
        result["total"] = row[0] if row else 0

        return result

    # ── Source cache methods ─────────────────────────────────────

    async def get_source(self, source: str, key: str = "default") -> dict | None:
        """Get a source cache entry. Returns dict with data, fetched_at, item_count."""
        db = await self._connect()
        cursor = await db.execute(
            "SELECT data, fetched_at, item_count FROM source_cache "
            "WHERE source = ? AND key = ?",
            (source, key),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "data": row[0],
            "fetched_at": datetime.fromisoformat(row[1]),
            "item_count": row[2],
        }

    async def set_source(
        self, source: str, data: str, item_count: int, key: str = "default"
    ) -> None:
        """Store a source cache entry."""
        db = await self._connect()
        await db.execute(
            """INSERT OR REPLACE INTO source_cache
               (source, key, data, fetched_at, item_count)
               VALUES (?, ?, ?, ?, ?)""",
            (source, key, data, datetime.now().isoformat(), item_count),
        )
        await db.commit()

    async def source_stats(self) -> list[dict]:
        """Get per-source cache statistics: source, total items, fetched_at."""
        db = await self._connect()
        cursor = await db.execute(
            "SELECT source, SUM(item_count), MAX(fetched_at) "
            "FROM source_cache GROUP BY source ORDER BY source"
        )
        rows = await cursor.fetchall()
        return [
            {
                "source": row[0],
                "item_count": row[1] or 0,
                "fetched_at": datetime.fromisoformat(row[2]) if row[2] else None,
            }
            for row in rows
        ]
