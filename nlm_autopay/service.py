import logging
from pathlib import Path

from nlm_autopay.business.payroll import PayrollCalculator
from nlm_autopay.config import Settings
from nlm_autopay.input.csv_parser import load_and_validate_csv
from nlm_autopay.integration.email_sender import EmailSender, build_email_sender
from nlm_autopay.models import EmployeeRecord, PayslipResult
from nlm_autopay.output.payslip import PayslipGenerator
from nlm_autopay.persistence.transaction_log import TransactionLogger, build_transaction_logger

logger = logging.getLogger(__name__)


class PayrollService:
    """Orchestrates validation, calculation, PDF, email, and logging."""

    def __init__(
        self,
        settings: Settings | None = None,
        calculator: PayrollCalculator | None = None,
        pdf_generator: PayslipGenerator | None = None,
        email_sender: EmailSender | None = None,
        transaction_logger: TransactionLogger | None = None,
    ) -> None:
        self._settings = settings or Settings.from_env()
        self._calculator = calculator or PayrollCalculator(self._settings)
        self._pdf = pdf_generator or PayslipGenerator(self._settings)
        self._email = email_sender or build_email_sender(self._settings)
        self._log = transaction_logger or build_transaction_logger(self._settings)

    def load_employees(self, csv_path: Path) -> tuple[list[EmployeeRecord], list[str]]:
        return load_and_validate_csv(csv_path)

    def process_employee(
        self,
        employee: EmployeeRecord,
        *,
        send_email: bool = True,
    ) -> PayslipResult:
        calculation = self._calculator.calculate(employee)
        pdf_path = self._pdf.generate(employee, calculation)
        email_sent = False
        status = "pdf_generated"
        error: str | None = None

        if send_email:
            try:
                self._email.send_payslip(employee, calculation, pdf_path)
                email_sent = True
                status = "sent"
            except Exception as exc:
                status = "email_failed"
                error = str(exc)
                logger.error("Email failed for %s: %s", employee.email, exc)

        self._log.append(employee, calculation, pdf_path.name, status)

        return PayslipResult(
            employee=employee,
            calculation=calculation,
            pdf_path=str(pdf_path),
            email_sent=email_sent,
            status=status,
            error=error,
        )

    def process_batch(
        self,
        employees: list[EmployeeRecord],
        *,
        send_email: bool = True,
    ) -> list[PayslipResult]:
        return [
            self.process_employee(emp, send_email=send_email) for emp in employees
        ]

    def find_employee(
        self, employees: list[EmployeeRecord], identifier: str
    ) -> EmployeeRecord | None:
        key = identifier.strip().lower()
        for emp in employees:
            if emp.name.lower() == key or emp.email.lower() == key:
                return emp
        return None
