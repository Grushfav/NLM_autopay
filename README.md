# NLM Kitchen – Payslip Automation

Upload a CSV of employee hours; the system calculates regular pay, overtime, net pay, and year-to-date totals, generates PDF payslips, and emails them.

This repository includes:

- **Web UI** (`app.py`, `run.py`) — Flask upload → review → send workflow
- **CLI** (`main.py`, `nlm_autopay/`) — batch/single processing with multiple email providers

## Pay rules

| Line | Calculation |
|------|-------------|
| Regular hours | `min(Hours, 80)` × Rate |
| Overtime | `(Hours − 80) × Rate × 1.5` when Hours > 80 |
| Net pay | Regular + Overtime + Allowance |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

### Web UI (Gmail App Password)

Edit `.env` with your Gmail address and an **App Password** (not your normal Gmail password):

1. Turn on [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification).
2. Create an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Set `GMAIL_USER`, `GMAIL_APP_PASSWORD`, and `EMAIL_FROM` in `.env`.

Place your company logo at `static/logo.png` (optional; text fallback is used otherwise).

### CLI (optional providers)

The CLI reads additional variables: `NLM_EMAIL_PROVIDER` (`console`, `sendgrid`, `outlook`, `gmail`), overtime settings, `NLM_OUTPUT_DIR`, `NLM_LOGO_PATH` (default `assets/nlm_logo.png`), and provider-specific keys. See `.env` / modular package docs.

## Run the web UI

```bash
.venv\Scripts\activate
python run.py
```

Open **http://127.0.0.1:5050** (change with `PORT` in `.env`).

1. **Upload** — CSV is validated row by row.
2. **Review** — See regular pay, overtime, net pay, YTD, and any row errors.
3. **Confirm & send** — Emails PDF payslips and updates YTD history.

Use **Preview only** to validate calculations without sending email or updating YTD history.

## Run the CLI

**Batch — PDF only:**

```bash
python main.py --csv employees.csv --no-email
```

**Batch — with email:**

```bash
python main.py --csv employees.csv
```

**Single employee:**

```bash
python main.py --csv employees.csv --mode single --employee "Alice Johnson"
```

**Dry-run email:**

```bash
python main.py --csv employees.csv --dry-run-email
```

## CSV format

**Web UI** — required: `Name`, `TRN`, `NIS`, `Rate`, `Hours`, `Allowance`, `Email`. Optional `YTD` overrides displayed year-to-date.

**CLI** — required: `Name`, `Email`, `Rate`, `Hours`, `Allowance`, `Period`.

See `samples/employees_sample.csv` for web UI examples.

## YTD tracking (web UI)

After each successful email, net pay is added to `data/ytd_history.json` keyed by TRN.

## Architecture (CLI package)

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

## Security

- Do not commit `.env`, `credentials.json`, or `token.json`.
- Employee CSV may contain PII; restrict file permissions and secure log storage.
