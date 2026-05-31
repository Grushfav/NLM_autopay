"""Start the NLM Kitchen payslip web UI."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from app import app  # noqa: E402

APP_BUILD = "2026-05-22"

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"\n  NLM Payslip UI (build {APP_BUILD}): http://127.0.0.1:{port}\n")
    app.run(debug=True, host="127.0.0.1", port=port, use_reloader=False)
