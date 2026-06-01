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


def calculate_pay_from_sheet(
    *,
    base_pay: float,
    regular_hours: float,
    ot_rate: float,
    ot_hours: float,
    incentive: float,
    period_total: float | None = None,
) -> PayBreakdown:
    """Pay from spreadsheet columns: base × regular hours, OT rate × OT hours, incentive."""
    regular_amount = regular_hours * base_pay
    overtime_amount = ot_hours * ot_rate if ot_hours > 0 else 0.0
    allowance = incentive
    net_pay = regular_amount + overtime_amount + allowance

    if period_total is not None and period_total > 0:
        net_pay = period_total

    return PayBreakdown(
        regular_units=regular_hours,
        regular_rate=base_pay,
        regular_amount=regular_amount,
        overtime_units=ot_hours,
        overtime_rate=ot_rate if ot_hours > 0 else 0.0,
        overtime_amount=overtime_amount,
        allowance=allowance,
        net_pay=net_pay,
    )


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
