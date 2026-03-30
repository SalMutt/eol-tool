"""FastAPI application wrapping eol-tool functionality."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .cache import ResultCache
from .check_pipeline import select_best_result
from .manufacturer_corrections import apply_manufacturer_corrections
from .models import EOLResult, EOLStatus, HardwareModel
from .normalizer import normalize_model
from .reader import read_models
from .registry import get_checker, get_checkers, list_checkers

logger = logging.getLogger(__name__)

app = FastAPI(title="EOL Tool API", version="2.0.0")

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


async def _run_check_pipeline(
    models: list[HardwareModel],
    concurrency: int = 5,
) -> list[EOLResult]:
    """Run the full check pipeline on a list of models. Reuses CLI logic."""
    apply_manufacturer_corrections(models)

    by_mfr: dict[str, list[HardwareModel]] = {}
    for m in models:
        by_mfr.setdefault(m.manufacturer, []).append(m)

    cache_inst = ResultCache()
    all_results: list[EOLResult] = []

    try:
        for mfr_name, mfr_models in sorted(by_mfr.items()):
            to_check: list[HardwareModel] = []
            for m in mfr_models:
                cached = await cache_inst.get(m.model, m.manufacturer)
                if cached:
                    cached.model = m
                    all_results.append(cached)
                else:
                    to_check.append(m)

            if not to_check:
                continue

            checker_classes = []
            manual_cls = get_checker("__manual__")
            vendor_classes = get_checkers(mfr_name)
            techgen_cls = get_checker("__techgen__")
            fallback_cls = get_checker("__fallback__")

            if manual_cls:
                checker_classes.append(manual_cls)
            checker_classes.extend(vendor_classes)
            if techgen_cls:
                checker_classes.append(techgen_cls)
            if fallback_cls:
                checker_classes.append(fallback_cls)

            if not checker_classes:
                for m in to_check:
                    all_results.append(
                        EOLResult(
                            model=m,
                            status=EOLStatus.UNKNOWN,
                            checked_at=datetime.now(),
                            source_name="",
                            notes="no-checker-available",
                        )
                    )
                continue

            per_model_results: list[list[EOLResult]] = [[] for _ in to_check]

            for checker_cls in checker_classes:
                try:
                    checker = checker_cls()
                    checker._semaphore = asyncio.Semaphore(concurrency)
                    async with checker:
                        checker_results = await checker.check_batch(to_check)
                    for i, r in enumerate(checker_results):
                        r.checker_priority = checker_cls.priority
                        per_model_results[i].append(r)
                except Exception as exc:
                    logger.warning("Checker %s failed: %s", checker_cls.__name__, exc)

            for i, m in enumerate(to_check):
                results = per_model_results[i]
                if results:
                    best = select_best_result(results)
                    await cache_inst.set(best)
                    all_results.append(best)
                else:
                    all_results.append(
                        EOLResult(
                            model=m,
                            status=EOLStatus.UNKNOWN,
                            checked_at=datetime.now(),
                            source_name="",
                            notes="all-checkers-failed",
                        )
                    )
    finally:
        await cache_inst.close()

    return all_results


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


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

    results = await _run_check_pipeline([hw])
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
        results = await _run_check_pipeline(models)
    finally:
        tmp_path.unlink(missing_ok=True)

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

    dated_count = sum(1 for r in results if r.eol_date is not None)

    return {
        "total": len(results),
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
