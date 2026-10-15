"""
Outbound SMS / OTP providers: MSG91, Telnyx, GTX.
"""

import requests

from cred import (
    MSG91_AUTH_KEY, MSG91_SENDER_ID, MSG91_TEMPLATE_ID,
    TELNYX_API_KEY, TELNYX_FROM_NUMBER,
    GTX_USER, GTX_PASS, GTX_REQUEST_URL, GTX_VERIFY_URL,
)


def send_msg91_sms(to_number, message):
    if not MSG91_AUTH_KEY or not MSG91_TEMPLATE_ID:
        return {"error": "MSG91 not configured"}
    url = "https://control.msg91.com/api/v5/flow/"
    payload = {
        "template_id": MSG91_TEMPLATE_ID,
        "sender": MSG91_SENDER_ID,
        "short_url": "0",
        "recipients": [{"mobiles": to_number.lstrip("+"), "var1": message}],
    }
    headers = {"authkey": MSG91_AUTH_KEY, "Content-Type": "application/json"}
    try:
        return requests.post(url, json=payload, headers=headers, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}


def send_telnyx_sms(to_number, message):
    if not TELNYX_API_KEY:
        return {"error": "Telnyx not configured"}
    url = "https://api.telnyx.com/v2/messages"
    headers = {
        "Authorization": f"Bearer {TELNYX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"from": TELNYX_FROM_NUMBER, "to": to_number, "text": message}
    try:
        return requests.post(url, json=payload, headers=headers, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}


def gtx_request_otp(phone, text_template="Your verification code is: $PIN$"):
    if not GTX_USER or not GTX_PASS:
        return {"error": "GTX not configured"}
    params = {"user": GTX_USER, "pass": GTX_PASS, "from": "AcmeCorp",
              "to": phone, "text": text_template}
    try:
        return requests.get(GTX_REQUEST_URL, params=params, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}


def gtx_verify_otp(request_id, user_pin):
    params = {"user": GTX_USER, "pass": GTX_PASS, "id": request_id, "pin": user_pin}
    try:
        return requests.get(GTX_VERIFY_URL, params=params, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}