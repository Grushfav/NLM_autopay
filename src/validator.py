import logging
from dataclasses import dataclass, field

import pandas as pd

from src.calculator import PayBreakdown, calculate_pay, format_jmd
from src.csv_processor import REQUIRED_COLUMNS, EmployeeRow, _normalize_columns, _parse_optional_ytd
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
    trn: str
    nis: str
    email: str
    rate: float
    hours: float
    allowance: float
    pay: PayBreakdown
    ytd: float
    ytd_source: str
    stored_ytd_before: float


@dataclass
class ValidationReport:
    filename: str
    columns: list[str]
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


def _try_parse_row(row: pd.Series, row_number: int) -> tuple[EmployeeRow | None, str | None]:
    try:
        name = str(row.get("Name", "")).strip()
        trn = str(row.get("TRN", "")).strip()
        nis = str(row.get("NIS", "")).strip()
        email = str(row.get("Email", "")).strip()
        rate = float(row["Rate"])
        hours = float(row["Hours"])
        allowance = float(row.get("Allowance", 0) or 0)
        ytd_override = _parse_optional_ytd(row.get("YTD"))

        if not name:
            raise ValueError("Name is empty")
        if not trn:
            raise ValueError("TRN is empty")
        if not nis:
            raise ValueError("NIS is empty")
        if not email or "@" not in email:
            raise ValueError("Invalid email address")
        if rate < 0:
            raise ValueError("Rate must be zero or positive")
        if hours < 0:
            raise ValueError("Hours must be zero or positive")
        if allowance < 0:
            raise ValueError("Allowance must be zero or positive")

        return (
            EmployeeRow(
                name=name,
                trn=trn,
                nis=nis,
                rate=rate,
                hours=hours,
                allowance=allowance,
                email=email,
                ytd_override=ytd_override,
                row_number=row_number,
            ),
            None,
        )
    except Exception as exc:
        return None, str(exc)


def validate_and_prepare(file_path: str, filename: str) -> ValidationReport:
    df = pd.read_csv(file_path)
    df = _normalize_columns(df)
    columns = list(df.columns)
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]

    report = ValidationReport(
        filename=filename,
        columns=columns,
        missing_columns=missing,
        total_rows=len(df),
    )

    if missing:
        return report

    tracker = YtdTracker()

    for idx, row in df.iterrows():
        row_number = int(idx) + 2
        raw_name = str(row.get("Name", "")).strip() or f"Row {row_number}"

        emp, err = _try_parse_row(row, row_number)
        if err:
            report.errors.append(RowError(row_number=row_number, raw_name=raw_name, message=err))
            continue

        pay = calculate_pay(emp.rate, emp.hours, emp.allowance)
        stored = tracker.stored_ytd(emp.trn)
        if emp.ytd_override is not None:
            ytd = emp.ytd_override
            ytd_source = "CSV override"
        else:
            ytd = stored + pay.net_pay
            ytd_source = "Calculated (stored + net)"

        report.prepared.append(
            PreparedEmployee(
                row_number=emp.row_number,
                name=emp.name,
                trn=emp.trn,
                nis=emp.nis,
                email=emp.email,
                rate=emp.rate,
                hours=emp.hours,
                allowance=emp.allowance,
                pay=pay,
                ytd=ytd,
                ytd_source=ytd_source,
                stored_ytd_before=stored,
            )
        )

    return report


def prepared_to_display(emp: PreparedEmployee) -> dict:
    pay = emp.pay
    return {
        "row_number": emp.row_number,
        "name": emp.name,
        "trn": emp.trn,
        "nis": emp.nis,
        "email": emp.email,
        "rate": emp.rate,
        "hours": emp.hours,
        "regular_units": pay.regular_units,
        "regular_amount": pay.regular_amount,
        "regular_amount_fmt": format_jmd(pay.regular_amount),
        "overtime_units": pay.overtime_units,
        "overtime_rate": pay.overtime_rate,
        "overtime_amount": pay.overtime_amount,
        "overtime_amount_fmt": format_jmd(pay.overtime_amount) if pay.overtime_units else "—",
        "allowance": emp.allowance,
        "allowance_fmt": format_jmd(emp.allowance),
        "net_pay": pay.net_pay,
        "net_pay_fmt": format_jmd(pay.net_pay),
        "ytd": emp.ytd,
        "ytd_fmt": format_jmd(emp.ytd),
        "ytd_source": emp.ytd_source,
    }
