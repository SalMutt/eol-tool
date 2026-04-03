"""Scheduled EOL checks with diff-based notifications."""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .cache import ResultCache
from .check_pipeline import run_check_pipeline
from .diff import compare_results, has_critical_changes
from .input_filter import filter_models
from .manufacturer_corrections import apply_manufacturer_corrections
from .notifier import send_ntfy, send_ntfy_error
from .reader import read_models, write_results

logger = logging.getLogger(__name__)


@dataclass
class ScheduleConfig:
    """Configuration for scheduled EOL checks."""

    input_path: str = ""
    results_dir: str = field(
        default_factory=lambda: os.environ.get("EOL_TOOL_RESULTS_DIR", "./results")
    )
    interval_hours: float = field(
        default_factory=lambda: float(os.environ.get("EOL_TOOL_SCHEDULE_INTERVAL", "24"))
    )
    ntfy_url: str = field(
        default_factory=lambda: os.environ.get("EOL_TOOL_NTFY_URL", "https://ntfy.sh")
    )
    ntfy_topic: str = field(
        default_factory=lambda: os.environ.get("EOL_TOOL_NTFY_TOPIC", "")
    )
    ntfy_token: str | None = field(
        default_factory=lambda: os.environ.get("EOL_TOOL_NTFY_TOKEN")
    )
    ntfy_priority: str = "default"
    notify_on: str = "warning"
    keep_results: int = 10
    concurrency: int = 2
    manufacturer: str = "all"


class ScheduledChecker:
    """Runs EOL checks on a schedule and notifies on changes."""

    def __init__(self, config: ScheduleConfig):
        self.config = config
        self._current_output: str | None = None

    async def run_once(self):
        """Run a single check cycle: check, diff, notify, prune."""
        results_dir = Path(self.config.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

        # 1. Load input
        models = read_models(Path(self.config.input_path))
        apply_manufacturer_corrections(models)
        models, _ = filter_models(models)

        # Filter by manufacturer if specified
        if self.config.manufacturer != "all":
            models = [m for m in models if m.manufacturer == self.config.manufacturer]

        logger.info("Checking %d models", len(models))

        # 2. Run check pipeline
        cache = ResultCache()
        try:
            results = await run_check_pipeline(
                models,
                concurrency=self.config.concurrency,
                use_cache=True,
                cache=cache,
            )
        finally:
            await cache.close()

        # 3. Write timestamped output
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        output_path = results_dir / f"eol-results-{ts}.xlsx"
        write_results(results, output_path)
        self._current_output = str(output_path)
        logger.info("Results written to %s", output_path)

        # 4. Find previous results and diff
        previous = self._find_previous_results()
        diff_result = None
        if previous:
            diff_result = compare_results(previous, str(output_path))
            logger.info(
                "Diff: %d changes (%s)",
                diff_result.summary.total_changes,
                "critical" if has_critical_changes(diff_result) else "no critical",
            )

            # 5. Send notification if changes detected
            if diff_result.summary.total_changes > 0:
                await send_ntfy(self.config, diff_result)
        else:
            logger.info("No previous results to compare against")

        # 6. Prune old results
        self._prune_old_results()

        return diff_result

    async def run_loop(self):
        """Run checks on the configured interval. Never crashes."""
        interval_seconds = self.config.interval_hours * 3600
        logger.info(
            "Starting scheduled checks every %.1f hours", self.config.interval_hours
        )

        while True:
            run_start = datetime.now()
            logger.info("Starting scheduled check at %s", run_start.isoformat())
            try:
                await self.run_once()
                logger.info("Check completed successfully")
            except Exception as exc:
                logger.error("Check failed: %s", exc)
                try:
                    await send_ntfy_error(self.config, str(exc))
                except Exception as notify_exc:
                    logger.error("Failed to send error notification: %s", notify_exc)

            logger.info("Next check in %.1f hours", self.config.interval_hours)
            await asyncio.sleep(interval_seconds)

    def _find_previous_results(self) -> str | None:
        """Find the most recent previous results file."""
        results_dir = Path(self.config.results_dir)
        if not results_dir.exists():
            return None

        files = sorted(results_dir.glob("eol-results-*.xlsx"), reverse=True)
        for f in files:
            if str(f) != self._current_output:
                return str(f)
        return None

    def _prune_old_results(self):
        """Keep only the last N results files."""
        results_dir = Path(self.config.results_dir)
        if not results_dir.exists():
            return

        files = sorted(results_dir.glob("eol-results-*.xlsx"), reverse=True)
        for old_file in files[self.config.keep_results :]:
            logger.info("Pruning old results: %s", old_file.name)
            old_file.unlink()
