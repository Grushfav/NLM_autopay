# Payroll rules
NLM_OVERTIME_THRESHOLD=80
NLM_OVERTIME_MULTIPLIER=1.5
NLM_OUTPUT_DIR=output

# Transaction log: csv | sqlite
NLM_LOG_BACKEND=csv
NLM_LOG_PATH=payslip_log.csv

# Email: console | sendgrid | outlook | gmail
NLM_EMAIL_PROVIDER=console
NLM_DRY_RUN_EMAIL=false

# SendGrid
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=payroll@yourdomain.com

# Microsoft Outlook / Graph API
OUTLOOK_CLIENT_ID=
OUTLOOK_CLIENT_SECRET=
OUTLOOK_TENANT_ID=
OUTLOOK_FROM_EMAIL=payroll@yourdomain.com

# Gmail API (OAuth2)
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
