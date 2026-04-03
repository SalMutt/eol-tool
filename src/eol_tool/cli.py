"""CLI interface for eol-tool."""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

import click

from eol_tool import __version__

from .diff import compare_results, format_diff_json, format_diff_text, has_critical_changes
from .input_filter import filter_models
from .manufacturer_corrections import apply_manufacturer_corrections
from .models import EOLResult, EOLStatus, HardwareModel, RiskCategory
from .reader import read_models, split_results_for_retry, write_results
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


async def _run_with_progress(
    models_to_check: list[HardwareModel],
    concurrency: int,
    no_cache: bool,
    skip_fallback: bool,
) -> list[EOLResult]:
    """Run check pipeline with CLI progress output."""
    from .cache import ResultCache
    from .check_pipeline import run_check_pipeline

    cache_inst = ResultCache() if not no_cache else None

    try:
        by_mfr: dict[str, list[HardwareModel]] = {}
        for m in models_to_check:
            by_mfr.setdefault(m.manufacturer, []).append(m)

        for mfr_name, mfr_models in sorted(by_mfr.items()):
            if cache_inst:
                cached_count = 0
                for m in mfr_models:
                    if await cache_inst.get(m.model, m.manufacturer):
                        cached_count += 1
                to_check = len(mfr_models) - cached_count
                if cached_count:
                    click.echo(
                        f"  {mfr_name}: {cached_count} cached, {to_check} to check"
                    )
                if to_check:
                    click.echo(f"Checking {mfr_name}: {to_check} models...")
            else:
                click.echo(f"Checking {mfr_name}: {len(mfr_models)} models...")

        results = await run_check_pipeline(
            models_to_check,
            concurrency=concurrency,
            use_cache=not no_cache,
            skip_fallback=skip_fallback,
            cache=cache_inst,
        )

        counts: dict[str, int] = {}
        for r in results:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        parts = [
            f"{counts.get(s, 0)} {s}"
            for s in ["eol", "active", "unknown"]
            if counts.get(s, 0)
        ]
        if parts:
            click.echo(f"  Done: {', '.join(parts)}")

        return results
    finally:
        if cache_inst:
            await cache_inst.close()


@cli.command()
@click.option(
    "--input", "input_path", type=click.Path(exists=True), default=None,
    help="Path to input spreadsheet",
)
@click.option("--output", "output_path", type=click.Path(), default=None, help="Output file path")
@click.option("--manufacturer", default="all", help="Manufacturer to check (or 'all')")
@click.option("--concurrency", default=5, type=int, help="Max concurrent requests")
@click.option("--dry-run", is_flag=True, help="Load models and show summary without checking")
@click.option("--no-cache", is_flag=True, help="Skip the result cache")
@click.option("--skip-fallback", is_flag=True, help="Skip the endoflife.date fallback checker")
@click.option("--show-filtered", is_flag=True, help="List rows removed by the input filter")
@click.option("--diff", "diff_path", type=click.Path(exists=True), default=None,
               help="Previous results xlsx to diff against after checking")
@click.option("--retry-unknowns", "retry_path", type=click.Path(exists=True), default=None,
              help="Re-check only UNKNOWN and NOT_FOUND models from a previous results file")
def check(
    input_path, output_path, manufacturer, concurrency, dry_run, no_cache, skip_fallback,
    show_filtered, diff_path, retry_path,
):
    """Check EOL status for hardware models."""
    if retry_path:
        _check_retry(retry_path, output_path, manufacturer, concurrency, no_cache,
                     skip_fallback, diff_path)
        return

    if not input_path:
        raise click.UsageError("--input is required (unless using --retry-unknowns)")

    models = read_models(Path(input_path))
    click.echo(f"Loaded {len(models)} models")

    apply_manufacturer_corrections(models)

    models, filtered_rows = filter_models(models)
    if filtered_rows:
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

    click.echo("")
    results = asyncio.run(
        _run_with_progress(models_to_check, concurrency, no_cache, skip_fallback)
    )

    if output_path:
        write_results(results, Path(output_path), filtered_rows=filtered_rows)
        click.echo(f"\nResults written to {output_path}")

    _print_summary_table(results)

    # Diff against previous results if requested
    if diff_path and output_path:
        click.echo("")
        diff_result = compare_results(diff_path, output_path)
        click.echo(format_diff_text(diff_result))
        if has_critical_changes(diff_result):
            raise SystemExit(1)


def _check_retry(retry_path, output_path, manufacturer, concurrency, no_cache, skip_fallback,
                 diff_path):
    """Handle --retry-unknowns: re-check only UNKNOWN/NOT_FOUND models from previous results."""
    mfr_filter = manufacturer if manufacturer != "all" else None
    already_classified, retry_models = split_results_for_retry(
        Path(retry_path), manufacturer=mfr_filter,
    )
    click.echo(
        f"Retrying {len(retry_models)} unknown/not-found models from previous run"
        f" (skipping {len(already_classified)} already classified)"
    )

    if not retry_models:
        click.echo("Nothing to retry — all models are already classified.")
        if output_path:
            write_results(already_classified, Path(output_path))
            click.echo(f"\nResults written to {output_path}")
        return

    checkers = _list_checkers()
    if not checkers:
        click.echo("\nNo checkers registered. Add checker modules to eol_tool/checkers/.")
        return

    click.echo("")
    new_results = asyncio.run(
        _run_with_progress(retry_models, concurrency, no_cache, skip_fallback)
    )

    # Merge: already classified + new results for retried models
    merged = list(already_classified) + list(new_results)

    # Count how many unknowns got resolved
    still_unknown = sum(
        1 for r in new_results
        if r.status in (EOLStatus.UNKNOWN, EOLStatus.NOT_FOUND)
    )
    resolved = len(retry_models) - still_unknown
    click.echo(
        f"\nResolved {resolved} of {len(retry_models)} unknowns"
        f" ({still_unknown} remain)"
    )

    if output_path:
        write_results(merged, Path(output_path))
        click.echo(f"Results written to {output_path}")

    _print_summary_table(merged)

    # Diff against the retry-unknowns file if --diff is also provided
    effective_diff_path = diff_path or retry_path
    if output_path:
        click.echo("")
        diff_result = compare_results(str(effective_diff_path), output_path)
        click.echo(format_diff_text(diff_result))
        if has_critical_changes(diff_result):
            raise SystemExit(1)


def _print_summary_table(results: list[EOLResult]) -> None:
    """Print the manufacturer/status/risk summary table."""
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


@cli.command("diff")
@click.option("--previous", required=True, type=click.Path(exists=True),
              help="Path to previous results xlsx")
@click.option("--current", required=True, type=click.Path(exists=True),
              help="Path to current results xlsx")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text",
              help="Output format")
@click.option("--verbose", is_flag=True, help="Show full details in text format")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Write diff to a file instead of stdout")
def diff_cmd(previous, current, output_format, verbose, output_path):
    """Compare two result sets and show what changed."""
    diff_result = compare_results(previous, current)

    if output_format == "json":
        output = format_diff_json(diff_result)
    else:
        output = format_diff_text(diff_result, verbose=verbose)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(output, encoding="utf-8")
        click.echo(f"Diff written to {output_path}")
    else:
        click.echo(output)

    if has_critical_changes(diff_result):
        raise SystemExit(1)


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


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True),
              help="Input xlsx file")
@click.option("--results-dir", "results_dir", default=None,
              help="Directory for timestamped results")
@click.option("--interval", "interval_hours", default=None, type=float,
              help="Check interval in hours (default: 24)")
@click.option("--ntfy-url", "ntfy_url", default=None, help="ntfy server URL")
@click.option("--topic", "ntfy_topic", default=None, help="ntfy topic name (required)")
@click.option("--ntfy-token", "ntfy_token", default=None,
              help="ntfy auth token (also reads EOL_TOOL_NTFY_TOKEN)")
@click.option("--notify-on", "notify_on", default=None,
              type=click.Choice(["critical", "warning", "all", "none"]),
              help="When to notify (default: warning)")
@click.option("--keep-results", "keep_results", default=None, type=int,
              help="Number of result files to keep (default: 10)")
@click.option("--concurrency", default=None, type=int, help="Checker concurrency (default: 2)")
@click.option("--manufacturer", default=None, help="Filter to specific manufacturer (default: all)")
@click.option("--run-once", "run_once", is_flag=True, help="Run a single check and exit")
@click.option("--dry-run", is_flag=True, help="Run check but don't send notifications")
def schedule(
    input_path, results_dir, interval_hours, ntfy_url, ntfy_topic, ntfy_token,
    notify_on, keep_results, concurrency, manufacturer, run_once, dry_run,
):
    """Run scheduled EOL checks with ntfy notifications."""
    from .scheduler import ScheduleConfig, ScheduledChecker

    # Build config from env var defaults, then override with CLI flags
    config = ScheduleConfig(input_path=input_path)

    if results_dir is not None:
        config.results_dir = results_dir
    if interval_hours is not None:
        config.interval_hours = interval_hours
    if ntfy_url is not None:
        config.ntfy_url = ntfy_url
    if ntfy_topic is not None:
        config.ntfy_topic = ntfy_topic
    if ntfy_token is not None:
        config.ntfy_token = ntfy_token
    if notify_on is not None:
        config.notify_on = notify_on
    if keep_results is not None:
        config.keep_results = keep_results
    if concurrency is not None:
        config.concurrency = concurrency
    if manufacturer is not None:
        config.manufacturer = manufacturer

    if dry_run:
        config.notify_on = "none"

    if not config.ntfy_topic:
        click.echo("Error: --topic is required (or set EOL_TOOL_NTFY_TOPIC)")
        raise SystemExit(1)

    Path(config.results_dir).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    click.echo(
        f"Starting scheduled EOL checks every {config.interval_hours} hours, "
        f"notifying {config.ntfy_topic} on {config.notify_on} changes"
    )

    checker = ScheduledChecker(config)

    if run_once:
        from .diff import has_critical_changes as _has_critical

        diff_result = asyncio.run(checker.run_once())
        if diff_result and _has_critical(diff_result):
            raise SystemExit(1)
    else:
        asyncio.run(checker.run_loop())


@cli.command()
@click.option("--topic", required=True, help="ntfy topic name")
@click.option("--message", required=True, help="Message to send")
@click.option("--ntfy-url", "ntfy_url", default=None, help="ntfy server URL (default: https://ntfy.sh)")
@click.option("--ntfy-token", "ntfy_token", default=None, help="ntfy auth token")
@click.option("--priority", default="3", help="Notification priority 1-5 (default: 3)")
def notify(topic, message, ntfy_url, ntfy_token, priority):
    """Send a test notification to verify ntfy configuration."""
    import httpx

    url_base = ntfy_url or os.environ.get("EOL_TOOL_NTFY_URL", "https://ntfy.sh")
    token = ntfy_token or os.environ.get("EOL_TOOL_NTFY_TOKEN")

    headers = {
        "Title": "EOL Tool Test",
        "Priority": priority,
        "Tags": "test_tube",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{url_base.rstrip('/')}/{topic}"

    try:
        resp = httpx.post(url, content=message, headers=headers, timeout=10.0)
        resp.raise_for_status()
        click.echo(f"Notification sent to {topic}")
    except Exception as exc:
        click.echo(f"Failed to send notification: {exc}")
        raise SystemExit(1)
