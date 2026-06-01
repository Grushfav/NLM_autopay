import logging
from dataclasses import dataclass, field

from src.calculator import PayBreakdown, format_jmd
from src.csv_formats import (
    detect_format,
    load_dataframe,
    parse_legacy_row,
    parse_payroll_sheet_row,
    required_columns_for_format,
)
from src.ytd import YtdTracker

logger = logging.getLogger(__name__)


@dataclass
class RowError:
    row_number: int
    raw_name: str
    message: str


@dataclass
class PreparedEmployee:
    row_number: int
    name: str
    site: str
    trn: str
    nis: str
    email: str
    pay: PayBreakdown
    ytd: float
    ytd_source: str
    stored_ytd_before: float
    ytd_key: str


@dataclass
class ValidationReport:
    filename: str
    columns: list[str]
    format: str
    missing_columns: list[str]
    prepared: list[PreparedEmployee] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    total_rows: int = 0

    @property
    def valid_count(self) -> int:
        return len(self.prepared)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def can_send(self) -> bool:
        return self.valid_count > 0 and not self.missing_columns


def validate_and_prepare(file_path: str, filename: str) -> ValidationReport:
    df = load_dataframe(file_path)
    columns = list(df.columns)
    fmt = detect_format(columns)
    missing = [
        c
        for c in required_columns_for_format(fmt)
        if c.strip().lower() not in {x.strip().lower() for x in columns}
    ]

    report = ValidationReport(
        filename=filename,
        columns=columns,
        format=fmt,
        missing_columns=missing,
        total_rows=len(df),
    )

    if missing or fmt == "unknown":
        if fmt == "unknown" and not missing:
            report.missing_columns = [
                "Employee, Site, Base Pay, Regular hours (payroll sheet) "
                "or Name, TRN, NIS, Rate, Hours, Allowance, Email (legacy)"
            ]
        return report

    col_map = {c.strip().lower(): c for c in columns}
    tracker = YtdTracker()

    for idx, row in df.iterrows():
        row_number = int(idx) + 2
        raw_name = str(row.get(col_map.get("employee", col_map.get("name", "")), "")).strip()
        if not raw_name or raw_name.lower() == "nan":
            raw_name = f"Row {row_number}"

        try:
            if fmt == "payroll_sheet":
                parsed = parse_payroll_sheet_row(row, row_number, columns, col_map)
            else:
                parsed = parse_legacy_row(row, row_number)

            if parsed is None:
                continue

            stored = tracker.stored_ytd(parsed.ytd_key)
            if parsed.ytd_override is not None:
                ytd = parsed.ytd_override
                ytd_source = "CSV override"
            else:
                ytd = stored + parsed.pay.net_pay
                ytd_source = "Calculated (stored + net)"

            report.prepared.append(
                PreparedEmployee(
                    row_number=parsed.row_number,
                    name=parsed.name,
                    site=parsed.site,
                    trn=parsed.trn,
                    nis=parsed.nis,
                    email=parsed.email,
                    pay=parsed.pay,
                    ytd=ytd,
                    ytd_source=ytd_source,
                    stored_ytd_before=stored,
                    ytd_key=parsed.ytd_key,
                )
            )
        except Exception as exc:
            logger.warning("Row %s: %s", row_number, exc)
            report.errors.append(
                RowError(row_number=row_number, raw_name=raw_name, message=str(exc))
            )

    return report


def prepared_to_display(emp: PreparedEmployee) -> dict:
    pay = emp.pay
    return {
        "row_number": emp.row_number,
        "name": emp.name,
        "site": emp.site or "—",
        "trn": emp.trn or "—",
        "nis": emp.nis or "—",
        "email": emp.email or "—",
        "rate": pay.regular_rate,
        "hours": pay.regular_units,
        "regular_units": pay.regular_units,
        "regular_amount": pay.regular_amount,
        "regular_amount_fmt": format_jmd(pay.regular_amount),
        "overtime_units": pay.overtime_units,
        "overtime_rate": pay.overtime_rate,
        "overtime_amount": pay.overtime_amount,
        "overtime_amount_fmt": format_jmd(pay.overtime_amount) if pay.overtime_units else "—",
        "allowance": pay.allowance,
        "allowance_fmt": format_jmd(pay.allowance) if pay.allowance else "—",
        "net_pay": pay.net_pay,
        "net_pay_fmt": format_jmd(pay.net_pay),
        "ytd": emp.ytd,
        "ytd_fmt": format_jmd(emp.ytd),
        "ytd_source": emp.ytd_source,
    }
