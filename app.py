import logging
import os
import uuid
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from src.batch_store import delete_batch, load_batch, save_batch
from src.email_service import EmailConfigError, verify_smtp_login
from src.pipeline import send_prepared_batch
from src.validator import prepared_to_display, validate_and_prepare

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-change-me-in-production")

UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _default_pay_cycle() -> tuple[str, str]:
    today = date.today()
    if today.day >= 16:
        start = date(today.year, today.month, 16)
        if today.month == 12:
            end = date(today.year + 1, 1, 15)
        else:
            end = date(today.year, today.month + 1, 15)
    else:
        if today.month == 1:
            start = date(today.year - 1, 12, 16)
        else:
            start = date(today.year, today.month - 1, 16)
        end = date(today.year, today.month, 15)
    return start.strftime("%B %d, %Y"), end.strftime("%B %d, %Y")


def _form_defaults() -> dict:
    cycle_start, cycle_end = _default_pay_cycle()
    return {
        "pay_cycle_start": cycle_start,
        "pay_cycle_end": cycle_end,
        "pay_date": date.today().strftime("%B %d, %Y"),
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        if request.args.get("test_gmail"):
            try:
                user = verify_smtp_login()
                flash(f"Gmail login OK for {user}. You can send payslips.", "success")
            except EmailConfigError as exc:
                flash(str(exc), "error")
        return render_template("index.html", **_form_defaults())
    return _prepare_payroll()


@app.route("/prepare", methods=["POST"])
def prepare():
    return _prepare_payroll()


def _prepare_payroll():
    defaults = _form_defaults()
    pay_cycle_start = request.form.get("pay_cycle_start", "").strip()
    pay_cycle_end = request.form.get("pay_cycle_end", "").strip()
    pay_date = request.form.get("pay_date", "").strip()
    pay_cycle = f"{pay_cycle_start} - {pay_cycle_end}"

    upload = request.files.get("csv_file")
    if not upload or not upload.filename:
        flash("Please upload a CSV file.", "error")
        return render_template("index.html", **defaults)

    if not upload.filename.lower().endswith(".csv"):
        flash("File must be a .csv file.", "error")
        return render_template("index.html", **defaults)

    batch_id = str(uuid.uuid4())
    csv_path = UPLOAD_DIR / f"{batch_id}.csv"
    upload.save(csv_path)

    try:
        report = validate_and_prepare(str(csv_path), upload.filename)
    except Exception as exc:
        csv_path.unlink(missing_ok=True)
        logger.exception("Validation failed")
        flash(f"Could not read CSV: {exc}", "error")
        return render_template("index.html", **defaults)

    if report.missing_columns:
        csv_path.unlink(missing_ok=True)
        flash(
            f"CSV is missing required columns: {', '.join(report.missing_columns)}",
            "error",
        )
        return render_template("index.html", **defaults)

    if not report.prepared:
        csv_path.unlink(missing_ok=True)
        flash("No valid employee rows found. Fix errors below and re-upload.", "error")
        return render_template(
            "preview.html",
            report=report,
            prepared=[],
            batch_id=None,
            pay_cycle=pay_cycle,
            pay_date=pay_date,
            pay_cycle_start=pay_cycle_start,
            pay_cycle_end=pay_cycle_end,
            total_net=0,
        )

    stored_batch_id = save_batch(
        report,
        pay_cycle=pay_cycle,
        pay_date=pay_date,
        csv_path=csv_path,
    )

    prepared = [prepared_to_display(e) for e in report.prepared]
    total_net = sum(p["net_pay"] for p in prepared)

    if report.errors:
        flash(
            f"Validated {report.valid_count} of {report.total_rows} row(s). "
            f"{report.error_count} row(s) need fixes before sending.",
            "warning",
        )
    else:
        flash(f"All {report.valid_count} row(s) validated. Review and confirm to send.", "success")

    return render_template(
        "preview.html",
        report=report,
        prepared=prepared,
        batch_id=stored_batch_id,
        pay_cycle=pay_cycle,
        pay_date=pay_date,
        pay_cycle_start=pay_cycle_start,
        pay_cycle_end=pay_cycle_end,
        total_net=total_net,
    )


@app.route("/send", methods=["POST"])
def send():
    batch_id = request.form.get("batch_id", "").strip()
    if not batch_id:
        flash("Session expired. Please upload the CSV again.", "error")
        return redirect(url_for("index"))

    try:
        batch = load_batch(batch_id)
        csv_path = batch.get("csv_path")
        results = send_prepared_batch(batch)
    except FileNotFoundError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))
    except EmailConfigError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))
    except Exception as exc:
        logger.exception("Send failed")
        flash(f"Send failed: {exc}", "error")
        return redirect(url_for("index"))

    if not results:
        flash("No payslips were processed.", "error")
        return redirect(url_for("index"))

    delete_batch(batch_id)
    if csv_path:
        Path(csv_path).unlink(missing_ok=True)

    sent = sum(1 for r in results if r.status == "sent")
    errors = sum(1 for r in results if r.status == "error")

    if errors:
        flash(f"Sent {sent} payslip(s). {errors} failed — see results.", "warning")
    else:
        flash(f"Successfully emailed {sent} payslip(s).", "success")

    return render_template("results.html", results=results, pay_cycle=batch["pay_cycle"], pay_date=batch["pay_date"])


@app.route("/test-email")
def test_email():
    return redirect("/?test_gmail=1")


@app.route("/cancel")
def cancel():
    batch_id = request.args.get("batch_id", "")
    if batch_id:
        delete_batch(batch_id)
        batch_file = UPLOAD_DIR / f"{batch_id}.csv"
        batch_file.unlink(missing_ok=True)
    flash("Upload cancelled.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"\n  NLM Payslip UI: http://127.0.0.1:{port}\n")
    app.run(debug=True, host="127.0.0.1", port=port, use_reloader=False)
