"""CLI interface for eol-tool."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import click

from eol_tool import __version__

from .manufacturer_corrections import apply_manufacturer_corrections
from .models import EOLResult, EOLStatus, HardwareModel, RiskCategory
from .reader import read_models, write_results
from .registry import get_checker, get_checkers
from .registry import list_checkers as _list_checkers

# Checkers that have a refresh_cache classmethod, keyed by source name
_REFRESHABLE_SOURCES: dict[str, str] = {
    "endoflife.date": "eol_tool.checkers.endoflife_date:EndOfLifeDateChecker",
    "juniper": "eol_tool.checkers.juniper:JuniperChecker",
}

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
def cli():
    """EOL Tool - Check end-of-life status for hardware models."""


async def _safe_check_batch(
    checker, models: list[HardwareModel],
) -> list[EOLResult]:
    """Delegate to checker.check_batch which handles per-model error catching."""
    return await checker.check_batch(models)


async def _run_check(
    models: list[HardwareModel],
    by_mfr: dict[str, list[HardwareModel]],
    concurrency: int,
    no_cache: bool,
    skip_fallback: bool,
) -> list[EOLResult]:
    """Run all applicable checkers for grouped models and return best results."""
    from .cache import ResultCache
    from .check_pipeline import select_best_result

    cache_inst = ResultCache() if not no_cache else None
    all_results: list[EOLResult] = []

    try:
        for mfr_name, mfr_models in sorted(by_mfr.items()):
            # Try to load cached results first
            to_check: list[HardwareModel] = []
            if cache_inst:
                for m in mfr_models:
                    cached = await cache_inst.get(m.model, m.manufacturer)
                    if cached:
                        cached.model = m
                        all_results.append(cached)
                    else:
                        to_check.append(m)
                if len(to_check) < len(mfr_models):
                    cached_count = len(mfr_models) - len(to_check)
                    click.echo(f"  {mfr_name}: {cached_count} cached, {len(to_check)} to check")
            else:
                to_check = mfr_models

            if not to_check:
                continue

            # Identify ALL applicable checkers
            checker_classes = []
            manual_cls = get_checker("__manual__")
            vendor_classes = get_checkers(mfr_name)
            techgen_cls = get_checker("__techgen__")
            fallback_cls = None if skip_fallback else get_checker("__fallback__")

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
                click.echo(
                    f"Checking {mfr_name}: {len(to_check)} models... skipped (no checker)"
                )
                continue

            click.echo(f"Checking {mfr_name}: {len(to_check)} models...")

            # Run ALL checkers and collect results per model
            per_model_results: list[list[EOLResult]] = [[] for _ in to_check]

            for checker_cls in checker_classes:
                try:
                    checker = checker_cls()
                    checker._semaphore = asyncio.Semaphore(concurrency)
                    async with checker:
                        checker_results = await _safe_check_batch(checker, to_check)
                    for i, r in enumerate(checker_results):
                        r.checker_priority = checker_cls.priority
                        per_model_results[i].append(r)
                except Exception as exc:
                    logger.warning("Checker %s failed: %s", checker_cls.__name__, exc)

            # Select best result for each model
            batch_results = []
            for i, m in enumerate(to_check):
                results = per_model_results[i]
                if results:
                    batch_results.append(select_best_result(results))
                else:
                    batch_results.append(
                        EOLResult(
                            model=m,
                            status=EOLStatus.UNKNOWN,
                            checked_at=datetime.now(),
                            source_name="",
                            notes="all-checkers-failed",
                        )
                    )

            # Store results in cache
            if cache_inst:
                for r in batch_results:
                    await cache_inst.set(r)

            all_results.extend(batch_results)

            # Print batch summary
            counts: dict[str, int] = {}
            for r in batch_results:
                counts[r.status.value] = counts.get(r.status.value, 0) + 1
            parts = [
                f"{counts.get(s, 0)} {s}"
                for s in ["eol", "active", "unknown"]
                if counts.get(s, 0)
            ]
            click.echo(f"  Done: {', '.join(parts)}")

    finally:
        if cache_inst:
            await cache_inst.close()

    return all_results


@cli.command()
@click.option(
    "--input", "input_path", required=True, type=click.Path(exists=True),
    help="Path to input spreadsheet",
)
@click.option("--output", "output_path", type=click.Path(), default=None, help="Output file path")
@click.option("--manufacturer", default="all", help="Manufacturer to check (or 'all')")
@click.option("--concurrency", default=5, type=int, help="Max concurrent requests")
@click.option("--dry-run", is_flag=True, help="Load models and show summary without checking")
@click.option("--no-cache", is_flag=True, help="Skip the result cache")
@click.option("--skip-fallback", is_flag=True, help="Skip the endoflife.date fallback checker")
def check(input_path, output_path, manufacturer, concurrency, dry_run, no_cache, skip_fallback):
    """Check EOL status for hardware models."""
    models = read_models(Path(input_path))
    click.echo(f"Loaded {len(models)} models")

    apply_manufacturer_corrections(models)

    by_mfr: dict[str, list] = {}
    for m in models:
        by_mfr.setdefault(m.manufacturer, []).append(m)

    click.echo(f"\nManufacturers ({len(by_mfr)}):")
    for mfr, mfr_models in sorted(by_mfr.items()):
        click.echo(f"  {mfr or '(none)'}: {len(mfr_models)} models")

    if dry_run:
        click.echo("\n--dry-run specified, exiting without checking.")
        return

    if manufacturer != "all":
        if manufacturer not in by_mfr:
            click.echo(f"No models found for manufacturer: {manufacturer}")
            return
        by_mfr = {manufacturer: by_mfr[manufacturer]}

    checkers = _list_checkers()
    if not checkers:
        click.echo("\nNo checkers registered. Add checker modules to eol_tool/checkers/.")
        return

    click.echo("")
    results = asyncio.run(
        _run_check(models, by_mfr, concurrency, no_cache, skip_fallback)
    )

    if output_path:
        write_results(results, Path(output_path))
        click.echo(f"\nResults written to {output_path}")

    # Print summary table
    risk_labels = ["Security", "Support", "Procurement", "Info"]
    hdr = (
        f"{'Manufacturer':<20} {'Total':>6} {'EOL':>6} "
        f"{'Active':>6} {'Unknown':>8} {'Not Found':>10}"
    )
    for rl in risk_labels:
        hdr += f" {rl:>12}"
    click.echo(f"\n{hdr}")
    click.echo("-" * (60 + 13 * len(risk_labels)))
    summary: dict[str, dict[str, int]] = {}
    for r in results:
        mfr = r.model.manufacturer or "(none)"
        summary.setdefault(
            mfr,
            {
                "total": 0, "eol": 0, "active": 0, "unknown": 0, "not_found": 0,
                "security": 0, "support": 0, "procurement": 0, "informational": 0,
            },
        )
        summary[mfr]["total"] += 1
        if r.status in (EOLStatus.EOL, EOLStatus.EOL_ANNOUNCED):
            summary[mfr]["eol"] += 1
        elif r.status == EOLStatus.ACTIVE:
            summary[mfr]["active"] += 1
        elif r.status == EOLStatus.NOT_FOUND:
            summary[mfr]["not_found"] += 1
        else:
            summary[mfr]["unknown"] += 1
        if r.risk_category != RiskCategory.NONE:
            summary[mfr][r.risk_category.value] += 1
    for mfr, c in sorted(summary.items()):
        line = (
            f"{mfr:<20} {c['total']:>6} {c['eol']:>6} "
            f"{c['active']:>6} {c['unknown']:>8} {c['not_found']:>10}"
        )
        for rk in ["security", "support", "procurement", "informational"]:
            line += f" {c[rk]:>12}"
        click.echo(line)


@cli.command("list-checkers")
def list_checkers_cmd():
    """Show registered EOL checkers."""
    checkers = _list_checkers()
    if not checkers:
        click.echo("No checkers registered.")
        return
    for name, cls in sorted(checkers.items()):
        click.echo(f"  {name}: {cls.__name__}")


@cli.group()
def cache():
    """Manage the result cache."""


@cache.command("stats")
def cache_stats():
    """Show cache statistics."""
    from .cache import ResultCache

    async def _run():
        c = ResultCache()
        try:
            s = await c.stats()
            click.echo(f"Total cached results: {s['total']}")
            if s["by_status"]:
                click.echo("\nBy status:")
                for status, count in sorted(s["by_status"].items()):
                    click.echo(f"  {status}: {count}")
            if s["by_manufacturer"]:
                click.echo("\nBy manufacturer:")
                for mfr, count in sorted(s["by_manufacturer"].items()):
                    click.echo(f"  {mfr}: {count}")

            source_info = await c.source_stats()
            if source_info:
                click.echo("\nSource cache:")
                for entry in source_info:
                    age = _format_age(entry["fetched_at"]) if entry["fetched_at"] else "never"
                    click.echo(
                        f"  {entry['source']}: {entry['item_count']} products, cached {age}"
                    )
        finally:
            await c.close()

    asyncio.run(_run())


@cache.command("clear")
@click.option("--manufacturer", default=None, help="Clear cache for a specific manufacturer only")
def cache_clear(manufacturer):
    """Clear cached results."""
    from .cache import ResultCache

    async def _run():
        c = ResultCache()
        try:
            deleted = await c.clear(manufacturer=manufacturer)
            if manufacturer:
                click.echo(f"Cleared {deleted} cached results for {manufacturer}.")
            else:
                click.echo(f"Cleared {deleted} cached results.")
        finally:
            await c.close()

    asyncio.run(_run())


def _load_checker_class(dotted_path: str):
    """Import and return a checker class from 'module:ClassName' path."""
    import importlib

    module_path, class_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _format_age(dt: datetime) -> str:
    """Format a datetime as a human-readable age string."""
    delta = datetime.now() - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


@cli.command()
@click.option(
    "--source", "source_name", default=None,
    type=click.Choice(list(_REFRESHABLE_SOURCES.keys()), case_sensitive=False),
    help="Refresh a specific source only",
)
def update(source_name):
    """Force-refresh cached data from all live API/scraper sources."""
    from .cache import ResultCache

    async def _run():
        cache = ResultCache()
        try:
            sources = (
                {source_name: _REFRESHABLE_SOURCES[source_name]}
                if source_name
                else _REFRESHABLE_SOURCES
            )

            for name, dotted_path in sources.items():
                click.echo(f"Refreshing {name}... ", nl=False)
                try:
                    checker_cls = _load_checker_class(dotted_path)
                    count = await checker_cls.refresh_cache(cache)
                    click.echo(f"done ({count} products cached)")
                except Exception as exc:
                    click.echo(f"failed ({exc})")

            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            click.echo(f"\nAll sources updated. Cache fresh as of {now}")
        finally:
            await cache.close()

    asyncio.run(_run())


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind address")
@click.option("--port", default=8080, type=int, help="Port to listen on")
def serve(host, port):
    """Start the API server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("uvicorn not installed. Install with: pip install eol-tool[api]")
        raise SystemExit(1)

    click.echo(f"Starting EOL Tool API on {host}:{port}")
    uvicorn.run("eol_tool.api:app", host=host, port=port)
