"""Check pipeline for selecting the best EOL result from multiple checkers."""

import logging
from datetime import datetime

from .checker import BaseChecker
from .models import EOLResult, EOLStatus, HardwareModel

logger = logging.getLogger(__name__)


def select_best_result(results: list[EOLResult]) -> EOLResult:
    """Select the best result using 'dated beats dateless' logic.

    1. Filter out NOT_FOUND and UNKNOWN results.
    2. If none remain, return the first UNKNOWN, or a NOT_FOUND.
    3. Split remaining into dated (eol_date is not None) and dateless.
    4. If any dated results exist, pick from dated only:
       sort by checker priority (lower = better), then confidence (higher = better).
    5. If no dated results, pick from dateless the same way.
    """
    if not results:
        return EOLResult(
            model=HardwareModel(model="", manufacturer="", category=""),
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="",
            notes="no-results",
        )

    # Step 1: filter out NOT_FOUND and UNKNOWN
    actionable = [
        r for r in results
        if r.status not in (EOLStatus.NOT_FOUND, EOLStatus.UNKNOWN)
    ]

    # Step 2: nothing actionable — return first UNKNOWN, else first result
    if not actionable:
        for r in results:
            if r.status == EOLStatus.UNKNOWN:
                return r
        return results[0]

    # Step 3: split into dated / dateless
    dated = [r for r in actionable if r.eol_date is not None]
    dateless = [r for r in actionable if r.eol_date is None]

    # Step 4: prefer dated results
    if dated:
        dated.sort(key=lambda r: (r.checker_priority, -r.confidence))
        winner = dated[0]
        logger.debug(
            "Selected dated result: source=%s priority=%d confidence=%d eol_date=%s",
            winner.source_name, winner.checker_priority,
            winner.confidence, winner.eol_date,
        )
        return winner

    # Step 5: fall back to dateless
    dateless.sort(key=lambda r: (r.checker_priority, -r.confidence))
    winner = dateless[0]
    logger.debug(
        "Selected dateless result: source=%s priority=%d confidence=%d",
        winner.source_name, winner.checker_priority, winner.confidence,
    )
    return winner


async def run_all_checkers(
    model: HardwareModel, checkers: list[BaseChecker],
) -> EOLResult:
    """Run every applicable checker for a model and return the best result.

    Runs ALL checkers (doesn't stop at first hit), collects non-exception
    results, and uses select_best_result to pick the winner.
    """
    logger.debug(
        "Running %d checkers for %s: %s",
        len(checkers), model.model,
        ", ".join(type(c).__name__ for c in checkers),
    )
    results: list[EOLResult] = []

    for checker in checkers:
        try:
            result = await checker.check(model)
            result.checker_priority = checker.priority
            results.append(result)
        except Exception as exc:
            logger.warning(
                "Checker %s failed for %s: %s",
                type(checker).__name__, model.model, exc,
            )

    if not results:
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            source_name="",
            notes="all-checkers-failed",
        )

    return select_best_result(results)
