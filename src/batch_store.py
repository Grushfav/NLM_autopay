import json
import uuid
from pathlib import Path

from src.validator import PreparedEmployee, ValidationReport

BATCH_DIR = Path(__file__).resolve().parent.parent / "uploads" / "batches"
BATCH_DIR.mkdir(parents=True, exist_ok=True)


def save_batch(
    report: ValidationReport,
    *,
    pay_cycle: str,
    pay_date: str,
    csv_path: Path,
) -> str:
    batch_id = str(uuid.uuid4())
    batch_path = BATCH_DIR / f"{batch_id}.json"

    payload = {
        "batch_id": batch_id,
        "pay_cycle": pay_cycle,
        "pay_date": pay_date,
        "filename": report.filename,
        "csv_path": str(csv_path),
        "employees": [
            {
                "row_number": e.row_number,
                "name": e.name,
                "trn": e.trn,
                "nis": e.nis,
                "email": e.email,
                "rate": e.rate,
                "hours": e.hours,
                "allowance": e.allowance,
                "ytd": e.ytd,
                "ytd_override": e.ytd_source == "CSV override",
            }
            for e in report.prepared
        ],
    }

    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return batch_id


def load_batch(batch_id: str) -> dict:
    batch_path = BATCH_DIR / f"{batch_id}.json"
    if not batch_path.exists():
        raise FileNotFoundError("Payroll batch expired or not found. Please upload again.")
    with open(batch_path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_batch(batch_id: str) -> None:
    batch_path = BATCH_DIR / f"{batch_id}.json"
    batch_path.unlink(missing_ok=True)
