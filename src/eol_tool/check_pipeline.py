"""Check pipeline for selecting the best EOL result from multiple checkers."""

import asyncio
import logging
from datetime import datetime

from .cache import ResultCache
from .checker import BaseChecker
from .checkers.endoflife_date import supplement_missing_dates
from .models import EOLResult, EOLStatus, HardwareModel
from .registry import get_checker, get_checkers

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


async def run_check_pipeline(
    models: list[HardwareModel],
    concurrency: int = 5,
    use_cache: bool = True,
    skip_fallback: bool = False,
    cache: ResultCache | None = None,
) -> list[EOLResult]:
    """Run all applicable checkers on a list of models and return best results.

    Groups models by manufacturer, builds the checker chain for each group,
    runs all checkers, and selects the best result per model.
    """
    by_mfr: dict[str, list[HardwareModel]] = {}
    for m in models:
        by_mfr.setdefault(m.manufacturer, []).append(m)

    own_cache = False
    cache_inst = cache
    if use_cache and cache_inst is None:
        cache_inst = ResultCache()
        own_cache = True
    elif not use_cache:
        cache_inst = None

    all_results: list[EOLResult] = []

    try:
        for mfr_name, mfr_models in sorted(by_mfr.items()):
            to_check: list[HardwareModel] = []
            if cache_inst:
                for m in mfr_models:
                    cached_result = await cache_inst.get(m.model, m.manufacturer)
                    if cached_result:
                        cached_result.model = m
                        all_results.append(cached_result)
                    else:
                        to_check.append(m)
            else:
                to_check = mfr_models

            if not to_check:
                continue

            checker_classes = []
            manual_cls = get_checker("__manual__")
            vendor_classes = get_checkers(mfr_name)
            generic_optics_cls = get_checker("__generic_optics__")
            techgen_cls = get_checker("__techgen__")
            fallback_cls = None if skip_fallback else get_checker("__fallback__")

            if manual_cls:
                checker_classes.append(manual_cls)
            checker_classes.extend(vendor_classes)
            if generic_optics_cls:
                checker_classes.append(generic_optics_cls)
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

            batch_results = []
            for i, m in enumerate(to_check):
                candidates = per_model_results[i]
                if candidates:
                    batch_results.append(select_best_result(candidates))
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

            if cache_inst:
                for r in batch_results:
                    await cache_inst.set(r)

            all_results.extend(batch_results)

        if not skip_fallback:
            logger.info("Supplementing missing dates from endoflife.date...")
            all_results = await supplement_missing_dates(all_results)

    finally:
        if own_cache and cache_inst:
            await cache_inst.close()

    return all_results


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
