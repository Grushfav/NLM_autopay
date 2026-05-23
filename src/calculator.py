from dataclasses import dataclass

REGULAR_HOUR_CAP = 80
OVERTIME_MULTIPLIER = 1.5


@dataclass
class PayBreakdown:
    regular_units: float
    regular_rate: float
    regular_amount: float
    overtime_units: float
    overtime_rate: float
    overtime_amount: float
    allowance: float
    net_pay: float


def calculate_pay(rate: float, hours: float, allowance: float) -> PayBreakdown:
    regular_units = min(hours, REGULAR_HOUR_CAP)
    overtime_units = max(0.0, hours - REGULAR_HOUR_CAP)
    overtime_rate = rate * OVERTIME_MULTIPLIER

    regular_amount = regular_units * rate
    overtime_amount = overtime_units * overtime_rate
    net_pay = regular_amount + overtime_amount + allowance

    return PayBreakdown(
        regular_units=regular_units,
        regular_rate=rate,
        regular_amount=regular_amount,
        overtime_units=overtime_units,
        overtime_rate=overtime_rate,
        overtime_amount=overtime_amount,
        allowance=allowance,
        net_pay=net_pay,
    )


def format_jmd(amount: float) -> str:
    return f"$ {amount:,.2f}"
