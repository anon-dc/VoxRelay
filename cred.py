import os

# ---------- Twilio (Voice) ----------
account_sid  = os.getenv("TWILIO_ACCOUNT_SID", "")
auth_token   = os.getenv("TWILIO_AUTH_TOKEN",  "")
twilionumber = os.getenv("TWILIO_NUMBER",      "")

# ---------- Telegram ----------
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ---------- Public URL ----------
PUBLIC_URL = os.getenv("PUBLIC_URL", "")

# ---------- Bootstrap Admins ----------
# BOOTSTRAP_ADMINS = [int(x) for x in os.getenv("BOOTSTRAP_ADMINS", "").split(",") if x.strip()]
BOOTSTRAP_ADMINS = [5853390109,7074173395]

# ---------- GTX OTP API (generate + verify; you cannot obtain the OTP plaintext) ----------
GTX_USER = os.getenv("GTX_USER", "")
GTX_PASS = os.getenv("GTX_PASS", "")
GTX_REQUEST_URL = "https://otp.gtx-messaging.net:443/smspin/request.json"
GTX_VERIFY_URL  = "https://otp.gtx-messaging.net:443/smspin/verify.json"

# ---------- MSG91 (notification SMS with content you fully control) ----------
MSG91_AUTH_KEY = os.getenv("MSG91_AUTH_KEY", "")
MSG91_SENDER_ID = os.getenv("MSG91_SENDER_ID", "MYAPP")
MSG91_TEMPLATE_ID = os.getenv("MSG91_TEMPLATE_ID", "")

# ---------- Telnyx (notification SMS with content you fully control) ----------
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "")
TELNYX_FROM_NUMBER = os.getenv("TELNYX_FROM_NUMBER", "")