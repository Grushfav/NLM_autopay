import logging
from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = ["Name", "TRN", "NIS", "Rate", "Hours", "Allowance", "Email"]
OPTIONAL_COLUMNS = ["YTD"]

logger = logging.getLogger(__name__)


@dataclass
class EmployeeRow:
    name: str
    trn: str
    nis: str
    rate: float
    hours: float
    allowance: float
    email: str
    ytd_override: float | None
    row_number: int


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _parse_optional_ytd(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _validate_row(row: pd.Series, row_number: int) -> EmployeeRow | None:
    try:
        name = str(row["Name"]).strip()
        trn = str(row["TRN"]).strip()
        nis = str(row["NIS"]).strip()
        email = str(row["Email"]).strip()
        rate = float(row["Rate"])
        hours = float(row["Hours"])
        allowance = float(row.get("Allowance", 0) or 0)
        ytd_override = _parse_optional_ytd(row.get("YTD"))

        if not name:
            raise ValueError("Name is empty")
        if not trn:
            raise ValueError("TRN is empty")
        if not email or "@" not in email:
            raise ValueError("Invalid email")
        if rate < 0 or hours < 0 or allowance < 0:
            raise ValueError("Rate, Hours, and Allowance must be non-negative")

        return EmployeeRow(
            name=name,
            trn=trn,
            nis=nis,
            rate=rate,
            hours=hours,
            allowance=allowance,
            email=email,
            ytd_override=ytd_override,
            row_number=row_number,
        )
    except Exception as exc:
        logger.warning("Skipping row %s: %s", row_number, exc)
        return None


def load_employees(file_path: str) -> tuple[list[EmployeeRow], list[str]]:
    df = pd.read_csv(file_path)
    df = _normalize_columns(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    employees: list[EmployeeRow] = []
    for idx, row in df.iterrows():
        row_number = int(idx) + 2
        parsed = _validate_row(row, row_number)
        if parsed:
            employees.append(parsed)

    if not employees:
        raise ValueError("No valid employee rows found in CSV")

    return employees, list(df.columns)
