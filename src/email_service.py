import os
import smtplib
from smtplib import SMTPAuthenticationError
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailConfigError(Exception):
    pass


GMAIL_SETUP_HELP = (
    "Gmail login failed. In .env set GMAIL_USER to your full @gmail.com address "
    "and GMAIL_APP_PASSWORD to a 16-character App Password (not your normal password). "
    "Create one at https://myaccount.google.com/apppasswords after enabling 2-Step Verification. "
    "Restart the app after saving .env."
)


def _normalize_password(raw: str) -> str:
    # App passwords are often copied as "abcd efgh ijkl mnop"
    return raw.strip().strip('"').strip("'").replace(" ", "")


def _is_auth_failure(exc: BaseException) -> bool:
    if isinstance(exc, SMTPAuthenticationError):
        return True
    code = getattr(exc, "smtp_code", None)
    if code == 535:
        return True
    text = str(exc).lower()
    return "535" in text or "badcredentials" in text or "username and password not accepted" in text


def _auth_error(exc: BaseException | None = None) -> EmailConfigError:
    err = EmailConfigError(GMAIL_SETUP_HELP)
    if exc is not None:
        err.__cause__ = exc
    return err


def _get_smtp_config() -> dict:
    user = os.getenv("GMAIL_USER", "").strip().strip('"')
    password = _normalize_password(os.getenv("GMAIL_APP_PASSWORD", ""))
    sender = os.getenv("EMAIL_FROM", user).strip().strip('"')

    if not user or not password:
        raise EmailConfigError(
            "Set GMAIL_USER and GMAIL_APP_PASSWORD in your .env file "
            "(use a Gmail App Password, not your regular password)."
        )

    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "sender": sender,
    }


def send_payslip_email(
    *,
    to_email: str,
    employee_name: str,
    pay_cycle: str,
    pay_date: str,
    pdf_bytes: bytes,
    filename: str,
) -> None:
    cfg = _get_smtp_config()

    msg = MIMEMultipart()
    msg["From"] = cfg["sender"]
    msg["To"] = to_email
    msg["Subject"] = f"NLM Kitchen Payslip – {pay_date}"

    body = (
        f"Dear {employee_name},\n\n"
        f"Please find attached your payslip for the pay cycle {pay_cycle}.\n"
        f"Pay date: {pay_date}\n\n"
        "Regards,\nNLM Kitchen"
    )
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["sender"], [to_email], msg.as_string())
    except Exception as exc:
        if _is_auth_failure(exc):
            raise _auth_error(exc) from exc
        raise


def send_bulk_payslips_email(
    *,
    to_email: str,
    pay_cycle: str,
    pay_date: str,
    attachments: list[tuple[str, str, bytes]],
) -> None:
    """Send all payslip PDFs in one email for manual distribution."""
    cfg = _get_smtp_config()
    if not to_email or "@" not in to_email:
        raise EmailConfigError("Delivery email address is invalid.")

    msg = MIMEMultipart()
    msg["From"] = cfg["sender"]
    msg["To"] = to_email
    msg["Subject"] = f"NLM Kitchen Payslips – {pay_cycle} ({len(attachments)} employees)"

    names = [name for name, _, _ in attachments]
    body = (
        f"Please find attached {len(attachments)} payslip(s) for pay cycle {pay_cycle}.\n"
        f"Pay date: {pay_date}\n\n"
        "Employees:\n"
        + "\n".join(f"  - {n}" for n in names)
        + "\n\n"
        "Forward each PDF to the employee as needed.\n\n"
        "Regards,\nNLM Kitchen"
    )
    msg.attach(MIMEText(body, "plain"))

    for employee_name, filename, pdf_bytes in attachments:
        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=filename,
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=60) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["sender"], [to_email], msg.as_string())
    except Exception as exc:
        if _is_auth_failure(exc):
            raise _auth_error(exc) from exc
        raise


def verify_smtp_login() -> str:
    """Raise EmailConfigError if Gmail credentials are missing or invalid."""
    cfg = _get_smtp_config()
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
    except Exception as exc:
        if _is_auth_failure(exc):
            raise _auth_error(exc) from exc
        raise EmailConfigError(f"Could not connect to Gmail SMTP: {exc}") from exc
    return cfg["user"]
