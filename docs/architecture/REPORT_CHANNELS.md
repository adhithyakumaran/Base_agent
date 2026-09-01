# Azure / OCI notification targets (test — replace for production)

## Test destinations (current demo)

| Channel | Value |
|---|---|
| Email | `adhithyakumaran2005@gmail.com` |
| WhatsApp | `+91 9965985951` (`+919965985951`) |
| Teams | Set `TEAMS_WEBHOOK_URL` in Azure variable group / OCI Vault when available |

## Azure Pipelines

- Cron schedule: **08:00 Asia/Kolkata** (`30 2 * * *` UTC) → `scripts/morning_patrol.py`
- Variable group `apex-qa-secrets` should hold: `SMTP_URL`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TEAMS_WEBHOOK_URL`, APEX UAT creds
- Without SMTP/Twilio secrets, deliveries are **queued + logged** (still demo-complete)

## OCI runtime env

```bash
REPORT_EMAIL=adhithyakumaran2005@gmail.com
REPORT_WHATSAPP=+919965985951
TEAMS_WEBHOOK_URL=   # optional until client webhook exists
SMTP_URL=            # optional for live email
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+1...
LLM_ENABLED=false
```

Console defaults these channels on first boot and migrates old placeholders.
