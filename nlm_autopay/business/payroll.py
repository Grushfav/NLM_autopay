from decimal import Decimal

from nlm_autopay.config import Settings
from nlm_autopay.models import EmployeeRecord, PayCalculation


class PayrollCalculator:
    """Compute gross (with overtime) and net pay for an employee record."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or Settings.from_env()
        self._threshold = settings.overtime_threshold_hours
        self._multiplier = settings.overtime_multiplier

    def calculate(self, employee: EmployeeRecord) -> PayCalculation:
        hours = employee.hours
        rate = employee.rate
        threshold = self._threshold

        if hours <= threshold:
            regular_hours = hours
            overtime_hours = Decimal("0")
            regular_pay = rate * hours
            overtime_pay = Decimal("0")
        else:
            regular_hours = threshold
            overtime_hours = hours - threshold
            regular_pay = rate * threshold
            overtime_pay = overtime_hours * rate * self._multiplier

        gross_pay = regular_pay + overtime_pay
        net_pay = gross_pay + employee.allowance

        return PayCalculation(
            regular_hours=regular_hours,
            overtime_hours=overtime_hours,
            regular_pay=regular_pay,
            overtime_pay=overtime_pay,
            gross_pay=gross_pay,
            allowance=employee.allowance,
            net_pay=net_pay,
        )
