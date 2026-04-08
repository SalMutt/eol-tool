"""CLI interface for eol-tool."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import click

from eol_tool import __version__

from .input_filter import filter_models
from .manufacturer_corrections import apply_manufacturer_corrections
from .models import EOLResult, EOLStatus, HardwareModel, RiskCategory
from .reader import read_models, write_results
from .registry import list_checkers as _list_checkers

# Checkers that have a refresh_cache classmethod, keyed by source name
_REFRESHABLE_SOURCES: dict[str, str] = {
    "endoflife.date": "eol_tool.checkers.endoflife_date:EndOfLifeDateChecker",
    "juniper": "eol_tool.checkers.juniper:JuniperChecker",
}

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    default="warning",
    help="Set logging verbosity",
)
@click.option("-v", "--verbose", is_flag=True, help="Shortcut to set log level to INFO")
def cli(log_level, verbose):
    """EOL Tool - Check end-of-life status for hardware models."""
    if verbose and log_level == "warning":
        log_level = "info"
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )


async def _run_with_progress(
    models_to_check: list[HardwareModel],
    concurrency: int,
    no_cache: bool,
    skip_fallback: bool,
    quiet: bool = False,
) -> list[EOLResult]:
    """Run check pipeline with CLI progress output."""
    import sys

    from .cache import ResultCache
    from .check_pipeline import run_check_pipeline
    from .models import EOLStatus

    cache_inst = ResultCache() if not no_cache else None

    def _progress(mfr_name, model_count, batch_results, mfr_idx, total_mfrs):
        if quiet:
            return
        eol = sum(1 for r in batch_results if r.status in (EOLStatus.EOL, EOLStatus.EOL_ANNOUNCED))
        active = sum(1 for r in batch_results if r.status == EOLStatus.ACTIVE)
        other = len(batch_results) - eol - active
        parts = []
        if eol:
            parts.append(f"{eol} eol")
        if active:
            parts.append(f"{active} active")
        if other:
            parts.append(f"{other} other")
        counts_str = ", ".join(parts) if parts else "all cached"
        line = (
            f"Checking {mfr_name}: {model_count} models..."
            f" done ({counts_str}) [{mfr_idx}/{total_mfrs} manufacturers]"
        )
        try:
            if sys.stderr.isatty():
                print(f"\r{line}\033[K", end="", file=sys.stderr, flush=True)
                if mfr_idx == total_mfrs:
                    print("", file=sys.stderr)
            else:
                print(line, file=sys.stderr)
        except (OSError, ValueError):
            pass

    try:
        results = await run_check_pipeline(
            models_to_check,
            concurrency=concurrency,
            use_cache=not no_cache,
            skip_fallback=skip_fallback,
            cache=cache_inst,
            progress_callback=_progress,
        )

        return results
    finally:
        if cache_inst:
            await cache_inst.close()


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
@click.option("--show-filtered", is_flag=True, help="List rows removed by the input filter")
@click.option("-q", "--quiet", is_flag=True, help="Suppress progress lines and scraper warnings")
@click.option("--show-warnings", is_flag=True, help="Show all individual warnings in detail")
def check(
    input_path, output_path, manufacturer, concurrency, dry_run, no_cache, skip_fallback,
    show_filtered, quiet, show_warnings,
):
    """Check EOL status for hardware models."""
    models = read_models(Path(input_path), show_warnings=show_warnings)

    if not quiet:
        click.echo(f"Loaded {len(models)} models")

    apply_manufacturer_corrections(models)

    models, filtered_rows = filter_models(models)
    if filtered_rows and not quiet:
        if show_filtered:
            click.echo(f"\nFiltered {len(filtered_rows)} junk rows:")
            for f in filtered_rows:
                click.echo(f"  {f['model']} \u2014 {f['reason']}")
        else:
            click.echo(
                f"Filtered {len(filtered_rows)} junk rows"
                " (use --show-filtered to list them)"
            )

    by_mfr: dict[str, list] = {}
    for m in models:
        by_mfr.setdefault(m.manufacturer, []).append(m)

    if not quiet:
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
        models_to_check = by_mfr[manufacturer]
    else:
        models_to_check = models

    checkers = _list_checkers()
    if not checkers:
        click.echo("\nNo checkers registered. Add checker modules to eol_tool/checkers/.")
        return

    if not quiet:
        click.echo("")
    results = asyncio.run(
        _run_with_progress(models_to_check, concurrency, no_cache, skip_fallback, quiet=quiet)
    )

    if output_path:
        write_results(results, Path(output_path), filtered_rows=filtered_rows)
        click.echo(f"\nResults written to {output_path}")

    # Save snapshot for diff comparison
    try:
        import json as _json
        from datetime import datetime as _dt
        from pathlib import Path as _P
        _data_dir = _P(__file__).resolve().parent.parent.parent / "data"
        _data_dir.mkdir(parents=True, exist_ok=True)
        _last = _data_dir / "last_run.json"
        _prev = _data_dir / "prev_run.json"
        if _last.exists():
            _last.replace(_prev)
        _snapshot = {
            "timestamp": _dt.now().isoformat(),
            "results": [
                {
                    "model": r.model.model,
                    "manufacturer": r.model.manufacturer,
                    "status": r.status.value,
                    "eol_date": str(r.eol_date) if r.eol_date else None,
                    "risk_category": r.risk_category.value,
                    "source": r.source_name,
                }
                for r in results
            ],
        }
        _tmp = _last.with_suffix(".json.tmp")
        with open(_tmp, "w") as _fh:
            _json.dump(_snapshot, _fh)
        _tmp.replace(_last)
    except Exception:
        pass  # Non-critical — don't break the CLI if snapshot fails


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
