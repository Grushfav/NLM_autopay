import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from nlm_autopay.models import EmployeeRecord

REQUIRED_COLUMNS = ("Name", "Email", "Rate", "Hours", "Allowance", "Period")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value.strip()))


def _to_decimal(value, field: str, row_index: int) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(
            f"Row {row_index}: invalid numeric value for {field!r}: {value!r}"
        ) from exc


def _parse_row(row: pd.Series, row_index: int) -> EmployeeRecord:
    missing = [col for col in REQUIRED_COLUMNS if pd.isna(row.get(col)) or str(row.get(col)).strip() == ""]
    if missing:
        raise ValueError(f"Row {row_index}: missing required fields: {', '.join(missing)}")

    name = str(row["Name"]).strip()
    email = str(row["Email"]).strip()
    period = str(row["Period"]).strip()

    if not _is_valid_email(email):
        raise ValueError(f"Row {row_index}: invalid email address: {email!r}")

    rate = _to_decimal(row["Rate"], "Rate", row_index)
    hours = _to_decimal(row["Hours"], "Hours", row_index)
    allowance = _to_decimal(row["Allowance"], "Allowance", row_index)

    if rate < 0 or hours < 0 or allowance < 0:
        raise ValueError(f"Row {row_index}: Rate, Hours, and Allowance must be non-negative")

    return EmployeeRecord(
        name=name,
        email=email,
        rate=rate,
        hours=hours,
        allowance=allowance,
        period=period,
        row_index=row_index,
    )


def load_and_validate_csv(csv_path: Path) -> tuple[list[EmployeeRecord], list[str]]:
    """
    Load employee CSV and return valid records plus warning messages for skipped rows.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df = _normalize_columns(df)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV missing required columns: {', '.join(missing_cols)}")

    records: list[EmployeeRecord] = []
    warnings: list[str] = []

    for idx, row in df.iterrows():
        row_index = int(idx) + 2  # 1-based + header row
        try:
            records.append(_parse_row(row, row_index))
        except ValueError as exc:
            warnings.append(str(exc))

    if not records and warnings:
        raise ValueError("No valid employee rows in CSV. " + "; ".join(warnings[:5]))

    return records, warnings
