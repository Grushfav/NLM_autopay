"""Detect and parse payroll CSV / Excel formats."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}

from src.calculator import PayBreakdown, calculate_pay, calculate_pay_from_sheet

# Legacy columns
LEGACY_REQUIRED = ["Name", "TRN", "NIS", "Rate", "Hours", "Allowance", "Email"]
LEGACY_OPTIONAL = ["YTD"]

# Payroll sheet (export from spreadsheet)
SHEET_REQUIRED = ["Employee", "Site", "Base Pay", "Regular hours"]
SHEET_OPTIONAL = ["OT Rate", "OT Hours", "Incentive", "TRN", "NIS", "Email", "YTD"]

SKIP_NAME_PATTERNS = re.compile(
    r"^(site\s*total|total|employee)$",
    re.IGNORECASE,
)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def _column_map(columns: list[str]) -> dict[str, str]:
    """Map lowercase stripped names to actual column headers."""
    return {c.strip().lower(): c for c in columns}


def detect_format(columns: list[str]) -> str:
    lower = {c.strip().lower() for c in columns}
    if "employee" in lower:
        return "payroll_sheet"
    if "name" in lower and "trn" in lower:
        return "legacy"
    return "unknown"


def _parse_optional_ytd(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    return parse_number(text)


def parse_number(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    text = str(value).strip()
    if not text or text.lower() in ("nan", "-", "—"):
        return 0.0
    text = text.replace("$", "").replace(",", "").strip()
    return float(text)


def _parse_optional_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _should_skip_row(employee_name: str) -> bool:
    if not employee_name:
        return True
    return bool(SKIP_NAME_PATTERNS.match(employee_name.strip()))


def _period_total_column(columns: list[str], col_map: dict[str, str]) -> str | None:
    known = {
        "employee",
        "site",
        "base pay",
        "regular hours",
        "ot rate",
        "ot hours",
        "double hours",
        "double rate hrs",
        "incentive",
        "trn",
        "nis",
        "email",
        "ytd",
        "name",
        "rate",
        "hours",
        "allowance",
    }
    extras = [c for c in columns if c.strip().lower() not in known]
    return extras[0] if extras else None


@dataclass
class ParsedEmployeeRow:
    row_number: int
    name: str
    site: str
    trn: str
    nis: str
    email: str
    pay: PayBreakdown
    ytd_override: float | None
    ytd_key: str


def _ytd_key(trn: str, site: str, name: str) -> str:
    if trn:
        return trn
    return f"{site}|{name}"


def parse_payroll_sheet_row(
    row: pd.Series,
    row_number: int,
    columns: list[str],
    col_map: dict[str, str],
) -> ParsedEmployeeRow | None:
    emp_col = col_map["employee"]
    name = _parse_optional_text(row.get(emp_col))
    if _should_skip_row(name):
        return None

    site = _parse_optional_text(row.get(col_map.get("site", ""), ""))
    base_pay = parse_number(row.get(col_map.get("base pay", ""), 0))
    regular_hours = parse_number(row.get(col_map.get("regular hours", ""), 0))
    ot_rate = parse_number(row.get(col_map.get("ot rate", ""), 0))
    ot_hours = parse_number(row.get(col_map.get("ot hours", ""), 0))
    incentive = parse_number(row.get(col_map.get("incentive", ""), 0))

    period_col = _period_total_column(columns, col_map)
    period_total = None
    if period_col:
        raw = row.get(period_col)
        if raw is not None and not (isinstance(raw, float) and pd.isna(raw)):
            parsed = parse_number(raw)
            if parsed > 0:
                period_total = parsed

    if base_pay < 0 or regular_hours < 0 or ot_hours < 0 or incentive < 0:
        raise ValueError("Pay amounts and hours must be non-negative")
    if not site:
        raise ValueError("Site is empty")

    trn = _parse_optional_text(row.get(col_map.get("trn", ""), ""))
    nis = _parse_optional_text(row.get(col_map.get("nis", ""), ""))
    email = _parse_optional_text(row.get(col_map.get("email", ""), ""))
    ytd_override = _parse_optional_ytd(row.get(col_map.get("ytd", ""), None))

    pay = calculate_pay_from_sheet(
        base_pay=base_pay,
        regular_hours=regular_hours,
        ot_rate=ot_rate,
        ot_hours=ot_hours,
        incentive=incentive,
        period_total=period_total,
    )

    return ParsedEmployeeRow(
        row_number=row_number,
        name=name,
        site=site,
        trn=trn,
        nis=nis,
        email=email,
        pay=pay,
        ytd_override=ytd_override,
        ytd_key=_ytd_key(trn, site, name),
    )


def parse_legacy_row(row: pd.Series, row_number: int) -> ParsedEmployeeRow | None:
    name = _parse_optional_text(row.get("Name"))
    if _should_skip_row(name):
        return None

    trn = _parse_optional_text(row.get("TRN"))
    nis = _parse_optional_text(row.get("NIS"))
    email = _parse_optional_text(row.get("Email"))
    rate = parse_number(row.get("Rate"))
    hours = parse_number(row.get("Hours"))
    allowance = parse_number(row.get("Allowance", 0))
    ytd_override = _parse_optional_ytd(row.get("YTD"))

    if not trn:
        raise ValueError("TRN is empty")
    if not nis:
        raise ValueError("NIS is empty")
    if not email or "@" not in email:
        raise ValueError("Invalid email address")
    if rate < 0 or hours < 0 or allowance < 0:
        raise ValueError("Rate, Hours, and Allowance must be non-negative")

    pay = calculate_pay(rate, hours, allowance)
    return ParsedEmployeeRow(
        row_number=row_number,
        name=name,
        site="",
        trn=trn,
        nis=nis,
        email=email,
        pay=pay,
        ytd_override=ytd_override,
        ytd_key=_ytd_key(trn, "", name),
    )


def required_columns_for_format(fmt: str) -> list[str]:
    if fmt == "payroll_sheet":
        return list(SHEET_REQUIRED)
    if fmt == "legacy":
        return list(LEGACY_REQUIRED)
    return []


def is_supported_payroll_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def _detect_header_row(raw: pd.DataFrame) -> int:
    """Find header row when Excel has title rows or repeated section headers."""
    for i in range(min(30, len(raw))):
        cells = [
            str(v).strip().lower()
            for v in raw.iloc[i].tolist()
            if v is not None and not (isinstance(v, float) and pd.isna(v))
        ]
        if "employee" in cells:
            return i
        if "name" in cells and "trn" in cells:
            return i
    return 0


def _read_excel(file_path: Path) -> pd.DataFrame:
    raw = pd.read_excel(file_path, header=None, engine="openpyxl")
    header_row = _detect_header_row(raw)
    df = pd.read_excel(file_path, header=header_row, engine="openpyxl")
    return _normalize_columns(df.dropna(how="all"))


def load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return _read_excel(path)
    if suffix == ".csv":
        return _normalize_columns(pd.read_csv(path))
    raise ValueError(
        f"Unsupported file type '{suffix}'. Use CSV or Excel (.xlsx)."
    )
