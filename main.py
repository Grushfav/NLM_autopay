#!/usr/bin/env python3
"""NLM_autopay — payroll automation CLI."""

import argparse
import logging
import sys
from pathlib import Path

from nlm_autopay.config import Settings
from nlm_autopay.service import PayrollService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NLM_autopay: CSV payroll, PDF payslips, email dispatch, audit logging.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("employees.csv"),
        help="Path to employee CSV (default: employees.csv)",
    )
    parser.add_argument(
        "--mode",
        choices=("batch", "single"),
        default="batch",
        help="Process all employees or a single employee (default: batch)",
    )
    parser.add_argument(
        "--employee",
        type=str,
        default="",
        help="Employee name or email (required for --mode single)",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate PDFs only; do not send email",
    )
    parser.add_argument(
        "--dry-run-email",
        action="store_true",
        help="Log email actions without sending (overrides provider to console)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if args.mode == "single" and not args.employee.strip():
        parser.error("--employee is required when --mode single")

    settings = Settings.from_env()
    if args.dry_run_email:
        settings.dry_run_email = True
        settings.email_provider = "console"

    service = PayrollService(settings=settings)

    try:
        employees, warnings = service.load_employees(args.csv)
    except (FileNotFoundError, ValueError) as exc:
        logging.error("%s", exc)
        return 1

    for warning in warnings:
        logging.warning("Skipped row: %s", warning)

    if args.mode == "single":
        match = service.find_employee(employees, args.employee)
        if match is None:
            logging.error("Employee not found: %s", args.employee)
            return 1
        targets = [match]
    else:
        targets = employees

    if not targets:
        logging.error("No employees to process")
        return 1

    results = service.process_batch(targets, send_email=not args.no_email)

    sent = sum(1 for r in results if r.status == "sent")
    failed = sum(1 for r in results if r.status == "email_failed")
    pdf_only = sum(1 for r in results if r.status == "pdf_generated")

    print(f"\nProcessed {len(results)} employee(s).")
    print(f"  Sent: {sent}  |  PDF only: {pdf_only}  |  Email failed: {failed}")
    for result in results:
        calc = result.calculation
        print(
            f"  - {result.employee.name}: gross={calc.gross_pay} net={calc.net_pay} "
            f"pdf={result.pdf_path} status={result.status}"
        )
        if result.error:
            print(f"      error: {result.error}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
