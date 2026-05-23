import logging
import re
from dataclasses import dataclass

import smtplib

from src.calculator import calculate_pay
from src.email_service import (
    EmailConfigError,
    _is_auth_failure,
    _auth_error,
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


def send_prepared_batch(batch: dict) -> list[SendResult]:
    pay_cycle = batch["pay_cycle"]
    pay_date = batch["pay_date"]
    tracker = YtdTracker()
    results: list[SendResult] = []

    verify_smtp_login()

    for emp in batch["employees"]:
        try:
            pay = calculate_pay(emp["rate"], emp["hours"], emp["allowance"])
            ytd = float(emp["ytd"])

            pdf_bytes = build_payslip_pdf(
                name=emp["name"],
                trn=emp["trn"],
                nis=emp["nis"],
                pay_cycle=pay_cycle,
                pay_date=pay_date,
                pay=pay,
                ytd=ytd,
            )

            send_payslip_email(
                to_email=emp["email"],
                employee_name=emp["name"],
                pay_cycle=pay_cycle,
                pay_date=pay_date,
                pdf_bytes=pdf_bytes,
                filename=_safe_filename(emp["name"]),
            )
            tracker.record(emp["trn"], emp["name"], ytd)

            results.append(
                SendResult(
                    name=emp["name"],
                    email=emp["email"],
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
            logger.exception("SMTP error for %s", emp["name"])
            results.append(
                SendResult(
                    name=emp["name"],
                    email=emp["email"],
                    net_pay=pay.net_pay,
                    ytd=ytd,
                    status="error",
                    message=str(exc),
                )
            )
        except Exception as exc:
            if _is_auth_failure(exc):
                raise _auth_error(exc) from exc
            logger.exception("Failed sending payslip for %s", emp["name"])
            results.append(
                SendResult(
                    name=emp["name"],
                    email=emp["email"],
                    net_pay=pay.net_pay,
                    ytd=ytd,
                    status="error",
                    message=str(exc),
                )
            )

    return results
