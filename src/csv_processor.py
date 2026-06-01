"""Backward-compatible CSV loading — delegates to csv_formats / validator."""

from src.csv_formats import LEGACY_REQUIRED, load_dataframe, parse_legacy_row
from src.validator import validate_and_prepare

REQUIRED_COLUMNS = LEGACY_REQUIRED
OPTIONAL_COLUMNS = ["YTD"]

__all__ = [
    "REQUIRED_COLUMNS",
    "OPTIONAL_COLUMNS",
    "load_dataframe",
    "validate_and_prepare",
]


def load_employees(file_path: str):
    report = validate_and_prepare(file_path, file_path)
    if report.missing_columns:
        raise ValueError(f"CSV missing required columns: {', '.join(report.missing_columns)}")
    return report.prepared, report.errors
