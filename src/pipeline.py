import logging
import re
from dataclasses import dataclass

import smtplib

from src.calculator import PayBreakdown
from src.email_service import (
    EmailConfigError,
    _auth_error,
    _is_auth_failure,
    send_bulk_payslips_email,
    send_payslip_email,
    verify_smtp_login,
)
from src.payslip_pdf import build_payslip_pdf
from src.ytd import YtdTracker

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    name: str
    email: str
    net_pay: float
    ytd: float
    status: str
    message: str


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")
    return f"payslip_{cleaned or 'employee'}.pdf"


def _pay_from_stored(data: dict) -> PayBreakdown:
    pay = data.get("pay")
    if pay:
        return PayBreakdown(**pay)
    return PayBreakdown(
        regular_units=float(data.get("hours", 0)),
        regular_rate=float(data.get("rate", 0)),
        regular_amount=0,
        overtime_units=0,
        overtime_rate=0,
        overtime_amount=0,
        allowance=float(data.get("allowance", 0)),
        net_pay=0,
    )


def send_prepared_batch(batch: dict) -> list[SendResult]:
    pay_cycle = batch["pay_cycle"]
    pay_date = batch["pay_date"]
    delivery_email = (batch.get("delivery_email") or "").strip()
    tracker = YtdTracker()
    results: list[SendResult] = []

    verify_smtp_login()

    prepared_items: list[tuple[str, str, bytes, dict]] = []

    for emp in batch["employees"]:
        pay = _pay_from_stored(emp)
        ytd = float(emp["ytd"])
        allowance_label = (
            "Incentive" if batch.get("format") == "payroll_sheet" else "Allowance"
        )
        pdf_bytes = build_payslip_pdf(
            name=emp["name"],
            trn=emp.get("trn", ""),
            nis=emp.get("nis", ""),
            site=emp.get("site", ""),
            pay_cycle=pay_cycle,
            pay_date=pay_date,
            pay=pay,
            ytd=ytd,
            allowance_label=allowance_label,
        )
        prepared_items.append(
            (
                emp["name"],
                _safe_filename(emp["name"]),
                pdf_bytes,
                {**emp, "pay": pay, "ytd": ytd},
            )
        )

    if delivery_email:
        try:
            send_bulk_payslips_email(
                to_email=delivery_email,
                pay_cycle=pay_cycle,
                pay_date=pay_date,
                attachments=[
                    (name, filename, pdf_bytes)
                    for name, filename, pdf_bytes, _ in prepared_items
                ],
            )
            for name, _, _, emp_data in prepared_items:
                pay = emp_data["pay"]
                ytd = emp_data["ytd"]
                tracker.record(emp_data["ytd_key"], name, ytd)
                results.append(
                    SendResult(
                        name=name,
                        email=delivery_email,
                        net_pay=pay.net_pay,
                        ytd=ytd,
                        status="sent",
                        message="Included in bulk email",
                    )
                )
        except EmailConfigError:
            raise
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPException) as exc:
            if _is_auth_failure(exc):
                raise _auth_error(exc) from exc
            raise
        except Exception as exc:
            if _is_auth_failure(exc):
                raise _auth_error(exc) from exc
            logger.exception("Bulk send failed")
            for name, _, _, emp_data in prepared_items:
                results.append(
                    SendResult(
                        name=name,
                        email=delivery_email,
                        net_pay=emp_data["pay"].net_pay,
                        ytd=emp_data["ytd"],
                        status="error",
                        message=str(exc),
                    )
                )
        return results

    for name, filename, pdf_bytes, emp_data in prepared_items:
        pay = emp_data["pay"]
        ytd = emp_data["ytd"]
        to_email = (emp_data.get("email") or "").strip()
        if not to_email:
            results.append(
                SendResult(
                    name=name,
                    email="",
                    net_pay=pay.net_pay,
                    ytd=ytd,
                    status="error",
                    message="No email on row; use delivery email option",
                )
            )
            continue
        try:
            send_payslip_email(
                to_email=to_email,
                employee_name=name,
                pay_cycle=pay_cycle,
                pay_date=pay_date,
                pdf_bytes=pdf_bytes,
                filename=filename,
            )
            tracker.record(emp_data["ytd_key"], name, ytd)
            results.append(
                SendResult(
                    name=name,
                    email=to_email,
                    net_pay=pay.net_pay,
                    ytd=ytd,
                    status="sent",
                    message="OK",
                )
            )
        except EmailConfigError:
            raise
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPException) as exc:
            if _is_auth_failure(exc):
                raise _auth_error(exc) from exc
            logger.exception("SMTP error for %s", name)
            results.append(
                SendResult(
                    name=name,
                    email=to_email,
                    net_pay=pay.net_pay,
                    ytd=ytd,
                    status="error",
                    message=str(exc),
                )
            )
        except Exception as exc:
            if _is_auth_failure(exc):
                raise _auth_error(exc) from exc
            logger.exception("Failed sending payslip for %s", name)
            results.append(
                SendResult(
                    name=name,
                    email=to_email,
                    net_pay=pay.net_pay,
                    ytd=ytd,
                    status="error",
                    message=str(exc),
                )
            )

    return results
