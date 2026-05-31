import base64
import logging
from abc import ABC, abstractmethod
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from nlm_autopay.config import Settings
from nlm_autopay.models import EmployeeRecord, PayCalculation

logger = logging.getLogger(__name__)


class EmailSender(ABC):
    @abstractmethod
    def send_payslip(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_path: Path,
    ) -> None:
        """Send payslip PDF to employee. Raises on failure."""


def _personalized_body(employee: EmployeeRecord, calculation: PayCalculation) -> str:
    return (
        f"Dear {employee.name},\n\n"
        f"Please find attached your payslip for pay period {employee.period}.\n\n"
        f"Summary:\n"
        f"  Gross Pay: ${calculation.gross_pay:,.2f}\n"
        f"  Allowance: ${calculation.allowance:,.2f}\n"
        f"  Net Pay:   ${calculation.net_pay:,.2f}\n\n"
        f"If you have questions, contact your payroll administrator.\n\n"
        f"Regards,\nNLM Autopay"
    )


class ConsoleEmailSender(EmailSender):
    """Log email actions without sending (development / dry-run)."""

    def send_payslip(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_path: Path,
    ) -> None:
        logger.info(
            "[DRY-RUN] Would email %s <%s> payslip %s (net=%s)",
            employee.name,
            employee.email,
            pdf_path.name,
            calculation.net_pay,
        )


class SendGridEmailSender(EmailSender):
    def __init__(self, api_key: str, from_email: str) -> None:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Attachment,
            Disposition,
            FileContent,
            FileName,
            FileType,
            Mail,
        )

        self._client = SendGridAPIClient(api_key)
        self._from_email = from_email
        self._Mail = Mail
        self._Attachment = Attachment
        self._FileContent = FileContent
        self._FileName = FileName
        self._FileType = FileType
        self._Disposition = Disposition

    def send_payslip(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_path: Path,
    ) -> None:
        body = _personalized_body(employee, calculation)
        message = self._Mail(
            from_email=self._from_email,
            to_emails=employee.email,
            subject=f"Payslip — {employee.period}",
            plain_text_content=body,
        )
        encoded = base64.b64encode(pdf_path.read_bytes()).decode()
        attachment = self._Attachment()
        attachment.file_content = self._FileContent(encoded)
        attachment.file_type = self._FileType("application/pdf")
        attachment.file_name = self._FileName(pdf_path.name)
        attachment.disposition = self._Disposition("attachment")
        message.attachment = attachment

        response = self._client.send(message)
        if response.status_code >= 400:
            raise RuntimeError(
                f"SendGrid failed for {employee.email}: HTTP {response.status_code}"
            )


class OutlookEmailSender(EmailSender):
    """Send via Microsoft Graph API (OAuth2 client credentials)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        from_email: str,
    ) -> None:
        import msal
        import requests

        self._requests = requests
        self._from_email = from_email
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Outlook auth failed: {result.get('error_description', result)}"
            )
        self._token = result["access_token"]

    def send_payslip(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_path: Path,
    ) -> None:
        body = _personalized_body(employee, calculation)
        pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode()
        payload = {
            "message": {
                "subject": f"Payslip — {employee.period}",
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": employee.email}}],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": pdf_path.name,
                        "contentType": "application/pdf",
                        "contentBytes": pdf_b64,
                    }
                ],
            },
            "saveToSentItems": True,
        }
        url = f"https://graph.microsoft.com/v1.0/users/{self._from_email}/sendMail"
        resp = self._requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Outlook send failed for {employee.email}: {resp.status_code} {resp.text}"
            )


class GmailEmailSender(EmailSender):
    """Send via Gmail API with OAuth2 user credentials."""

    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        self._SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), self._SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials not found: {credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), self._SCOPES
                )
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())
        self._service = build("gmail", "v1", credentials=creds)

    def send_payslip(
        self,
        employee: EmployeeRecord,
        calculation: PayCalculation,
        pdf_path: Path,
    ) -> None:
        import googleapiclient

        body = _personalized_body(employee, calculation)
        message = MIMEMultipart()
        message["to"] = employee.email
        message["subject"] = f"Payslip — {employee.period}"
        message.attach(MIMEText(body, "plain"))

        with pdf_path.open("rb") as fh:
            part = MIMEApplication(fh.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=pdf_path.name)
        message.attach(part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            self._service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
        except googleapiclient.errors.HttpError as exc:
            raise RuntimeError(f"Gmail send failed for {employee.email}: {exc}") from exc


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.dry_run_email or settings.email_provider == "console":
        return ConsoleEmailSender()

    provider = settings.email_provider
    if provider == "sendgrid":
        if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
            raise ValueError(
                "SendGrid requires SENDGRID_API_KEY and SENDGRID_FROM_EMAIL"
            )
        return SendGridEmailSender(
            settings.sendgrid_api_key, settings.sendgrid_from_email
        )
    if provider == "outlook":
        if not all(
            [
                settings.outlook_client_id,
                settings.outlook_client_secret,
                settings.outlook_tenant_id,
                settings.outlook_from_email,
            ]
        ):
            raise ValueError(
                "Outlook requires OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, "
                "OUTLOOK_TENANT_ID, and OUTLOOK_FROM_EMAIL"
            )
        return OutlookEmailSender(
            settings.outlook_client_id,
            settings.outlook_client_secret,
            settings.outlook_tenant_id,
            settings.outlook_from_email,
        )
    if provider == "gmail":
        return GmailEmailSender(
            settings.gmail_credentials_path, settings.gmail_token_path
        )

    raise ValueError(
        f"Unknown email provider: {provider!r}. "
        "Use console, sendgrid, outlook, or gmail."
    )
