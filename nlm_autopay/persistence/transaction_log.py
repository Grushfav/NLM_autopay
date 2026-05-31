import csv
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from nlm_autopay.config import Settings
from nlm_autopay.models import EmployeeRecord, PayCalculation

LOG_FIELDS = (
    "timestamp",
    "name",
    "email",
    "period",
    "gross_pay",
    "net_pay",
    "pdf_filename",
    "status",
)


class TransactionLogger(ABC):
    """Append-only transaction log for audit integrity."""

    @abstractmethod
    def append(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_filename: str,
        status: str,
    ) -> None:
        pass


class CsvTransactionLogger(TransactionLogger):
    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._log_path.exists():
            with self._log_path.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=LOG_FIELDS).writeheader()

    def append(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_filename: str,
        status: str,
    ) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": employee.name,
            "email": employee.email,
            "period": employee.period,
            "gross_pay": str(calculation.gross_pay),
            "net_pay": str(calculation.net_pay),
            "pdf_filename": pdf_filename,
            "status": status,
        }
        with self._log_path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=LOG_FIELDS).writerow(row)


class SqliteTransactionLogger(TransactionLogger):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payslip_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    period TEXT NOT NULL,
                    gross_pay TEXT NOT NULL,
                    net_pay TEXT NOT NULL,
                    pdf_filename TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_filename: str,
        status: str,
    ) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO payslip_log
                (timestamp, name, email, period, gross_pay, net_pay, pdf_filename, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    employee.name,
                    employee.email,
                    employee.period,
                    str(calculation.gross_pay),
                    str(calculation.net_pay),
                    pdf_filename,
                    status,
                ),
            )
            conn.commit()


def build_transaction_logger(settings: Settings) -> TransactionLogger:
    if settings.log_backend == "sqlite":
        path = settings.log_path
        if path.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
            path = path.with_suffix(".sqlite")
        return SqliteTransactionLogger(path)
    return CsvTransactionLogger(settings.log_path)
