"""Diff reporting for EOL check results."""

from datetime import datetime

from pydantic import BaseModel

from .models import EOLStatus, RiskCategory
from .reader import read_results


class DiffEntry(BaseModel):
    """A single change between two result sets."""

    model: str
    manufacturer: str
    category: str
    change_type: str  # status_change, new_eol_date, risk_escalation, new_model, removed_model
    previous_status: str | None = None
    current_status: str | None = None
    previous_risk: str | None = None
    current_risk: str | None = None
    previous_eol_date: str | None = None
    current_eol_date: str | None = None
    severity: str = "info"  # critical, warning, info
    description: str = ""


class DiffSummary(BaseModel):
    """Aggregate counts of changes."""

    active_to_eol: int = 0
    unknown_to_eol: int = 0
    eol_to_active: int = 0
    unknown_to_active: int = 0
    active_to_unknown: int = 0
    new_eol_dates: int = 0
    new_models: int = 0
    removed_models: int = 0
    risk_escalations: int = 0
    total_changes: int = 0


class DiffResult(BaseModel):
    """Full diff report between two result sets."""

    timestamp: datetime
    previous_file: str
    current_file: str
    previous_count: int
    current_count: int
    summary: DiffSummary
    changes: list[DiffEntry]


_EOL_STATUSES = {EOLStatus.EOL.value, EOLStatus.EOL_ANNOUNCED.value}
_ACTIVE_STATUSES = {EOLStatus.ACTIVE.value}
_UNKNOWN_STATUSES = {EOLStatus.UNKNOWN.value, EOLStatus.NOT_FOUND.value}

_RISK_ORDER = {
    RiskCategory.NONE.value: 0,
    RiskCategory.INFORMATIONAL.value: 1,
    RiskCategory.PROCUREMENT.value: 2,
    RiskCategory.SUPPORT.value: 3,
    RiskCategory.SECURITY.value: 4,
}

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _make_key(model_str: str, manufacturer: str) -> tuple[str, str]:
    return (model_str.strip().lower(), manufacturer.strip().lower())


def _is_eol(status: str) -> bool:
    return status in _EOL_STATUSES


def _is_active(status: str) -> bool:
    return status in _ACTIVE_STATUSES


def _is_unknown(status: str) -> bool:
    return status in _UNKNOWN_STATUSES


def _classify_severity(
    prev_status: str | None,
    curr_status: str | None,
    prev_risk: str | None,
    curr_risk: str | None,
    change_type: str,
) -> str:
    if change_type == "status_change":
        if prev_status and curr_status:
            if _is_active(prev_status) and _is_eol(curr_status):
                return "critical"
            if _is_unknown(prev_status) and _is_eol(curr_status):
                return "warning"
            if _is_active(prev_status) and _is_unknown(curr_status):
                return "warning"
        return "info"

    if change_type == "risk_escalation":
        if curr_risk == RiskCategory.SECURITY.value:
            return "critical"
        if curr_risk == RiskCategory.SUPPORT.value:
            return "warning"
        return "info"

    return "info"


def compare_results(previous_path: str, current_path: str) -> DiffResult:
    """Compare two results xlsx files and produce a structured diff."""
    prev_results = read_results(previous_path)
    curr_results = read_results(current_path)

    prev_map: dict[tuple[str, str], object] = {}
    for r in prev_results:
        key = _make_key(r.model.model, r.model.manufacturer)
        prev_map[key] = r

    curr_map: dict[tuple[str, str], object] = {}
    for r in curr_results:
        key = _make_key(r.model.model, r.model.manufacturer)
        curr_map[key] = r

    changes: list[DiffEntry] = []
    summary = DiffSummary()

    # Check matched and new models
    for key, curr in curr_map.items():
        prev = prev_map.get(key)
        if prev is None:
            summary.new_models += 1
            changes.append(
                DiffEntry(
                    model=curr.model.model,
                    manufacturer=curr.model.manufacturer,
                    category=curr.model.category,
                    change_type="new_model",
                    current_status=curr.status.value,
                    current_risk=curr.risk_category.value,
                    current_eol_date=str(curr.eol_date) if curr.eol_date else None,
                    severity="info",
                    description=f"New model: {curr.model.model} ({curr.status.value})",
                )
            )
            continue

        # Status changes
        if prev.status.value != curr.status.value:
            prev_s = prev.status.value
            curr_s = curr.status.value
            severity = _classify_severity(prev_s, curr_s, None, None, "status_change")

            if _is_active(prev_s) and _is_eol(curr_s):
                summary.active_to_eol += 1
            elif _is_unknown(prev_s) and _is_eol(curr_s):
                summary.unknown_to_eol += 1
            elif _is_eol(prev_s) and _is_active(curr_s):
                summary.eol_to_active += 1
            elif _is_unknown(prev_s) and _is_active(curr_s):
                summary.unknown_to_active += 1
            elif _is_active(prev_s) and _is_unknown(curr_s):
                summary.active_to_unknown += 1

            risk_label = ""
            if curr.risk_category.value != RiskCategory.NONE.value:
                risk_label = f" ({curr.risk_category.value} risk)"

            changes.append(
                DiffEntry(
                    model=curr.model.model,
                    manufacturer=curr.model.manufacturer,
                    category=curr.model.category,
                    change_type="status_change",
                    previous_status=prev_s,
                    current_status=curr_s,
                    previous_risk=prev.risk_category.value,
                    current_risk=curr.risk_category.value,
                    previous_eol_date=str(prev.eol_date) if prev.eol_date else None,
                    current_eol_date=str(curr.eol_date) if curr.eol_date else None,
                    severity=severity,
                    description=(
                        f"{curr.model.manufacturer} {curr.model.model}: "
                        f"{prev_s.title()} -> {curr_s.title()}{risk_label}"
                    ),
                )
            )

        # EOL date changes (only if status didn't change, or date appeared)
        prev_date = str(prev.eol_date) if prev.eol_date else None
        curr_date = str(curr.eol_date) if curr.eol_date else None
        if prev_date != curr_date and prev.status.value == curr.status.value:
            if curr_date and not prev_date:
                summary.new_eol_dates += 1
                changes.append(
                    DiffEntry(
                        model=curr.model.model,
                        manufacturer=curr.model.manufacturer,
                        category=curr.model.category,
                        change_type="new_eol_date",
                        previous_status=prev.status.value,
                        current_status=curr.status.value,
                        previous_eol_date=prev_date,
                        current_eol_date=curr_date,
                        severity="info",
                        description=(
                            f"{curr.model.manufacturer} {curr.model.model}: "
                            f"EOL date set to {curr_date}"
                        ),
                    )
                )

        # Risk escalation (only if status didn't change)
        if prev.status.value == curr.status.value:
            prev_risk_val = _RISK_ORDER.get(prev.risk_category.value, 0)
            curr_risk_val = _RISK_ORDER.get(curr.risk_category.value, 0)
            if curr_risk_val > prev_risk_val:
                summary.risk_escalations += 1
                severity = _classify_severity(
                    None, None, prev.risk_category.value, curr.risk_category.value,
                    "risk_escalation",
                )
                changes.append(
                    DiffEntry(
                        model=curr.model.model,
                        manufacturer=curr.model.manufacturer,
                        category=curr.model.category,
                        change_type="risk_escalation",
                        previous_status=prev.status.value,
                        current_status=curr.status.value,
                        previous_risk=prev.risk_category.value,
                        current_risk=curr.risk_category.value,
                        severity=severity,
                        description=(
                            f"{curr.model.manufacturer} {curr.model.model}: "
                            f"Risk {prev.risk_category.value} -> {curr.risk_category.value}"
                        ),
                    )
                )

    # Removed models
    for key, prev in prev_map.items():
        if key not in curr_map:
            summary.removed_models += 1
            changes.append(
                DiffEntry(
                    model=prev.model.model,
                    manufacturer=prev.model.manufacturer,
                    category=prev.model.category,
                    change_type="removed_model",
                    previous_status=prev.status.value,
                    previous_risk=prev.risk_category.value,
                    previous_eol_date=str(prev.eol_date) if prev.eol_date else None,
                    severity="info",
                    description=f"Removed: {prev.model.manufacturer} {prev.model.model}",
                )
            )

    summary.total_changes = len(changes)

    # Sort: critical first, then warning, then info; then manufacturer, then model
    changes.sort(
        key=lambda e: (_SEVERITY_ORDER.get(e.severity, 9), e.manufacturer.lower(), e.model.lower())
    )

    return DiffResult(
        timestamp=datetime.now(),
        previous_file=str(previous_path),
        current_file=str(current_path),
        previous_count=len(prev_results),
        current_count=len(curr_results),
        summary=summary,
        changes=changes,
    )


def format_diff_text(diff: DiffResult, verbose: bool = False) -> str:
    """Format the diff as plain text for terminal output and ntfy notifications."""
    if diff.summary.total_changes == 0:
        return "EOL Check Diff: No changes detected"

    lines: list[str] = []
    lines.append(f"EOL Check Diff: {diff.summary.total_changes} changes detected")

    by_severity: dict[str, list[DiffEntry]] = {"critical": [], "warning": [], "info": []}
    for entry in diff.changes:
        by_severity.setdefault(entry.severity, []).append(entry)

    for sev_label, sev_key in [("CRITICAL", "critical"), ("WARNING", "warning"), ("INFO", "info")]:
        entries = by_severity.get(sev_key, [])
        if not entries:
            continue
        lines.append("")
        lines.append(f"{sev_label} ({len(entries)}):")
        for entry in entries:
            if verbose:
                lines.append(f"  {entry.description}")
                if entry.change_type == "status_change":
                    if entry.previous_eol_date or entry.current_eol_date:
                        lines.append(
                            f"    EOL date: {entry.previous_eol_date or 'none'}"
                            f" -> {entry.current_eol_date or 'none'}"
                        )
                    if entry.previous_risk != entry.current_risk:
                        lines.append(
                            f"    Risk: {entry.previous_risk or 'none'}"
                            f" -> {entry.current_risk or 'none'}"
                        )
                elif entry.change_type == "new_eol_date":
                    lines.append(f"    Date: {entry.current_eol_date}")
                elif entry.change_type == "risk_escalation":
                    lines.append(
                        f"    Risk: {entry.previous_risk} -> {entry.current_risk}"
                    )
                elif entry.change_type in ("new_model", "removed_model"):
                    lines.append(f"    Category: {entry.category}")
            else:
                lines.append(f"  {entry.description}")

    # Summary line
    s = diff.summary
    eol_delta = s.active_to_eol + s.unknown_to_eol - s.eol_to_active
    active_delta = s.eol_to_active + s.unknown_to_active - s.active_to_eol - s.active_to_unknown
    unknown_delta = s.active_to_unknown - s.unknown_to_eol - s.unknown_to_active

    parts = []
    if diff.current_count or eol_delta:
        sign = "+" if eol_delta >= 0 else ""
        parts.append(f"EOL ({sign}{eol_delta})")
    if diff.current_count or active_delta:
        sign = "+" if active_delta >= 0 else ""
        parts.append(f"Active ({sign}{active_delta})")
    if diff.current_count or unknown_delta:
        sign = "+" if unknown_delta >= 0 else ""
        parts.append(f"Unknown ({sign}{unknown_delta})")

    if parts:
        new_removed = ""
        if s.new_models or s.removed_models:
            new_removed_parts = []
            if s.new_models:
                new_removed_parts.append(f"+{s.new_models} new")
            if s.removed_models:
                new_removed_parts.append(f"-{s.removed_models} removed")
            new_removed = ", " + ", ".join(new_removed_parts)
        lines.append("")
        lines.append(f"Summary: {', '.join(parts)}{new_removed}")

    return "\n".join(lines)


def format_diff_json(diff: DiffResult) -> str:
    """Serialize the full DiffResult to JSON."""
    return diff.model_dump_json(indent=2)


def has_critical_changes(diff: DiffResult) -> bool:
    """Return True if any changes have critical severity."""
    return any(e.severity == "critical" for e in diff.changes)
