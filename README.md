<div align="center">

<img src="https://github.com/anon-dc/VoxRelay/blob/8e138dafd57bcc3ed0cf769a075105b09af9fc98/main/docs/voxrelay-banner.png" alt="VoxRelay" width="820">

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

<br><br>

<h1>VoxRelay</h1>

<h3>Telegram-controlled IVR & communications automation</h3>

<p>
Build, manage and monitor consent-based voice and messaging workflows
from a centralized Telegram interface.
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

**VoxRelay** is a Flask-based communications automation platform designed to connect Telegram-based operator workflows with programmable voice and messaging services.

It provides a centralized interface for:

* Outbound voice workflows
* IVR menus
* Call status monitoring
* DTMF event handling
* SMS delivery
* Template-based call scripts
* Operator approval workflows
* Campaign history
* Recording metadata
* Administrative controls
* Health monitoring

VoxRelay is designed for **authorized, consent-based communications**. Operators are responsible for complying with applicable telecommunications, privacy, recording-consent, anti-spam and data-protection requirements.

---

## Features

<table>
<tr>
<td width="50%" valign="top">

### Voice Automation

* Initiate outbound calls from Telegram
* Programmable IVR workflows
* TwiML-based call scripts
* DTMF menu handling
* Real-time call status notifications
* Answering Machine Detection support
* Recording status and metadata
* Configurable caller experience
* Call lifecycle tracking
* Provider failover support where configured
* Idempotency protection for duplicate call actions
* Call SID / provider reference tracking
* Configurable runtime retention and cleanup
* Telegram workflow back / cancel controls

</td>
<td width="50%" valign="top">

### Operator Controls

* Telegram-based control panel
* Start and stop workflows
* Approve or reject supported workflow actions
* Live call notifications
* Operator activity tracking
* User administration
* Role-based access
* Configurable defaults
* Health monitoring
* Provider configuration management
* Call and message reference tracking
* Configurable audit/retention controls

</td>
</tr>

<tr>
<td width="50%" valign="top">

### Messaging

* SMS workflow support
* Provider abstraction
* Message templates
* Placeholder substitution
* Delivery status tracking
* Campaign history
* Configurable sender information
* Provider-specific integrations

</td>
<td width="50%" valign="top">

### Administration

* Manage Telegram users
* Upload and manage call templates
* Configure company information
* Configure voice settings
* Configure recording notices
* Review recent campaigns
* Review call metadata
* Application health endpoint

</td>
</tr>
</table>

---

## Architecture

<div align="center">

<img src="https://raw.githubusercontent.com/anon-dc/voxrelay/main/docs/DC Community Storyboard Infographic.png" alt="VoxRelay Architecture" width="820">

</div>

### Core runtime capabilities

VoxRelay is designed around a small, provider-agnostic workflow layer. The application can coordinate operator actions, voice callbacks, messaging providers and persistent campaign metadata without requiring a separate database service for the default SQLite deployment.

Key runtime capabilities include:

* **Provider abstraction** — isolate provider-specific API calls behind a common interface.
* **Provider fallback** — where configured, attempt an alternate supported provider when the primary route cannot be used.
* **Idempotency protection** — prevent duplicate execution when the same operator action or webhook is delivered more than once.
* **Call reference tracking** — retain provider call/message identifiers needed to correlate status callbacks with an internal workflow.
* **Short-lived workflow state** — keep active Telegram/call state separate from long-term campaign history.
* **Automatic cleanup** — remove expired transient workflow data according to the configured retention policy.
* **Single-service deployment** — the default architecture can run from one Flask application with SQLite; Redis/PostgreSQL can be introduced when horizontal scaling requires shared state.
* **Template-driven execution** — keep voice prompts and supported workflow definitions outside the core provider integration code.

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
│  Telegram Bot                               │
│  Workflow Engine                            │
│  IVR / Voice Webhooks                       │
│  Messaging Providers                        │
│  Call State                                 │
│  Notifications                              │
│  Template Engine                            │
│  Administration                             │
│                                             │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────┐
│ Voice        │  │ Messaging    │
│ Provider     │  │ Provider     │
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

---

## Project Structure

```text
voxrelay/
│
├── app.py
├── cred.py
├── dbase.py
├── settings.ini
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── docs/
│   ├── banner.svg
│   └── architecture.svg
│
├── templates/
│   ├── IVR.xml
│   ├── MENU.xml
│   ├── VERIFY.xml
│   ├── CALLBACK.xml
│   ├── APPOINTMENT.xml
│   ├── DELIVERY.xml
│   ├── PAYMENT.xml
│   └── ...
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

### Module overview

| Module              | Purpose                                    |
| ------------------- | ------------------------------------------ |
| `app.py`            | Flask application entry point              |
| `dbase.py`          | SQLite database operations                 |
| `bot_core.py`       | Telegram bot initialization and messaging  |
| `flows.py`          | Telegram user and administrative workflows |
| `verify.py`         | Authorized verification workflow handling  |
| `security.py`       | Security-related workflow state            |
| `voice_webhooks.py` | Voice callbacks and IVR events             |
| `twiml_engine.py`   | Template loading and substitution          |
| `providers.py`      | External messaging/voice provider wrappers |
| `call_state.py`     | Per-call runtime state                     |
| `notify.py`         | Operator notifications                     |
| `telegram_entry.py` | Telegram webhook and health/debug routes   |

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

Create a local `cred.py` file.

```python
# Voice provider
account_sid = "YOUR_ACCOUNT_SID"
auth_token = "YOUR_AUTH_TOKEN"
twilionumber = "+10000000000"

# Telegram
API_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Public HTTPS endpoint
PUBLIC_URL = "https://voice.example.com"

# Telegram administrators
BOOTSTRAP_ADMINS = [
    123456789
]

# Optional messaging provider configuration
TELNYX_API_KEY = ""
TELNYX_FROM_NUMBER = ""

MSG91_AUTH_KEY = ""
MSG91_SENDER_ID = ""
MSG91_TEMPLATE_ID = ""

GTX_USER = ""
GTX_PASS = ""
GTX_REQUEST_URL = ""
GTX_VERIFY_URL = ""
```

**Never commit this file to Git.**

---

# Configuration

Application defaults can be defined through `settings.ini`.

```ini
[company]
name = Example Company
website = https://example.com
support_phone = +18005551212

[voice]
polly_voice = Polly.Joanna

[call]
record_notice = This call may be recorded for quality and compliance purposes.

[support]
contact = https://www.dcwurld.com
support_label = DCWURLD

[retention]
workflow_seconds = 1800
```

Additional provider-specific options can be kept in `cred.py`, environment variables, or another protected secrets mechanism. Do not place production secrets in `settings.ini` when the file is tracked by Git.

### Recommended configuration groups

| Group | Purpose |
| ----- | ------- |
| `company` | Public company/contact information |
| `voice` | Voice defaults and provider settings |
| `call` | Recording and caller-experience settings |
| `support` | Support destination and branding |
| `retention` | Expiration of temporary workflow state |

---

# Running VoxRelay

Start the application:

```bash
python app.py
```

The Flask application can then be exposed through a reverse proxy such as:

* Caddy
* nginx
* Cloudflare Tunnel

The public HTTPS endpoint must be reachable by the configured external providers.

### Cloudflare Tunnel

A Cloudflare Tunnel can be used when the application is intentionally kept on a private host and outbound tunnel connectivity is preferred over opening inbound ports. The tunnel should terminate at the local Flask/reverse-proxy service and the public hostname must use HTTPS.

### Reverse proxy responsibilities

The reverse proxy should handle:

* TLS certificates
* HTTP-to-HTTPS redirects
* Request size/rate controls where appropriate
* Access restrictions for administrative/debug routes
* Forwarded headers required by the application

Typical endpoints include:

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
Live Status
```

The exact workflow depends on the configured templates and provider integrations.

### Operator navigation

Supported workflows can expose explicit **Back**, **Cancel**, **Confirm**, and **Exit** actions so an operator can safely move through a multi-step workflow without restarting the entire session.

A typical state model is:

```text
Start
  │
  ▼
Destination
  │
  ▼
Communication Type
  │
  ▼
Template
  │
  ▼
Review
  ├── Back
  ├── Cancel
  └── Confirm
          │
          ▼
       Execute
          │
          ▼
      Live Status
          │
          ▼
        Cleanup
```

Transient Telegram workflow state should be treated as short-lived state rather than a permanent record. Configure retention and cleanup according to the deployment's operational and compliance requirements.

---

# IVR Templates

VoxRelay uses XML/TwiML-style templates for programmable voice workflows.

Example:

```xml
<Response>
    <Say voice="{{voice}}">
        Welcome to {{company}}.
    </Say>

    <Gather
        numDigits="1"
        action="/webhooks/voice/menu"
        method="POST"
    >
        <Say voice="{{voice}}">
            Press 1 to continue.
            Press 2 to speak with support.
            Press 9 to end this call.
        </Say>
    </Gather>
</Response>
```

Templates can use application variables such as:

| Variable            | Description               |
| ------------------- | ------------------------- |
| `{{company}}`       | Configured company name   |
| `{{voice}}`         | Configured voice          |
| `{{record_notice}}` | Recording disclosure      |
| `{{website}}`       | Company website           |
| `{{support_phone}}` | Support number            |
| `{{client_name}}`   | Authorized customer name  |
| `{{client_email}}`  | Authorized customer email |

Avoid placing passwords, payment-card data, authentication secrets or other unnecessary sensitive information into templates or application logs.

---

# DTMF & IVR Events

VoxRelay can process DTMF input from supported voice providers.

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
```

Events can be forwarded to the Telegram operator interface for monitoring.

### Call lifecycle

Where supported by the provider, VoxRelay can correlate events using the provider's call identifier:

```text
Call requested
    │
    ▼
Provider Call SID / Reference
    │
    ├── initiated
    ├── ringing
    ├── answered
    ├── completed
    └── failed / busy / no-answer
```

Provider identifiers should be treated as operational metadata and should not be used as substitutes for authentication secrets.

### Recording

If recording is enabled, configure an appropriate disclosure before recording begins and follow the laws and provider requirements applicable to the calling parties. Store only the recording metadata and media required for the authorized business purpose, with a defined retention period.

---

# Messaging

Provider integrations can be configured through the provider abstraction layer.

Supported integrations may include:

```text
Voice
├── Twilio
└── Other compatible provider adapters

Messaging
├── Telnyx
├── MSG91
└── GTX
```

The exact capabilities available through each provider depend on the adapter implementation and the provider account.

### Provider fallback

Where multiple provider adapters are configured, VoxRelay can use a primary/secondary provider strategy for supported operations:

```text
Workflow
   │
   ▼
Primary Provider
   │
   ├── success ─────────► Continue
   │
   └── eligible failure
             │
             ▼
      Secondary Provider
             │
             ▼
          Continue
```

Fallback should only be enabled for operations where the application can safely determine that retrying through another provider will not create a duplicate action.

The provider layer allows the application to maintain a consistent internal interface while provider-specific API calls remain isolated.

Example conceptual flow:

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

| Method | Endpoint                        | Description                     |
| ------ | ------------------------------- | ------------------------------- |
| `POST` | `/telegram`                     | Telegram webhook                |
| `POST` | `/webhooks/voice/play/<script>` | Serve voice template            |
| `POST` | `/webhooks/voice/gather`        | Generic DTMF handler            |
| `POST` | `/webhooks/voice/menu`          | IVR menu handler                |
| `POST` | `/webhooks/voice/status`        | Voice status callback           |
| `POST` | `/webhooks/voice/verify/*`      | Verification workflow           |
| `GET`  | `/health`                       | Application health              |
| `GET`  | `/debug/traffic`                | Development traffic information |
| `GET`  | `/debug/calls`                  | Development call state          |

> **Production warning:** Do not expose `/debug/*` publicly without authentication and access controls.

---

# Database

VoxRelay uses SQLite with WAL mode.

Typical application tables include:

| Table            | Purpose                        |
| ---------------- | ------------------------------ |
| `Users`          | Telegram users and roles       |
| `Scripts`        | Stored communication templates |
| `Campaigns`      | Communication history          |
| `UserDefaults`   | User-specific defaults         |
| `VerifySessions` | Verification workflow state    |
| `VerifyAudit`    | Verification audit events      |
| `PendingFlow`    | Active Telegram workflows      |
| `CallContext`    | Call-related runtime metadata  |

Database connections should remain isolated between application threads.

---

# Security

Security should be treated as a deployment requirement rather than an optional feature.

## Credentials

Never commit:

```text
cred.py
.env
UserDetails.db
*.sqlite
*.sqlite3
```

Use environment variables or a protected secrets manager for production credentials.

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

Do not unnecessarily collect, store, transmit or log:

* Passwords
* Full payment-card numbers
* CVV/security codes
* Social Security numbers
* Government identification numbers
* Authentication secrets
* Private API keys

Use purpose-specific identifiers and short-lived verification references whenever possible.

## Webhook replay and duplicate protection

Webhook endpoints should be designed to tolerate retries and duplicate deliveries. Use provider event IDs, call references, timestamps, or another appropriate idempotency key where available.

Do not assume that receiving the same webhook twice means a second business action should be performed.

## Temporary state and cleanup

Transient workflow state should have an explicit expiration policy. VoxRelay may use short-lived state for:

* Pending operator workflows
* Active call context
* Temporary verification references
* Provider callback correlation
* One-time workflow actions

Expired transient state should be cleaned up rather than retained indefinitely.

---

# Compliance & Responsible Use

VoxRelay is intended for **authorized communications and legitimate business workflows**.

Operators are responsible for:

* Obtaining appropriate consent before contacting recipients
* Following applicable telecommunications regulations
* Respecting do-not-call requirements
* Providing required recording disclosures
* Respecting SMS opt-out requirements
* Protecting customer information
* Maintaining appropriate access controls
* Using provider APIs according to their terms
* Obtaining authorization before automating communications

VoxRelay should **not** be used for impersonation, phishing, credential theft, unauthorized account verification, harassment, spam or fraudulent activity.

---

# Deployment

A recommended production architecture is:

```text
                 Internet
                    │
                    ▼
          ┌──────────────────┐
          │ Cloudflare / CDN  │
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

Install the application:

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

---

# Operational Notes

### Idempotency

Operator actions and provider callbacks can be retried. Any action that creates a call, message or campaign should use a suitable idempotency mechanism so a repeated request does not unintentionally create duplicate communications.

### Runtime cleanup

The application can distinguish temporary runtime state from persistent campaign/audit data. Configure a retention period appropriate to the deployment and remove expired state on a regular basis.

### Single-process deployment

The default `call_state.py` implementation is process-local. For a simple installation, run a single application worker unless the application has been updated to use shared runtime state.

---

# Scaling

The default call state implementation is process-local.

```text
call_state.py
      │
      ▼
In-memory state
```

For multiple application workers or multiple servers, migrate shared runtime state to a distributed backend such as Redis.

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
                    SQLite/
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

### DTMF events are missing

Verify:

* The `<Gather>` action URL
* HTTP method
* Provider webhook configuration
* DTMF configuration
* Application logs

### SQLite locking problems

Ensure the application uses the intended WAL/thread-safe database configuration and avoid multiple unrelated processes writing to the same SQLite database.

---

# Development

Clone the repository:

```bash
git clone https://github.com/anon-dc/voxrelay.git
cd voxrelay
```

Create the development environment:

```bash
python -m venv .venv
```

Activate it:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
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

Pin exact versions for production deployments after testing your environment.

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

* [ ] PostgreSQL support
* [ ] Redis call-state backend
* [ ] Role-based permissions
* [ ] Web administration dashboard
* [ ] Provider health dashboard
* [ ] Structured audit logging
* [ ] Webhook signature middleware
* [ ] Improved campaign analytics
* [ ] Background task queue
* [ ] Docker deployment
* [ ] Automated test suite
* [ ] Provider failover
* [ ] Multi-tenant configuration
* [ ] Improved observability
* [ ] OpenTelemetry integration

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
7. Do not introduce functionality designed to bypass consent, authentication or provider safeguards.

Open an issue for bugs, feature requests or architectural discussions.

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

<a href="https://www.dcwurld.com">[www.dcwurld.com](http://www.dcwurld.com)</a>

</div>
