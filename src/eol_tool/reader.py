"""Read hardware models from spreadsheets and write results."""

import logging
from datetime import date, datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory
from .normalizer import normalize_model

logger = logging.getLogger(__name__)

_EXPECTED_HEADERS = {"model", "manufacturer", "category", "condition", "original_item"}

_RESULT_COLUMNS = [
    "Model",
    "Manufacturer",
    "Category",
    "Condition",
    "EOL Status",
    "EOL Date",
    "EOS Date",
    "Date Source",
    "Confidence",
    "Source",
    "Checked At",
    "Original_Item",
    "Notes",
    "EOL Reason",
    "Risk Category",
]

_STATUS_STYLES = {
    "eol": (Font(color="FF0000"), PatternFill(fgColor="FFE6E6", fill_type="solid")),
    "eol_announced": (Font(color="FF8C00"), PatternFill(fgColor="FFF3E0", fill_type="solid")),
    "active": (Font(color="008000"), PatternFill(fgColor="E6FFE6", fill_type="solid")),
    "unknown": (Font(color="666666"), PatternFill(fgColor="F0F0F0", fill_type="solid")),
    "not_found": (Font(color="999999"), PatternFill(fgColor="F5F5F5", fill_type="solid")),
}

_RISK_STYLES = {
    "security": (Font(color="8B0000"), PatternFill(fgColor="FFE0E0", fill_type="solid")),
    "support": (Font(color="FF8C00"), PatternFill(fgColor="FFF0E0", fill_type="solid")),
    "procurement": (Font(color="0000CD"), PatternFill(fgColor="E0E8FF", fill_type="solid")),
    "informational": (Font(color="808080"), PatternFill(fgColor="F0F0F0", fill_type="solid")),
}

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(fgColor="2F5496", fill_type="solid")

_DEFAULT_WIDTHS = {
    "Model": 30,
    "Manufacturer": 18,
    "Category": 14,
    "Condition": 12,
    "EOL Status": 16,
    "EOL Date": 14,
    "EOS Date": 14,
    "Date Source": 22,
    "Confidence": 12,
    "Source": 30,
    "Checked At": 22,
    "Original_Item": 30,
    "Notes": 40,
    "EOL Reason": 22,
    "Risk Category": 16,
}

_DATE_SOURCE_LABELS = {
    "manufacturer_confirmed": "Manufacturer Confirmed",
    "community_database": "Community Database",
    "none": "Not Available",
}


def read_results(path: Path) -> list[EOLResult]:
    """Read EOL results back from a results xlsx file.

    Expects a sheet named 'EOL Results' with the standard result columns.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["EOL Results"] if "EOL Results" in wb.sheetnames else wb.worksheets[0]

    rows = ws.iter_rows(values_only=True)
    raw_headers = next(rows)
    headers = [str(h).strip().lower().replace(" ", "_") for h in raw_headers if h is not None]

    results: list[EOLResult] = []
    for row in rows:
        values = dict(zip(headers, row))
        model_str = str(values.get("model") or "").strip()
        if not model_str:
            continue

        manufacturer = str(values.get("manufacturer") or "").strip()
        category = str(values.get("category") or "").strip() or "unknown"
        condition = str(values.get("condition") or "").strip()
        original_item = str(values.get("original_item") or "").strip()

        status_str = str(values.get("eol_status") or "unknown").strip().lower()
        try:
            status = EOLStatus(status_str)
        except ValueError:
            status = EOLStatus.UNKNOWN

        eol_date = None
        eol_date_raw = values.get("eol_date")
        if eol_date_raw:
            eol_date_str = str(eol_date_raw).strip()
            if eol_date_str:
                try:
                    if isinstance(eol_date_raw, date):
                        eol_date = eol_date_raw if isinstance(eol_date_raw, date) else None
                    else:
                        eol_date = date.fromisoformat(eol_date_str)
                except (ValueError, TypeError):
                    pass

        eos_date = None
        eos_date_raw = values.get("eos_date")
        if eos_date_raw:
            eos_date_str = str(eos_date_raw).strip()
            if eos_date_str:
                try:
                    if isinstance(eos_date_raw, date):
                        eos_date = eos_date_raw
                    else:
                        eos_date = date.fromisoformat(eos_date_str)
                except (ValueError, TypeError):
                    pass

        risk_str = str(values.get("risk_category") or "none").strip().lower()
        try:
            risk = RiskCategory(risk_str)
        except ValueError:
            risk = RiskCategory.NONE

        reason_str = str(values.get("eol_reason") or "none").strip().lower()
        try:
            reason = EOLReason(reason_str)
        except ValueError:
            reason = EOLReason.NONE

        confidence_raw = values.get("confidence")
        try:
            confidence = int(confidence_raw) if confidence_raw else 0
        except (ValueError, TypeError):
            confidence = 0

        checked_at_raw = values.get("checked_at")
        if isinstance(checked_at_raw, datetime):
            checked_at = checked_at_raw
        elif checked_at_raw:
            try:
                checked_at = datetime.fromisoformat(str(checked_at_raw).strip())
            except ValueError:
                checked_at = datetime.now()
        else:
            checked_at = datetime.now()

        source_name = str(values.get("source") or "").strip()
        date_source_raw = str(values.get("date_source") or "none").strip()
        # Reverse map display labels back to internal values
        _reverse_date_source = {v.lower(): k for k, v in _DATE_SOURCE_LABELS.items()}
        date_source = _reverse_date_source.get(date_source_raw.lower(), date_source_raw.lower())

        notes = str(values.get("notes") or "").strip()

        hw = HardwareModel(
            model=model_str,
            manufacturer=manufacturer,
            category=category,
            condition=condition,
            original_item=original_item,
        )

        results.append(
            EOLResult(
                model=hw,
                status=status,
                eol_date=eol_date,
                eos_date=eos_date,
                source_name=source_name,
                checked_at=checked_at,
                confidence=confidence,
                notes=notes,
                eol_reason=reason,
                risk_category=risk,
                date_source=date_source,
            )
        )

    wb.close()
    return results


def read_models(path: Path) -> list[HardwareModel]:
    """Read hardware models from an Excel spreadsheet.

    Expects a sheet named 'Models' (or the first sheet) with columns:
    Model, Manufacturer, Category, Condition, Original_Item.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Models"] if "Models" in wb.sheetnames else wb.worksheets[0]

    rows = ws.iter_rows(values_only=True)
    raw_headers = next(rows)
    headers = [str(h).strip().lower().replace(" ", "_") for h in raw_headers if h is not None]

    models: list[HardwareModel] = []
    for row_num, row in enumerate(rows, start=2):
        values = dict(zip(headers, row))
        model_str = str(values.get("model") or "").strip()
        if not model_str:
            continue

        manufacturer = str(values.get("manufacturer") or "").strip()
        if not manufacturer:
            logger.warning("Row %d: model '%s' has no manufacturer", row_num, model_str)

        category = str(values.get("category") or "").strip()
        if not category:
            category = "unknown"

        models.append(
            HardwareModel(
                model=normalize_model(model_str, manufacturer),
                manufacturer=manufacturer,
                category=category,
                condition=str(values.get("condition") or "").strip(),
                original_item=str(values.get("original_item") or "").strip(),
            )
        )

    wb.close()
    return models


def write_results(
    results: list[EOLResult],
    path: Path,
    filtered_rows: list[dict] | None = None,
) -> None:
    """Write EOL check results to an xlsx file with formatting."""
    wb = openpyxl.Workbook()

    # --- EOL Results sheet ---
    ws = wb.active
    ws.title = "EOL Results"

    # Header row
    for col, name in enumerate(_RESULT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for row_idx, r in enumerate(results, start=2):
        display_model = r.model.original_item if r.model.original_item else r.model.model
        ws.cell(row=row_idx, column=1, value=display_model)
        ws.cell(row=row_idx, column=2, value=r.model.manufacturer)
        ws.cell(row=row_idx, column=3, value=r.model.category)
        ws.cell(row=row_idx, column=4, value=r.model.condition)

        status_cell = ws.cell(row=row_idx, column=5, value=r.status.value)
        style = _STATUS_STYLES.get(r.status.value)
        if style:
            status_cell.font = style[0]
            status_cell.fill = style[1]

        ws.cell(row=row_idx, column=6, value=str(r.eol_date) if r.eol_date else "")
        ws.cell(row=row_idx, column=7, value=str(r.eos_date) if r.eos_date else "")
        ws.cell(
            row=row_idx, column=8,
            value=_DATE_SOURCE_LABELS.get(r.date_source, "Not Available"),
        )
        ws.cell(row=row_idx, column=9, value=r.confidence)
        ws.cell(row=row_idx, column=10, value=r.source_name)
        ws.cell(row=row_idx, column=11, value=r.checked_at.isoformat())
        ws.cell(row=row_idx, column=12, value=r.model.original_item)
        ws.cell(row=row_idx, column=13, value=r.notes)
        ws.cell(row=row_idx, column=14, value=r.eol_reason.value)

        risk_cell = ws.cell(row=row_idx, column=15, value=r.risk_category.value)
        risk_style = _RISK_STYLES.get(r.risk_category.value)
        if risk_style:
            risk_cell.font = risk_style[0]
            risk_cell.fill = risk_style[1]

    # Column widths
    for col, name in enumerate(_RESULT_COLUMNS, start=1):
        width = min(_DEFAULT_WIDTHS.get(name, 15), 50)
        ws.column_dimensions[get_column_letter(col)].width = width

    # Auto-filter and freeze
    ws.auto_filter.ref = f"A1:{get_column_letter(len(_RESULT_COLUMNS))}{len(results) + 1}"
    ws.freeze_panes = "A2"

    # --- Summary sheet ---
    ws_summary = wb.create_sheet("Summary")

    ws_summary.cell(row=1, column=1, value="EOL Results Summary")
    ws_summary.cell(row=1, column=1).font = Font(bold=True, size=14)

    ws_summary.cell(row=2, column=1, value="Generated At")
    ws_summary.cell(row=2, column=2, value=datetime.now().isoformat(timespec="seconds"))

    ws_summary.cell(row=3, column=1, value="Total Models Checked")
    ws_summary.cell(row=3, column=2, value=len(results))

    # Count by status
    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

    ws_summary.cell(row=4, column=1, value="Total EOL")
    ws_summary.cell(row=4, column=2, value=status_counts.get("eol", 0))
    ws_summary.cell(row=5, column=1, value="Total Active")
    ws_summary.cell(row=5, column=2, value=status_counts.get("active", 0))
    ws_summary.cell(row=6, column=1, value="Total Unknown")
    ws_summary.cell(row=6, column=2, value=status_counts.get("unknown", 0))

    # Count by risk category
    risk_counts: dict[str, int] = {}
    for r in results:
        risk_counts[r.risk_category.value] = risk_counts.get(r.risk_category.value, 0) + 1

    ws_summary.cell(row=7, column=1, value="Risk: Security")
    ws_summary.cell(row=7, column=2, value=risk_counts.get("security", 0))
    ws_summary.cell(row=8, column=1, value="Risk: Support")
    ws_summary.cell(row=8, column=2, value=risk_counts.get("support", 0))
    ws_summary.cell(row=9, column=1, value="Risk: Procurement")
    ws_summary.cell(row=9, column=2, value=risk_counts.get("procurement", 0))
    ws_summary.cell(row=10, column=1, value="Risk: Informational")
    ws_summary.cell(row=10, column=2, value=risk_counts.get("informational", 0))

    # Pivot: status counts by manufacturer
    row_offset = 12
    ws_summary.cell(row=row_offset, column=1, value="EOL Status by Manufacturer")
    ws_summary.cell(row=row_offset, column=1).font = Font(bold=True, size=12)

    mfr_status: dict[str, dict[str, int]] = {}
    for r in results:
        mfr = r.model.manufacturer or "(no manufacturer)"
        mfr_status.setdefault(mfr, {})
        sv = r.status.value
        mfr_status[mfr][sv] = mfr_status[mfr].get(sv, 0) + 1

    statuses = ["eol", "eol_announced", "active", "unknown", "not_found"]
    header_row = row_offset + 1
    ws_summary.cell(row=header_row, column=1, value="Manufacturer")
    ws_summary.cell(row=header_row, column=1).font = Font(bold=True)
    for ci, s in enumerate(statuses, start=2):
        cell = ws_summary.cell(row=header_row, column=ci, value=s)
        cell.font = Font(bold=True)

    for ri, (mfr, counts) in enumerate(sorted(mfr_status.items()), start=header_row + 1):
        ws_summary.cell(row=ri, column=1, value=mfr)
        for ci, s in enumerate(statuses, start=2):
            ws_summary.cell(row=ri, column=ci, value=counts.get(s, 0))

    # Auto-size summary columns
    ws_summary.column_dimensions["A"].width = 25
    for ci in range(2, len(statuses) + 2):
        ws_summary.column_dimensions[get_column_letter(ci)].width = 16

    # --- Filtered sheet (optional) ---
    if filtered_rows:
        ws_filtered = wb.create_sheet("Filtered")
        filtered_headers = ["Model", "Manufacturer", "Reason"]
        for col, name in enumerate(filtered_headers, start=1):
            cell = ws_filtered.cell(row=1, column=col, value=name)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
        for row_idx, f in enumerate(filtered_rows, start=2):
            ws_filtered.cell(row=row_idx, column=1, value=f["model"])
            ws_filtered.cell(row=row_idx, column=2, value=f["manufacturer"])
            ws_filtered.cell(row=row_idx, column=3, value=f["reason"])
        ws_filtered.column_dimensions["A"].width = 30
        ws_filtered.column_dimensions["B"].width = 20
        ws_filtered.column_dimensions["C"].width = 30

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    wb.close()
