"""FastAPI application wrapping eol-tool functionality."""

import csv
import io
import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from eol_tool import __version__

from .cache import ResultCache
from .check_pipeline import run_check_pipeline
from .diff import compare_results
from .input_filter import filter_models
from .manufacturer_corrections import apply_manufacturer_corrections
from .models import EOLResult, HardwareModel
from .normalizer import normalize_model
from .paths import get_overrides_csv
from .reader import read_models
from .registry import list_checkers

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"eol", "active", "unknown"}
_VALID_REASONS = {
    "manufacturer_declared", "technology_generation", "product_discontinued",
    "vendor_acquired", "community_data", "manual_override", "none", "",
}
_VALID_RISKS = {"security", "support", "procurement", "informational", "none", ""}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CSV_FIELDS = [
    "model", "manufacturer", "status", "eol_reason", "risk_category",
    "eol_date", "eos_date", "source_url", "notes",
]

_csv_lock = threading.Lock()


class OverrideBody(BaseModel):
    model: str
    manufacturer: str = ""
    status: str
    eol_reason: str = ""
    risk_category: str = ""
    eol_date: str = ""
    eos_date: str = ""
    source_url: str = ""
    notes: str = ""

    @field_validator("model")
    @classmethod
    def model_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("model is required and must be non-empty")
        return v.strip()

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v.lower() not in _VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        return v.lower()

    @field_validator("eol_reason")
    @classmethod
    def reason_valid(cls, v: str) -> str:
        if v and v.lower() not in _VALID_REASONS:
            valid = ", ".join(sorted(_VALID_REASONS - {""}))
            raise ValueError(f"eol_reason must be one of: {valid}")
        return v.lower()

    @field_validator("risk_category")
    @classmethod
    def risk_valid(cls, v: str) -> str:
        if v and v.lower() not in _VALID_RISKS:
            valid = ", ".join(sorted(_VALID_RISKS - {""}))
            raise ValueError(f"risk_category must be one of: {valid}")
        return v.lower()

    @field_validator("eol_date", "eos_date")
    @classmethod
    def date_format(cls, v: str) -> str:
        if v and not _DATE_RE.match(v):
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class OverrideDeleteParams(BaseModel):
    model: str
    manufacturer: str = ""


def _read_overrides_csv(csv_path: Path | None = None) -> list[dict[str, str]]:
    path = csv_path or get_overrides_csv()
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_overrides_csv(rows: list[dict[str, str]], csv_path: Path | None = None) -> None:
    path = csv_path or get_overrides_csv()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _CSV_FIELDS})
    tmp.replace(path)


def _override_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("model", "").strip().lower(), row.get("manufacturer", "").strip().lower())


def get_csv_path() -> Path:
    """Return the CSV path. Allows tests to override."""
    return get_overrides_csv()


app = FastAPI(title="EOL Tool API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _result_to_dict(r: EOLResult) -> dict:
    """Convert an EOLResult to the API response dict."""
    return {
        "model": r.model.model,
        "manufacturer": r.model.manufacturer,
        "category": r.model.category,
        "status": r.status.value,
        "eol_date": r.eol_date.isoformat() if r.eol_date else None,
        "eos_date": r.eos_date.isoformat() if r.eos_date else None,
        "date_source": r.date_source,
        "risk_category": r.risk_category.value,
        "eol_reason": r.eol_reason.value,
        "confidence": r.confidence,
        "source": r.source_name,
        "notes": r.notes,
    }


def _infer_manufacturer(model_str: str) -> str:
    """Try to infer manufacturer from model string using known checker prefixes."""
    upper = model_str.upper()
    prefix_map = {
        "EX": "Juniper",
        "QFX": "Juniper",
        "MX": "Juniper",
        "SRX": "Juniper",
        "ACX": "Juniper",
        "JNP": "Juniper",
        "WS-C": "Cisco",
        "N9K": "Cisco",
        "N5K": "Cisco",
        "N3K": "Cisco",
        "C9": "Cisco",
        "ASR": "Cisco",
        "ISR": "Cisco",
        "XEON": "Intel",
        "X520": "Intel",
        "X540": "Intel",
        "X550": "Intel",
        "X710": "Intel",
        "E5-": "Intel",
        "E3-": "Intel",
        "EPYC": "AMD",
        "OPTERON": "AMD",
        "POWEREDGE": "Dell",
        "MZ-": "Samsung",
        "PM": "Samsung",
        "MZIL": "Samsung",
        "ST": "Seagate",
        "X10": "Supermicro",
        "X11": "Supermicro",
        "X12": "Supermicro",
        "X13": "Supermicro",
        "MCX": "Mellanox",
        "CX": "Mellanox",
        "MTFD": "Micron",
        "5300": "Micron",
        "5400": "Micron",
        "WD": "WD",
        "WUS": "WD",
    }
    for prefix, mfr in prefix_map.items():
        if upper.startswith(prefix):
            return mfr
    return ""


@app.get("/api/health")
async def health():
    """Scraper health dashboard data."""
    from .health import get_checker_health

    h = get_checker_health()
    data = h.get_health()

    recommendations: list[str] = []
    for name, info in data["checkers"].items():
        if info["status"] == "down":
            recommendations.append(
                f"{name} scraper is failing. Check if the vendor changed their page structure."
            )
        elif info["status"] == "degraded":
            recommendations.append(
                f"{name} has {info['success_rate']}% success rate."
                " May be experiencing rate limits."
            )
        if info["retry_count"] >= 5:
            recommendations.append(
                f"{name} required {info['retry_count']} retries."
                " Consider increasing timeout."
            )

    if not data["checkers"]:
        recommendations.append(
            "No EOL checks recorded. Run a check or start the scheduler."
        )

    data["recommendations"] = recommendations
    data["version"] = __version__
    return data


def _get_results_dir() -> Path:
    """Return the results directory path."""
    return Path(os.environ.get("EOL_TOOL_RESULTS_DIR", "./results"))


def _find_latest_results(results_dir: Path | None = None) -> Path | None:
    """Find the most recent results xlsx file."""
    rdir = results_dir or _get_results_dir()
    if not rdir.exists():
        return None
    files = sorted(rdir.glob("eol-results-*.xlsx"), reverse=True)
    return files[0] if files else None


# Set by scheduler when running; allows /api/status to report next check time
_next_scheduled_check: str | None = None


@app.get("/api/status")
async def status():
    """System status: last check info, counts, and cache stats."""
    results_dir = _get_results_dir()
    latest = _find_latest_results(results_dir)

    result: dict = {
        "last_check_time": None,
        "last_check_file": None,
        "total_models": 0,
        "eol_count": 0,
        "active_count": 0,
        "unknown_count": 0,
        "cache_stats": None,
        "next_scheduled_check": _next_scheduled_check,
    }

    if latest:
        result["last_check_file"] = latest.name
        # Extract timestamp from filename: eol-results-YYYY-MM-DDThh-mm-ss.xlsx
        stem = latest.stem  # eol-results-YYYY-MM-DDThh-mm-ss
        ts_part = stem.replace("eol-results-", "", 1)
        try:
            check_time = datetime.strptime(ts_part, "%Y-%m-%dT%H-%M-%S")
            result["last_check_time"] = check_time.isoformat()
        except ValueError:
            # Fall back to file modification time
            mtime = datetime.fromtimestamp(latest.stat().st_mtime)
            result["last_check_time"] = mtime.isoformat()

        # Read basic counts from the results file
        try:
            from .reader import read_results

            results = read_results(latest)
            result["total_models"] = len(results)
            for r in results:
                sv = r.status.value
                if sv in ("eol", "eol_announced"):
                    result["eol_count"] += 1
                elif sv == "active":
                    result["active_count"] += 1
                elif sv in ("unknown", "not_found"):
                    result["unknown_count"] += 1
        except Exception:
            logger.warning("Failed to read results from %s", latest, exc_info=True)

    # Cache stats
    try:
        cache_inst = ResultCache()
        try:
            result["cache_stats"] = await cache_inst.stats()
        finally:
            await cache_inst.close()
    except Exception:
        logger.warning("Failed to get cache stats", exc_info=True)

    return result


@app.get("/api/lookup")
async def lookup(
    model: str = Query(..., description="Model string to look up"),
    manufacturer: str = Query("", description="Manufacturer name (optional)"),
):
    """Look up EOL status for a single model."""
    if not manufacturer:
        manufacturer = _infer_manufacturer(model)

    normalized = normalize_model(model, manufacturer)
    hw = HardwareModel(
        model=normalized,
        manufacturer=manufacturer,
        category="unknown",
        original_item=model,
    )

    apply_manufacturer_corrections([hw])
    results = await run_check_pipeline([hw])
    if not results:
        return {"model": model, "status": "not_found", "date_source": "none"}

    r = results[0]
    return _result_to_dict(r)


@app.post("/api/check")
async def check_upload(file: UploadFile = File(...)):
    """Upload an xlsx file and run the full check pipeline."""
    suffix = ".xlsx"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        models = read_models(tmp_path)
        apply_manufacturer_corrections(models)
        models, filtered_rows = filter_models(models)
        results = await run_check_pipeline(models)
    finally:
        tmp_path.unlink(missing_ok=True)

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

    dated_count = sum(1 for r in results if r.eol_date is not None)

    return {
        "total": len(results),
        "filtered": len(filtered_rows),
        "eol": status_counts.get("eol", 0) + status_counts.get("eol_announced", 0),
        "active": status_counts.get("active", 0),
        "unknown": status_counts.get("unknown", 0),
        "not_found": status_counts.get("not_found", 0),
        "dated": dated_count,
        "results": [_result_to_dict(r) for r in results],
    }


@app.get("/api/sources")
async def sources():
    """List available data sources and their cache freshness."""
    cache_inst = ResultCache()
    try:
        source_info = await cache_inst.source_stats()
    finally:
        await cache_inst.close()

    checkers = list_checkers()

    # Build source list from registered checkers + cache info
    source_cache_map = {s["source"]: s for s in source_info}
    source_list = []

    # Known source types
    source_types = {
        "endoflife.date": "api",
        "juniper": "scraper",
        "supermicro": "scraper",
        "cisco": "scraper",
        "dell": "scraper",
    }

    seen = set()
    for name, cls in sorted(checkers.items()):
        if name.startswith("__"):
            if name == "__fallback__":
                display_name = "endoflife.date"
            elif name == "__manual__":
                display_name = "manual-overrides"
            elif name == "__techgen__":
                display_name = "tech-generation"
            else:
                continue
        else:
            display_name = name

        if display_name in seen:
            continue
        seen.add(display_name)

        cache_entry = source_cache_map.get(display_name)
        src_type = source_types.get(display_name, "local")

        entry: dict = {
            "name": display_name,
            "type": src_type,
            "priority": cls.priority,
        }

        if cache_entry:
            entry["cached_products"] = cache_entry["item_count"]
            fetched_at = cache_entry["fetched_at"]
            if fetched_at:
                age_hours = (datetime.now() - fetched_at).total_seconds() / 3600
                entry["cache_age_hours"] = round(age_hours, 1)
                entry["last_refreshed"] = fetched_at.isoformat() + "Z"
            else:
                entry["cache_age_hours"] = None
                entry["last_refreshed"] = None
        else:
            entry["cached_products"] = 0
            entry["cache_age_hours"] = None
            entry["last_refreshed"] = None

        source_list.append(entry)

    return {"sources": source_list}


@app.get("/api/overrides")
async def list_overrides():
    """Return all manual overrides as a JSON array."""
    with _csv_lock:
        rows = _read_overrides_csv(get_csv_path())
    return [
        {k: row.get(k, "") for k in _CSV_FIELDS}
        for row in rows
        if row.get("model", "").strip()
    ]


@app.post("/api/overrides", status_code=201)
async def create_override(body: OverrideBody):
    """Add a new manual override."""
    new_key = (body.model.lower(), body.manufacturer.strip().lower())
    with _csv_lock:
        rows = _read_overrides_csv(get_csv_path())
        for row in rows:
            if _override_key(row) == new_key:
                return Response(
                    content='{"detail":"duplicate model+manufacturer combination"}',
                    status_code=409,
                    media_type="application/json",
                )
        new_row = body.model_dump()
        rows.append(new_row)
        _write_overrides_csv(rows, get_csv_path())
    return {k: new_row.get(k, "") for k in _CSV_FIELDS}


@app.put("/api/overrides")
async def update_override(body: OverrideBody):
    """Update an existing manual override identified by model+manufacturer."""
    target_key = (body.model.lower(), body.manufacturer.strip().lower())
    with _csv_lock:
        rows = _read_overrides_csv(get_csv_path())
        found = False
        for i, row in enumerate(rows):
            if _override_key(row) == target_key:
                rows[i] = body.model_dump()
                found = True
                break
        if not found:
            return Response(
                content='{"detail":"override not found"}',
                status_code=404,
                media_type="application/json",
            )
        _write_overrides_csv(rows, get_csv_path())
    return {k: rows[i].get(k, "") for k in _CSV_FIELDS}


@app.delete("/api/overrides")
async def delete_override(
    model: str = Query(..., description="Model to delete"),
    manufacturer: str = Query("", description="Manufacturer"),
):
    """Delete a manual override by model+manufacturer."""
    target_key = (model.strip().lower(), manufacturer.strip().lower())
    with _csv_lock:
        rows = _read_overrides_csv(get_csv_path())
        new_rows = [r for r in rows if _override_key(r) != target_key]
        if len(new_rows) == len(rows):
            return Response(
                content='{"detail":"override not found"}',
                status_code=404,
                media_type="application/json",
            )
        _write_overrides_csv(new_rows, get_csv_path())
    return {"deleted": True}


@app.get("/api/overrides/export")
async def export_overrides():
    """Download the overrides CSV file."""
    with _csv_lock:
        rows = _read_overrides_csv(get_csv_path())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in _CSV_FIELDS})
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=manual_overrides.csv"},
    )


@app.post("/api/overrides/import")
async def import_overrides(file: UploadFile = File(...)):
    """Import a CSV file and merge with existing overrides."""
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    incoming = list(reader)

    with _csv_lock:
        existing = _read_overrides_csv(get_csv_path())
        existing_map: dict[tuple[str, str], int] = {}
        for i, row in enumerate(existing):
            existing_map[_override_key(row)] = i

        added = 0
        updated = 0
        unchanged = 0

        for imp_row in incoming:
            key = _override_key(imp_row)
            if not key[0]:
                continue
            normalized = {k: imp_row.get(k, "") for k in _CSV_FIELDS}
            if key in existing_map:
                idx = existing_map[key]
                old = {k: existing[idx].get(k, "") for k in _CSV_FIELDS}
                if old != normalized:
                    existing[idx] = normalized
                    updated += 1
                else:
                    unchanged += 1
            else:
                existing.append(normalized)
                existing_map[key] = len(existing) - 1
                added += 1

        _write_overrides_csv(existing, get_csv_path())

    return {"added": added, "updated": updated, "unchanged": unchanged}


_LAST_RESULTS_PATH: Path | None = None


def _set_last_results(path: Path) -> None:
    global _LAST_RESULTS_PATH
    _LAST_RESULTS_PATH = path


@app.post("/api/diff")
async def diff_upload(
    previous: UploadFile = File(...),
    current: UploadFile = File(...),
):
    """Compare two xlsx result files and return the diff as JSON."""
    prev_tmp = NamedTemporaryFile(suffix=".xlsx", delete=False)
    curr_tmp = NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        prev_tmp.write(await previous.read())
        prev_tmp.close()
        curr_tmp.write(await current.read())
        curr_tmp.close()

        diff_result = compare_results(prev_tmp.name, curr_tmp.name)
        return json.loads(diff_result.model_dump_json())
    finally:
        Path(prev_tmp.name).unlink(missing_ok=True)
        Path(curr_tmp.name).unlink(missing_ok=True)


@app.get("/api/diff/last")
async def diff_last(
    current: str = Query(..., description="Path to current results xlsx"),
):
    """Compare against the most recent stored results."""
    if _LAST_RESULTS_PATH is None or not _LAST_RESULTS_PATH.exists():
        return Response(
            content='{"detail":"no previous results available"}',
            status_code=404,
            media_type="application/json",
        )
    diff_result = compare_results(str(_LAST_RESULTS_PATH), current)
    return json.loads(diff_result.model_dump_json())


# Mount static files last so API routes take precedence
_frontend_candidates = [
    Path(__file__).resolve().parent.parent.parent / "frontend",  # source tree
    Path("/app/frontend"),  # Docker
    Path.cwd() / "frontend",  # current directory
]
for _candidate in _frontend_candidates:
    if _candidate.is_dir() and (_candidate / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(_candidate), html=True), name="frontend")
        break
