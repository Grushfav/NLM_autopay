"""Test Gmail SMTP credentials from .env — run before sending payslips."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.email_service import EmailConfigError, verify_smtp_login


def main() -> int:
    try:
        user = verify_smtp_login()
        print(f"Gmail login OK for: {user}")
        print("You can send payslips from the web app.")
        return 0
    except EmailConfigError as exc:
        print("Gmail login FAILED:")
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
