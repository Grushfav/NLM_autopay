# NLM Kitchen – Payslip Automation

Upload a CSV of employee hours; the system calculates regular pay, overtime, net pay, and year-to-date totals, generates PDF payslips, and emails them via Gmail.

## Pay rules

| Line | Calculation |
|------|-------------|
| Regular hours | `min(Hours, 80)` × Rate |
| Overtime | `(Hours − 80) × Rate × 1.5` when Hours > 80 |
| Net pay | Regular + Overtime + Allowance |

## CSV format

Required columns: `Name`, `TRN`, `NIS`, `Rate`, `Hours`, `Allowance`, `Email`

Optional: `YTD` — if set, that value is printed on the payslip instead of (stored YTD + net pay).

Invalid rows are skipped and logged; valid rows still process.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your Gmail address and an **App Password** (not your normal Gmail password):

1. Turn on [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification) for the Gmail account.
2. Create an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (choose "Mail" / "Other").
3. Copy the 16-character password (no spaces) into `.env`:

```
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
EMAIL_FROM=you@gmail.com
```

4. Restart the app after changing `.env`.

Place your company logo at `static/logo.png` (optional; text fallback is used otherwise).

## Run the web UI

```bash
.venv\Scripts\activate
python run.py
```

Open **http://127.0.0.1:5050**

1. **Upload** — CSV is validated row by row.
2. **Review** — See regular pay, overtime, net pay, YTD, and any row errors.
3. **Confirm & send** — Emails PDF payslips and updates YTD history.

> Port 5000 is often used by other tools on Windows. This app defaults to **5050** (`PORT` in `.env` to change).

Use **Preview only** to validate calculations without sending email or updating YTD history.

## YTD tracking

After each successful email, net pay is added to `data/ytd_history.json` keyed by TRN. Provide `YTD` in the CSV to override the displayed value (e.g. opening balance).

## Sample data

See `samples/employees_sample.csv` (includes Barbara Grossett example: 97 hours @ $400 → net $45,200).
