import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass
class Settings:
    overtime_threshold_hours: Decimal
    overtime_multiplier: Decimal
    output_dir: Path
    log_backend: str
    log_path: Path
    email_provider: str
    sendgrid_api_key: str
    sendgrid_from_email: str
    outlook_client_id: str
    outlook_client_secret: str
    outlook_tenant_id: str
    outlook_from_email: str
    gmail_credentials_path: Path
    gmail_token_path: Path
    dry_run_email: bool
    logo_path: Path | None

    @classmethod
    def _default_logo_path(cls) -> Path:
        return Path(__file__).resolve().parent.parent / "assets" / "nlm_logo.png"

    @classmethod
    def from_env(cls) -> "Settings":
        base = Path(os.getenv("NLM_OUTPUT_DIR", "output"))
        logo_env = os.getenv("NLM_LOGO_PATH", "").strip()
        logo_path = Path(logo_env) if logo_env else cls._default_logo_path()
        if not logo_path.is_file():
            logo_path = None
        return cls(
            overtime_threshold_hours=Decimal(
                os.getenv("NLM_OVERTIME_THRESHOLD", "80")
            ),
            overtime_multiplier=Decimal(os.getenv("NLM_OVERTIME_MULTIPLIER", "1.5")),
            output_dir=base,
            log_backend=os.getenv("NLM_LOG_BACKEND", "csv").lower(),
            log_path=Path(os.getenv("NLM_LOG_PATH", "payslip_log.csv")),
            email_provider=os.getenv("NLM_EMAIL_PROVIDER", "console").lower(),
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            sendgrid_from_email=os.getenv("SENDGRID_FROM_EMAIL", ""),
            outlook_client_id=os.getenv("OUTLOOK_CLIENT_ID", ""),
            outlook_client_secret=os.getenv("OUTLOOK_CLIENT_SECRET", ""),
            outlook_tenant_id=os.getenv("OUTLOOK_TENANT_ID", ""),
            outlook_from_email=os.getenv("OUTLOOK_FROM_EMAIL", ""),
            gmail_credentials_path=Path(
                os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
            ),
            gmail_token_path=Path(os.getenv("GMAIL_TOKEN_PATH", "token.json")),
            dry_run_email=os.getenv("NLM_DRY_RUN_EMAIL", "false").lower()
            in ("1", "true", "yes"),
            logo_path=logo_path,
        )
