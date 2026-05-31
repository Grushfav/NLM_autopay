# NLM_autopay

Modular payroll automation: CSV intake, overtime calculation, PDF payslips, email delivery, and append-only transaction logging.

## Architecture

```
CSV Upload          Payroll Logic         PDF Output
(input/)     -->    (business/)     -->   (output/)
                           |
                           v
                    Email (integration/)
                           |
                           v
                    Transaction Log (persistence/)
```


| Layer         | Module                                       | Responsibility                    |
| ------------- | -------------------------------------------- | --------------------------------- |
| Input         | `nlm_autopay/input/csv_parser.py`            | Parse & validate employee CSV     |
| Business      | `nlm_autopay/business/payroll.py`            | Gross/net with overtime rules     |
| Output        | `nlm_autopay/output/payslip.py`              | PDF payslip generation            |
| Integration   | `nlm_autopay/integration/email_sender.py`    | SendGrid, Outlook, Gmail, console |
| Persistence   | `nlm_autopay/persistence/transaction_log.py` | Append-only CSV or SQLite log     |
| Orchestration | `nlm_autopay/service.py`, `main.py`          | End-to-end workflow               |


## Payroll rules

- **Regular pay**: `Rate × min(Hours, threshold)` (default threshold: 80)
- **Overtime pay**: `(Hours − threshold) × Rate × multiplier` when hours exceed threshold (default multiplier: 1.5)
- **Gross pay**: regular + overtime
- **Net pay**: gross + allowance

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # optional: configure email & paths
```

## CSV format

Required columns (header row):


| Column    | Description                       |
| --------- | --------------------------------- |
| Name      | Employee full name                |
| Email     | Valid email address               |
| Rate      | Hourly rate (numeric)             |
| Hours     | Hours worked (numeric)            |
| Allowance | Fixed allowance (numeric)         |
| Period    | Pay period label (e.g. `2026-04`) |


Incomplete or invalid rows are skipped with warnings; processing continues for valid rows.

## Usage

**Batch — all employees, PDF only (no email):**

```bash
python main.py --csv employees.csv --no-email
```

**Batch — with email (configure provider in `.env`):**

```bash
python main.py --csv employees.csv
```

**Single employee (by name or email):**

```bash
python main.py --csv employees.csv --mode single --employee "Alice Johnson"
```

**Dry-run email (log only, no send):**

```bash
python main.py --csv employees.csv --dry-run-email
```

**Verbose logging:**

```bash
python main.py --csv employees.csv -v
```

## Configuration

Environment variables (see `.env.example`):


| Variable                  | Default           | Description                               |
| ------------------------- | ----------------- | ----------------------------------------- |
| `NLM_OVERTIME_THRESHOLD`  | `80`              | Hours before overtime applies             |
| `NLM_OVERTIME_MULTIPLIER` | `1.5`             | Overtime rate multiplier                  |
| `NLM_OUTPUT_DIR`          | `output`          | PDF output directory                      |
| `NLM_LOGO_PATH`           | `assets/nlm_logo.png` | Company logo on payslip PDFs (omit file to skip) |
| `NLM_LOG_BACKEND`         | `csv`             | `csv` or `sqlite`                         |
| `NLM_LOG_PATH`            | `payslip_log.csv` | Log file path                             |
| `NLM_EMAIL_PROVIDER`      | `console`         | `console`, `sendgrid`, `outlook`, `gmail` |


### Email providers

- **console** — Development default; logs intended sends without network calls.
- **sendgrid** — Set `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL`.
- **outlook** — Microsoft Graph with `OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET`, `OUTLOOK_TENANT_ID`, `OUTLOOK_FROM_EMAIL`.
- **gmail** — OAuth2 via `credentials.json` from Google Cloud Console; token saved to `token.json` on first run.

## Transaction log

Each run appends one row per processed employee:

`timestamp`, `name`, `email`, `period`, `gross_pay`, `net_pay`, `pdf_filename`, `status`

Statuses: `pdf_generated`, `sent`, `email_failed`.

Logs are append-only (no updates/deletes) for audit integrity.

## Security notes

- Do not commit `.env`, `credentials.json`, or `token.json`.
- Use OAuth2 / API keys via environment variables, not hard-coded secrets.
- Employee CSV may contain PII; restrict file permissions and secure log storage.

## Extensibility

The layered design supports future modules without changing the CLI contract:

- Tax deductions: extend `PayrollCalculator` and payslip template
- Digital signatures: post-process PDFs in `output/`
- Cloud storage: new integration adapter alongside email senders

## License

Internal use — NLM Autopay.