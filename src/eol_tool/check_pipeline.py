"""Check pipeline for selecting the best EOL result from multiple checkers."""

import asyncio
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta

from .cache import ResultCache
from .checker import BaseChecker
from .checkers.endoflife_date import EndOfLifeDateChecker, supplement_missing_dates
from .generation_dates import lookup_generation_dates
from .models import EOLReason, EOLResult, EOLStatus, HardwareModel
from .normalizer import _strip_colon_prefixes
from .registry import get_checker, get_checkers

logger = logging.getLogger(__name__)


def _strip_item_prefix(item: str) -> str:
    """Strip QuickBooks category/condition prefix from Item string.

    "PROCESSORS:NEW:Intel Xeon E3-1230 v5" -> "Intel Xeon E3-1230 v5"
    """
    return _strip_colon_prefixes(item.strip().upper()).strip()


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
    progress_callback: Callable[[str, int, list[EOLResult], int, int], None] | None = None,
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
    total_mfrs = len(by_mfr)
    mfr_index = 0

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
                mfr_index += 1
                if progress_callback:
                    progress_callback(mfr_name, len(mfr_models), [], mfr_index, total_mfrs)
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
                no_checker_results = []
                for m in to_check:
                    r = EOLResult(
                        model=m,
                        status=EOLStatus.UNKNOWN,
                        checked_at=datetime.now(),
                        source_name="",
                        notes="no-checker-available",
                    )
                    no_checker_results.append(r)
                all_results.extend(no_checker_results)
                mfr_index += 1
                if progress_callback:
                    progress_callback(
                        mfr_name, len(mfr_models), no_checker_results,
                        mfr_index, total_mfrs,
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

            mfr_index += 1
            if progress_callback:
                progress_callback(
                    mfr_name, len(mfr_models), batch_results,
                    mfr_index, total_mfrs,
                )

        if not skip_fallback:
            logger.info("Supplementing missing dates from endoflife.date...")
            all_results = await supplement_missing_dates(all_results)

        # Tier 2: Item string fallback — retry endoflife.date with the
        # human-readable original_item when the MPN-based check found no dates.
        if not skip_fallback:
            all_results = await _tier2_item_fallback(all_results)

        # Tier 3: Generation-based approximate dates for anything still missing.
        _tier3_generation_dates(all_results)

        # Tier 4: Derive status from dates when checker returned unknown.
        _derive_status_from_dates(all_results)

        # Tier 5: Consistency — correct status/date contradictions.
        _fix_status_date_contradictions(all_results)

        # Tier 6: Estimate EOL dates for EOL models that have release but no EOL.
        _estimate_eol_from_lifecycle(all_results)

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


# ------------------------------------------------------------------
# Tier 2: Item-string fallback
# ------------------------------------------------------------------


async def _tier2_item_fallback(results: list[EOLResult]) -> list[EOLResult]:
    """Retry endoflife.date with the original_item for models with no dates.

    When the MPN-based check returned no release_date AND no eol_date,
    and the model has an original_item that differs from the model string,
    clean the item string and try the endoflife.date checker with it.
    """
    needs_retry: list[EOLResult] = [
        r for r in results
        if r.release_date is None
        and r.eol_date is None
        and r.model.original_item
        and r.model.original_item.strip() != r.model.model.strip()
    ]
    if not needs_retry:
        return results

    # Build temporary models from cleaned item strings
    retry_pairs: list[tuple[EOLResult, HardwareModel]] = []
    for r in needs_retry:
        cleaned = _strip_item_prefix(r.model.original_item)
        if not cleaned or cleaned == r.model.model.upper():
            continue
        temp_model = HardwareModel(
            model=cleaned,
            manufacturer=r.model.manufacturer,
            category=r.model.category,
            condition=r.model.condition,
            original_item=r.model.original_item,
        )
        retry_pairs.append((r, temp_model))

    if not retry_pairs:
        return results

    logger.info(
        "Tier 2: retrying %d models with original_item via endoflife.date",
        len(retry_pairs),
    )

    try:
        checker = EndOfLifeDateChecker()
        async with checker:
            temp_models = [pair[1] for pair in retry_pairs]
            date_results = await checker.check_batch(temp_models)
            for (original_result, _temp_model), date_result in zip(
                retry_pairs, date_results
            ):
                if date_result.release_date or date_result.eol_date:
                    if date_result.release_date:
                        original_result.release_date = date_result.release_date
                    if date_result.eol_date:
                        original_result.eol_date = date_result.eol_date
                    if date_result.eos_date and not original_result.eos_date:
                        original_result.eos_date = date_result.eos_date
                    original_result.date_source = date_result.date_source
                    note = "dates-from-item-string-fallback"
                    if original_result.notes:
                        original_result.notes = f"{original_result.notes}; {note}"
                    else:
                        original_result.notes = note
    except Exception:
        logger.warning("Tier 2 item fallback failed", exc_info=True)

    return results


# ------------------------------------------------------------------
# Tier 3: Generation-based approximate dates
# ------------------------------------------------------------------


def _tier3_generation_dates(results: list[EOLResult]) -> None:
    """Fill missing dates from the generation_dates.csv lookup table.

    Modifies results in place. Only touches models where BOTH release_date
    and eol_date are still None after Tiers 1 and 2.
    """
    filled = 0
    for r in results:
        if r.release_date is not None or r.eol_date is not None:
            continue
        gen = lookup_generation_dates(
            r.model.model,
            r.notes or "",
            r.model.manufacturer,
            r.model.category,
            r.model.original_item,
        )
        if not gen:
            continue
        if gen["release_date"]:
            r.release_date = gen["release_date"]
        if gen["eol_estimate"] and r.eol_date is None:
            r.eol_date = gen["eol_estimate"]
        if r.date_source == "none":
            r.date_source = gen["source"]
        note = f"generation-estimate:{gen['pattern']}"
        if r.notes:
            r.notes = f"{r.notes}; {note}"
        else:
            r.notes = note
        filled += 1
    if filled:
        logger.info("Tier 3: filled dates for %d models from generation data", filled)


# ------------------------------------------------------------------
# Tier 4: Derive status from dates
# ------------------------------------------------------------------


def _derive_status_from_dates(results: list[EOLResult]) -> None:
    """Derive EOL status from dates when checker returned unknown.

    When a checker returned UNKNOWN but post-processing (generation dates,
    endoflife.date, etc.) filled in dates, use those dates to set a status.
    Modifies results in place.
    """
    today = date.today()
    derived = 0
    for r in results:
        if r.status != EOLStatus.UNKNOWN:
            continue
        if not r.release_date and not r.eol_date:
            continue
        if r.eol_date and r.eol_date <= today:
            r.status = EOLStatus.EOL
            r.confidence = max(r.confidence, 50)
            if not r.eol_reason or r.eol_reason == EOLReason.NONE:
                r.eol_reason = EOLReason.TECHNOLOGY_GENERATION
            r.notes = (r.notes or "") + "; status-derived-from-dates"
        elif r.eol_date and r.eol_date > today:
            r.status = EOLStatus.EOL_ANNOUNCED
            r.confidence = max(r.confidence, 50)
            r.notes = (r.notes or "") + "; eol-announced-from-dates"
        elif r.release_date and not r.eol_date:
            r.status = EOLStatus.ACTIVE
            r.confidence = max(r.confidence, 40)
            r.notes = (r.notes or "") + "; status-derived-from-dates"
        else:
            continue
        derived += 1
    if derived:
        logger.info("Tier 4: derived status for %d models from dates", derived)


# ------------------------------------------------------------------
# Tier 5: Fix status/date contradictions
# ------------------------------------------------------------------


def _fix_status_date_contradictions(results: list[EOLResult]) -> None:
    """Correct status when it contradicts the dates.

    - active with past EOL or EOS date → eol
    - eol_announced with past EOL date → eol
    """
    today = date.today()
    corrected = 0
    for r in results:
        if r.status == EOLStatus.ACTIVE and r.eol_date and r.eol_date <= today:
            r.status = EOLStatus.EOL
            r.notes = (r.notes or "") + "; corrected-active-to-eol-past-eol-date"
            corrected += 1
        elif r.status == EOLStatus.ACTIVE and r.eos_date and r.eos_date <= today:
            r.status = EOLStatus.EOL
            r.notes = (r.notes or "") + "; corrected-active-to-eol-past-eos-date"
            corrected += 1
        elif (
            r.status == EOLStatus.EOL_ANNOUNCED
            and r.eol_date
            and r.eol_date <= today
        ):
            r.status = EOLStatus.EOL
            r.notes = (r.notes or "") + "; corrected-announced-to-eol-past-date"
            corrected += 1
    if corrected:
        logger.info(
            "Tier 5: corrected %d status/date contradictions", corrected,
        )


# ------------------------------------------------------------------
# Tier 6: Lifecycle-based EOL date estimation
# ------------------------------------------------------------------

_LIFECYCLE_YEARS: dict[str, int] = {
    "cpu": 5,
    "memory": 7,
    "ssd": 5,
    "drive": 5,
    "nic": 7,
    "switch": 7,
    "raid": 7,
    "gpu": 5,
    "server-board": 5,
    "server": 7,
    "cooling": 10,
    "chassis": 10,
    "optic": 7,
    "firewall": 7,
}


def _estimate_eol_from_lifecycle(results: list[EOLResult]) -> None:
    """Estimate EOL date for EOL models that have a release date but no EOL date.

    Uses category-based typical lifecycle durations. Only sets dates that
    fall in the past (won't invent future EOL dates for items already EOL).
    """
    today = date.today()
    filled = 0
    for r in results:
        if r.status != EOLStatus.EOL:
            continue
        if r.eol_date is not None:
            continue
        if r.release_date is None:
            continue
        years = _LIFECYCLE_YEARS.get(r.model.category.lower(), 5)
        estimated_eol = r.release_date + timedelta(days=years * 365)
        if estimated_eol <= today:
            r.eol_date = estimated_eol
            r.date_source = (r.date_source or "") + "+lifecycle-estimate"
            r.notes = (r.notes or "") + f"; eol-estimated-{years}yr-lifecycle"
            filled += 1
    if filled:
        logger.info("Tier 6: estimated EOL dates for %d models via lifecycle", filled)
