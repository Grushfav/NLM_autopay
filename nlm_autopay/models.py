from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EmployeeRecord:
    name: str
    email: str
    rate: Decimal
    hours: Decimal
    allowance: Decimal
    period: str
    row_index: int


@dataclass(frozen=True)
class PayCalculation:
    regular_hours: Decimal
    overtime_hours: Decimal
    regular_pay: Decimal
    overtime_pay: Decimal
    gross_pay: Decimal
    allowance: Decimal
    net_pay: Decimal


@dataclass(frozen=True)
class PayslipResult:
    employee: EmployeeRecord
    calculation: PayCalculation
    pdf_path: str
    email_sent: bool
    status: str
    error: str | None = None
