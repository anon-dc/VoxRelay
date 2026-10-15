"""
Telegram flows: /start, User Mode (Call + SMS), Custom Script, Admin panel.
"""

import os
import xml.etree.ElementTree as ET
import configparser

from telebot import types
from twilio.rest import Client

from cred import account_sid, auth_token, twilionumber, PUBLIC_URL, BOOTSTRAP_ADMINS
import dbase as db
from modules import call_state as cs
from modules.bot_core import (
    bot, send, track_user_message, safe_answer, clean_previous, delete_previous,
    back_button, cancel_button, is_cancel, is_back,
)
from modules.notify import notify_caller  # noqa: F401
from modules.providers import send_msg91_sms, send_telnyx_sms
from modules.twiml_engine import all_available_scripts, TEMPLATES_DIR, PAGE_SIZE

twilio_client = Client(account_sid, auth_token)

HOLD_MAX_SECONDS = 600

# Which scripts use Answering Machine Detection.
AMD_SCRIPTS = {"OTP", "SECURITY", "VERIFY", "PASSCODE", "HIPAA", "BANK"}


# ============================================================
# /start
# ============================================================

def user_active(uid):
    return db.is_active(uid) or db.is_admin(uid)


def _send_start_greeting(uid, name, username):
    if uid in BOOTSTRAP_ADMINS and not db.is_admin(uid):
        db.upsert_user(uid, username, role="admin", days=3650)

    if not db.get_user(uid):
        _send_unauthorized_screen(uid, name, reason="new")
        return
    if not user_active(uid):
        _send_unauthorized_screen(uid, name, reason="expired")
        return

    db.clear_pending(uid)

    description = (
        "📞 *Automated Voice & SMS Bot*\n\n"
        "This bot lets you place automated calls and send notification SMS "
        "messages to a target number.\n\n"
        "• *Call Mode* - play a TwiML script and capture IVR responses\n"
        "• *SMS Mode* - compose and send a one-off SMS via Telnyx / MSG91\n"
        "• *Custom Script* - admin-only TwiML builder\n\n"
        "Everything is logged and auditable."
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("👤 User Mode", callback_data="startmode:user"))
    if db.is_admin(uid):
        kb.add(types.InlineKeyboardButton("🛠 Admin Mode", callback_data="startmode:admin"))

    send(uid, f"Hello {name} 👑", reply_markup=types.ReplyKeyboardRemove())
    send(uid, description, parse_mode="Markdown", reply_markup=kb)


def _send_unauthorized_screen(uid, name, reason="new"):
    plan = "❌"
    reason_text = {
        "new": "→ You do not have an active subscription. ←",
        "expired": "→ Your subscription has expired. ←",
    }.get(reason, "→ You do not have an active subscription. ←")

    support_label = db.get_support_label()
    contact_url = db.get_support_contact()
    purchase_url = db.get_purchase_url()
    usage_url = db.get_usage_url()

    text = (
        f"👋 Hello {name}!\n\n"
        f"Welcome to DC COMMUNITY! 🤖\n\n"
        f"{reason_text}\n\n"
        f"💰 Active Plan:  {plan}"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔑 Purchase Key", url=purchase_url))
    kb.add(types.InlineKeyboardButton("💬 Get Support", url=contact_url))
    kb.add(types.InlineKeyboardButton("📖 How to Use", url=usage_url))
    kb.add(types.InlineKeyboardButton("⬅ Back", callback_data="back:main_unauth"))

    send(uid, text, parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    send(uid, f"▫️ For Support: Contact Us ⤵️ {support_label}", reply_markup=kb)


def start_from_callback(call):
    uid = call.from_user.id
    name = call.from_user.first_name or call.from_user.username or "there"
    _send_start_greeting(uid, name, call.from_user.username)


@bot.callback_query_handler(func=lambda c: c.data == "back:main_unauth")
def cb_back_main_unauth(call):
    safe_answer(call)
    delete_previous(call)
    uid = call.from_user.id
    name = call.from_user.first_name or call.from_user.username or "there"
    _send_start_greeting(uid, name, call.from_user.username)


@bot.message_handler(commands=["start"])
def start(message):
    track_user_message(message)
    uid = message.from_user.id
    name = message.from_user.first_name or message.from_user.username or "there"
    _send_start_greeting(uid, name, message.from_user.username)


@bot.callback_query_handler(func=lambda c: c.data.startswith("startmode:"))
def cb_start_mode(call):
    uid = call.from_user.id
    mode = call.data.split(":", 1)[1]
    safe_answer(call)
    clean_previous(call)

    if mode == "user":
        if not user_active(uid):
            send(call.message.chat.id, "🚫 Not authorized.")
            return
        flow_prompt_number(call.message)
    elif mode == "admin":
        if not db.is_admin(uid):
            send(call.message.chat.id, "❌ Admin only.")
            return
        show_admin_menu(call.message)


# ============================================================
# USER MODE - step 1 / 2
# ============================================================

def flow_prompt_number(message):
    db.clear_pending(message.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=1).add(cancel_button())

    sent = send(
        message.chat.id,
        "📱 *Step 1 - Destination number*\n\n"
        "*Reply with the number:*\n"
        "(e.g. +14358762364)\n\n"
        "You *must* use the +!\n\n"
        "Send `back` at any step to go back.\n"
        "Send `cancel` to return to /start.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    bot.register_next_step_handler(sent, flow_validate_number)


def flow_validate_number(message):
    track_user_message(message)
    uid = message.from_user.id
    raw = (message.text or "").strip()

    if raw == "/start" or is_cancel(raw):
        return _cancel_flow(message.chat.id, uid)
    if is_back(raw):
        return _cancel_flow(message.chat.id, uid)

    if not raw.startswith("+") or not raw[1:].isdigit():
        kb = types.InlineKeyboardMarkup(row_width=1).add(cancel_button())
        sent = send(
            message.chat.id,
            "❌ Invalid number. Include the *+* and country code.\n\nTry again:",
            parse_mode="Markdown",
            reply_markup=kb,
        )
        bot.register_next_step_handler(sent, flow_validate_number)
        return

    db.set_pending_number(uid, raw)

    kb = types.InlineKeyboardMarkup(row_width=2).row(
        back_button("back:step1"), cancel_button())

    sent = send(
        message.chat.id,
        f"✅ Number saved: `{raw}`\n\n*Step 2 - Confirm*\n\nType *Ok* to continue.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    bot.register_next_step_handler(sent, flow_confirm_ok)


def flow_confirm_ok(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return _back_to_step1(message.chat.id, message.from_user.id)

    if raw.lower() != "ok":
        kb = types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step1"), cancel_button())
        sent = send(message.chat.id, "Type *Ok* to continue.",
                    parse_mode="Markdown", reply_markup=kb)
        bot.register_next_step_handler(sent, flow_confirm_ok)
        return
    flow_mode_picker(message)


# ============================================================
# Step 3 - mode
# ============================================================

def flow_mode_picker(message):
    name = message.from_user.first_name or "there"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📞 Call Mode", callback_data="mode:call"),
        types.InlineKeyboardButton("✉ SMS Mode", callback_data="mode:sms"),
        types.InlineKeyboardButton("✒ Custom Script", callback_data="mode:custom"),
    )
    kb.row(back_button("back:step2"), cancel_button())
    send(
        message.chat.id,
        f"*Step 3 - Mode*\n\nWhat mode do you want, {name} 👑",
        parse_mode="Markdown",
        reply_markup=kb,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("mode:"))
def cb_mode(call):
    uid = call.from_user.id
    if not user_active(uid):
        safe_answer(call, "Not authorized.")
        return
    mode = call.data.split(":", 1)[1]
    safe_answer(call)
    clean_previous(call)
    db.set_pending_mode(uid, mode)

    if mode == "call":
        sent = send(
            call.message.chat.id,
            "📞 *Call Mode*\n\n*Step 4 - Company identity*\n\nType *Ok* to continue.",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_ok_then_company)
    elif mode == "sms":
        sent = send(
            call.message.chat.id,
            "✉ *SMS Mode*\n\n*Step 4 - Company identity*\n\nType *Ok* to continue.",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_ok_then_company_sms)
    elif mode == "custom":
        if not db.is_admin(uid):
            send(call.message.chat.id, "❌ Custom Script is admin only.")
            return
        flow_custom_script_start(call.message)


# ============================================================
# CALL MODE - step 4 → 4c → 5 → 7
# ============================================================

def flow_ok_then_company(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_mode_picker(message)

    if raw.lower() != "ok":
        sent = send(
            message.chat.id, "Type *Ok* to continue.",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_ok_then_company)
        return

    default_company = db.get_company_name()
    if default_company:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton(f"✅ Use default: {default_company}",
                                       callback_data="company:default"),
            types.InlineKeyboardButton("✏ Enter a different company",
                                       callback_data="company:custom"),
        )
        kb.row(back_button("back:step3"), cancel_button())
        send(
            message.chat.id,
            f"*Step 4 - Company identity*\n\n"
            f"Company on file: *{default_company}*\n\n"
            f"Use it, or enter a temporary one for this call?",
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        sent = send(
            message.chat.id,
            "*Step 4 - Company identity*\n\n"
            "No default company configured.\n\n"
            "*Reply with the company name:*\n"
            "(e.g. Acme Financial / City Hospital / Metro Telecom)",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_save_company)


def flow_save_company(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_mode_picker(message)

    if not raw:
        sent = send(
            message.chat.id, "Please send a company name.",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_save_company)
        return
    db.set_pending_service(message.from_user.id, raw)
    flow_prompt_client_name(message)


@bot.callback_query_handler(func=lambda c: c.data in ("company:default", "company:custom"))
def cb_company(call):
    safe_answer(call)
    if call.data == "company:default":
        clean_previous(call)
        fake = call.message
        fake.from_user = call.from_user
        fake.text = ""
        flow_prompt_client_name(fake)
    elif call.data == "company:custom":
        delete_previous(call)
        sent = send(
            call.message.chat.id,
            "*Step 4 - Company identity*\n\n"
            "*Reply with the company name:*\n"
            "(e.g. Acme Financial / City Hospital / Metro Telecom)",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_save_company)


def flow_prompt_client_name(message):
    sent = send(
        message.chat.id,
        "*Step 4b - Client name*\n\n"
        "Send the *client's full name* (e.g. `John Smith`).\n"
        "This is used to personalize the call.\n\n"
        "Send `skip` to leave it blank, `back` to change company, "
        "or `cancel` to abort.",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step4"), cancel_button()
        ),
    )
    bot.register_next_step_handler(sent, flow_save_client_name)


def flow_save_client_name(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_ok_then_company(message)

    if raw.lower() in ("skip", "-", "none"):
        raw = ""
    db.set_pending_client_name(message.from_user.id, raw)
    flow_prompt_client_email(message)


def flow_prompt_client_email(message):
    sent = send(
        message.chat.id,
        "*Step 4c - Client email*\n\n"
        "Send the *client's email address* (e.g. `jsmith@example.com`).\n"
        "It will be spoken back during the call as a reference.\n\n"
        "Send `skip` to leave it blank, `back` to change the name, "
        "or `cancel` to abort.",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step4b"), cancel_button()
        ),
    )
    bot.register_next_step_handler(sent, flow_save_client_email)


def flow_save_client_email(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_prompt_client_name(message)

    if raw.lower() in ("skip", "-", "none"):
        raw = ""
    db.set_pending_client_email(message.from_user.id, raw)
    flow_script_picker(message)


def flow_script_picker(message, page=0):
    name = message.from_user.first_name or "there"
    scripts = all_available_scripts()
    if not scripts:
        send(
            message.chat.id,
            "No scripts available yet. Contact an admin.",
            reply_markup=types.InlineKeyboardMarkup().add(cancel_button()),
        )
        return

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = scripts[start:end]

    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in page_items:
        kb.add(types.InlineKeyboardButton(f"📄 {s}", callback_data=f"pick:{s}"))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅ Prev", callback_data=f"pg:step5:{page - 1}"))
    if end < len(scripts):
        nav.append(types.InlineKeyboardButton("Next ➡", callback_data=f"pg:step5:{page + 1}"))
    if nav:
        kb.row(*nav)

    kb.row(back_button("back:step4c"), cancel_button())

    send(
        message.chat.id,
        f"*Step 5 - Script*\n\n"
        f"Please choose a template, {name} 👑 "
        f"({len(scripts)} available)",
        parse_mode="Markdown",
        reply_markup=kb,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("pg:step5:"))
def cb_pg_step5(call):
    safe_answer(call)
    clean_previous(call)
    page = int(call.data.split(":")[2])
    fake = call.message
    fake.from_user = call.from_user
    flow_script_picker(fake, page)


@bot.callback_query_handler(func=lambda c: c.data.startswith("pick:"))
def cb_pick_script(call):
    uid = call.from_user.id
    if not user_active(uid):
        safe_answer(call, "Not authorized.")
        return
    script = call.data.split(":", 1)[1]
    if script not in all_available_scripts():
        safe_answer(call, "Script no longer available.")
        return
    db.set_pending_script(uid, script)
    safe_answer(call, f"📄 {script}")
    clean_previous(call)

    sent = send(
        call.message.chat.id,
        f"*Step 6 - Confirm script*\n\n"
        f"Selected: *{script}*\n\n*Type \"Ok\" to confirm*",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step5"), cancel_button()
        ),
    )
    bot.register_next_step_handler(sent, flow_confirm_script)


def flow_confirm_script(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_script_picker(message)

    if raw.lower() != "ok":
        sent = send(
            message.chat.id, "Type *Ok* to continue.",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step5"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_confirm_script)
        return

    sent = send(
        message.chat.id,
        f"*Step 7 - Confirm Call*\n\n"
        f'Reply *"Call"* to run, or send `back` to change the script.',
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step5"), cancel_button()
        ),
    )
    bot.register_next_step_handler(sent, flow_confirm_dial)


def flow_confirm_dial(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_script_picker(message)

    if raw.lower() != "call":
        sent = send(
            message.chat.id, 'Reply *"Call"* to begin, or `back` / `cancel`.',
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step5"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_confirm_dial)
        return

    uid = message.from_user.id
    chat_id = message.chat.id
    script = db.get_pending_script(uid)
    target = db.get_pending_number(uid)
    company = db.get_pending_service(uid) or db.get_company_name() or "our office"
    client_name = db.get_pending_client_name(uid) or ""
    client_email = db.get_pending_client_email(uid) or ""

    if not (script and target):
        send(chat_id, "Missing data. Use /start to restart.")
        return _cancel_flow(chat_id, uid)

    send(chat_id, "Calling ☎️...")

    # Decide on AMD.
    use_amd = (script or "").upper() in AMD_SCRIPTS

    create_kwargs = dict(
        to=target,
        from_=twilionumber,
        url=f"{PUBLIC_URL}/webhooks/voice/play/{script}",
        record=True,
        status_callback=f"{PUBLIC_URL}/webhooks/voice/status",
        status_callback_event=[
            "initiated", "ringing", "answered", "in-progress", "completed"
        ],
    )
    if use_amd:
        create_kwargs.update(
            machine_detection="DetectMessageEnd",
            machine_detection_timeout=30,
            machine_detection_speech_threshold=2400,
            machine_detection_speech_end_threshold=1200,
            machine_detection_silence_timeout=5000,
        )

    try:
        call = twilio_client.calls.create(**create_kwargs)
    except Exception as e:
        send(chat_id, f"❌ Call failed: {e}")
        return _cancel_flow(chat_id, uid)

    db.set_call_company(call.sid, company)
    db.set_call_owner(call.sid, chat_id, uid)
    db.set_call_client(call.sid, client_name=client_name, client_email=client_email)
    db.log_campaign(uid, script, target, call.sid)

    cs.new_call(call.sid, chat_id=chat_id, script=script, company=company,
                phase="not_you")

    db.clear_pending(uid)

    client_line = ""
    if client_name or client_email:
        client_line = (
            f"\nClient: *{client_name or '-'}*"
            f"\nEmail: `{client_email or '-'}`"
        )

    amd_line = "\n🤖 AMD enabled" if use_amd else ""

    send(
        chat_id,
        f"✅ Call placed.\n"
        f"Script: *{script}*\nCompany: *{company}*{client_line}"
        f"{amd_line}\n"
        f"SID: `{call.sid}`\n\n"
        f"⌛ Waiting for the target to pick up…\n"
        f"Call stays live until verification is approved, rejected-and-retried, "
        f"or times out after {HOLD_MAX_SECONDS // 60} minutes on hold.",
        parse_mode="Markdown",
    )


# ============================================================
# SMS MODE
# ============================================================

def flow_ok_then_company_sms(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_mode_picker(message)

    if raw.lower() != "ok":
        sent = send(
            message.chat.id, "Type *Ok* to continue.",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_ok_then_company_sms)
        return

    default_company = db.get_company_name()
    if default_company:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton(f"✅ Use default: {default_company}",
                                       callback_data="company:default_sms"),
            types.InlineKeyboardButton("✏ Enter a different company",
                                       callback_data="company:custom_sms"),
        )
        kb.row(back_button("back:step3"), cancel_button())
        send(
            message.chat.id,
            f"*Step 4 - Company identity*\n\n"
            f"Company on file: *{default_company}*\n\n"
            f"Use it, or enter a temporary one for this SMS?",
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        sent = send(
            message.chat.id,
            "*Step 4 - Company identity*\n\n"
            "No default company configured.\n\n"
            "*Reply with the company name:*\n"
            "(e.g. Acme Financial / City Hospital / Metro Telecom)",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_save_company_sms)


def flow_save_company_sms(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_mode_picker(message)

    if not raw:
        sent = send(
            message.chat.id, "Please send a company name.",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_save_company_sms)
        return
    db.set_pending_service(message.from_user.id, raw)
    flow_sms_prompt(message)


@bot.callback_query_handler(func=lambda c: c.data in ("company:default_sms", "company:custom_sms"))
def cb_company_sms(call):
    safe_answer(call)
    if call.data == "company:default_sms":
        clean_previous(call)
        fake = call.message
        fake.from_user = call.from_user
        fake.text = ""
        flow_sms_prompt(fake)
    elif call.data == "company:custom_sms":
        delete_previous(call)
        sent = send(
            call.message.chat.id,
            "*Step 4 - Company identity*\n\n"
            "*Reply with the company name:*\n"
            "(e.g. Acme Financial / City Hospital / Metro Telecom)",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step3"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_save_company_sms)


def flow_sms_prompt(message):
    name = message.from_user.first_name or "there"

    example = (
        "Hello, this is an automated message from {company}. "
        "Your appointment is confirmed for tomorrow at 3 PM. "
        "Reply STOP to opt out."
    )

    kb = types.InlineKeyboardMarkup(row_width=2).row(
        back_button("back:step4_sms"), cancel_button()
    )

    sent = send(
        message.chat.id,
        f"*Step 5 - SMS message*\n\n"
        f"Type the exact text you want to send, {name} 👑\n\n"
        f"*Example:*\n"
        f"`{example}`\n\n"
        f"`{{company}}`, `{{client_name}}` and `{{client_email}}` will be "
        f"replaced with the values you entered.\n\n"
        f"Keep it under 160 characters for a single-segment SMS.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    bot.register_next_step_handler(sent, flow_sms_body)


def flow_sms_body(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_sms_prompt(message)

    if not raw:
        sent = send(
            message.chat.id, "Please type the SMS text.",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step4_sms"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_sms_body)
        return

    uid = message.from_user.id
    db.set_pending_provider(uid, "Telnyx")
    db.set_pending_script(uid, None)
    db.set_pending_sms_body(uid, raw)

    company = db.get_pending_service(uid) or db.get_company_name() or "our office"
    client_name = db.get_pending_client_name(uid) or ""
    client_email = db.get_pending_client_email(uid) or ""
    preview = (raw.replace("{company}", company)
                  .replace("{client_name}", client_name or "valued customer")
                  .replace("{client_email}", client_email))

    sent = send(
        message.chat.id,
        f"*Step 6 - Confirm SMS*\n\n"
        f"To: `{db.get_pending_number(uid)}`\n"
        f"From: *{company}*\n\n"
        f"*Preview:*\n"
        f"{preview}\n\n"
        f'Reply *"Send"* to send, or `back` to edit the text.',
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step5_sms"), cancel_button()
        ),
    )
    bot.register_next_step_handler(sent, flow_confirm_send_sms)


@bot.callback_query_handler(func=lambda c: c.data == "back:step4_sms")
def cb_back_step4_sms(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    fake.text = "ok"
    flow_ok_then_company_sms(fake)


@bot.callback_query_handler(func=lambda c: c.data == "back:step5_sms")
def cb_back_step5_sms(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    flow_sms_prompt(fake)


def flow_confirm_send_sms(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)
    if is_back(raw):
        return flow_sms_prompt(message)

    if raw.lower() != "send":
        sent = send(
            message.chat.id, 'Reply *"Send"* to send, or `back` / `cancel`.',
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
                back_button("back:step5_sms"), cancel_button()
            ),
        )
        bot.register_next_step_handler(sent, flow_confirm_send_sms)
        return

    uid = message.from_user.id
    target = db.get_pending_number(uid)
    company = db.get_pending_service(uid) or db.get_company_name() or "our office"
    client_name = db.get_pending_client_name(uid) or ""
    client_email = db.get_pending_client_email(uid) or ""
    body_template = db.get_pending_sms_body(uid) or ""
    body = (body_template.replace("{company}", company)
                         .replace("{client_name}", client_name or "valued customer")
                         .replace("{client_email}", client_email))

    if not body:
        send(message.chat.id, "No message to send. Use /start to restart.")
        return _cancel_flow(message.chat.id, uid)

    provider = db.get_pending_provider(uid) or "Telnyx"
    if provider == "MSG91":
        result = send_msg91_sms(target, body)
    else:
        result = send_telnyx_sms(target, body)

    if "error" in result:
        send(message.chat.id, f"❌ SMS failed: {result['error']}")
    else:
        send(message.chat.id, "SMS is getting sent 🗯..")

    db.clear_pending(uid)
    _send_start_greeting(uid, message.from_user.first_name or "there",
                         message.from_user.username)


# ============================================================
# Navigation
# ============================================================

@bot.callback_query_handler(func=lambda c: c.data == "back:main")
def cb_back_main(call):
    safe_answer(call)
    delete_previous(call)
    db.clear_pending(call.from_user.id)
    start_from_callback(call)


@bot.callback_query_handler(func=lambda c: c.data == "back:step1")
def cb_back_step1(call):
    safe_answer(call)
    clean_previous(call)
    db.clear_pending(call.from_user.id)
    fake = call.message
    fake.from_user = call.from_user
    flow_prompt_number(fake)


@bot.callback_query_handler(func=lambda c: c.data == "back:step2")
def cb_back_step2(call):
    safe_answer(call)
    clean_previous(call)
    target = db.get_pending_number(call.from_user.id) or "-"
    sent = send(
        call.message.chat.id,
        f"✅ Number saved: `{target}`\n\n*Step 2 - Confirm*\n\nType *Ok* to continue.",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=2).row(
            back_button("back:step1"), cancel_button()
        ),
    )
    bot.register_next_step_handler(sent, flow_confirm_ok)


@bot.callback_query_handler(func=lambda c: c.data == "back:step3")
def cb_back_step3(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    flow_mode_picker(fake)


@bot.callback_query_handler(func=lambda c: c.data == "back:step4")
def cb_back_step4(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    fake.text = "ok"
    flow_ok_then_company(fake)


@bot.callback_query_handler(func=lambda c: c.data == "back:step4b")
def cb_back_step4b(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    flow_prompt_client_name(fake)


@bot.callback_query_handler(func=lambda c: c.data == "back:step4c")
def cb_back_step4c(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    flow_prompt_client_email(fake)


@bot.callback_query_handler(func=lambda c: c.data == "back:step5")
def cb_back_step5(call):
    safe_answer(call)
    clean_previous(call)
    fake = call.message
    fake.from_user = call.from_user
    flow_script_picker(fake)


def _cancel_flow(chat_id, uid):
    db.clear_pending(uid)
    send(chat_id, "✖ Flow cancelled. Returning to /start…")
    name = "there"
    try:
        name = bot.get_chat(uid).first_name or "there"
    except Exception:
        pass
    _send_start_greeting(uid, name, None)


def _back_to_step1(chat_id, uid):
    db.clear_pending(uid)
    fake = type("M", (), {"chat": type("C", (), {"id": chat_id}),
                          "from_user": type("U", (), {"id": uid})})()
    flow_prompt_number(fake)


# ============================================================
# Custom Script (admin)
# ============================================================

def flow_custom_script_start(message):
    sent = send(
        message.chat.id,
        "✒ *Custom Script*\n\nSend a short name (no spaces), or `cancel`.",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=1).add(cancel_button()),
    )
    bot.register_next_step_handler(sent, flow_custom_script_name)


def flow_custom_script_name(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)

    if not raw or " " in raw:
        sent = send(
            message.chat.id, "Invalid name. Try again:",
            reply_markup=types.InlineKeyboardMarkup(row_width=1).add(cancel_button()),
        )
        bot.register_next_step_handler(sent, flow_custom_script_name)
        return
    if raw in all_available_scripts():
        sent = send(
            message.chat.id, f"'{raw}' exists. Choose another:",
            reply_markup=types.InlineKeyboardMarkup(row_width=1).add(cancel_button()),
        )
        bot.register_next_step_handler(sent, flow_custom_script_name)
        return
    sent = send(
        message.chat.id,
        "Paste raw TwiML starting with `<Response>`, or `cancel`:",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(row_width=1).add(cancel_button()),
    )
    bot.register_next_step_handler(sent, flow_custom_script_body, raw)


def flow_custom_script_body(message, name):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw) or raw == "/start":
        return _cancel_flow(message.chat.id, message.from_user.id)

    try:
        root = ET.fromstring(raw)
        if root.tag != "Response":
            raise ValueError("Root must be <Response>")
    except Exception as e:
        sent = send(
            message.chat.id, f"❌ Invalid TwiML: {e}\n\nTry again:",
            reply_markup=types.InlineKeyboardMarkup(row_width=1).add(cancel_button()),
        )
        bot.register_next_step_handler(sent, flow_custom_script_body, name)
        return

    db.save_script(message.from_user.id, name, raw)
    with open(os.path.join(TEMPLATES_DIR, f"{name}.xml"), "w", encoding="utf-8") as f:
        f.write(raw)
    send(message.chat.id, f"✅ Script '{name}' saved.")


# ============================================================
# ADMIN MODE
# ============================================================

def show_admin_menu(message, edit=False):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📄 Scripts", callback_data="adm:scripts"),
        types.InlineKeyboardButton("👥 Users", callback_data="adm:users"),
    )
    kb.add(
        types.InlineKeyboardButton("⚙ Settings", callback_data="adm:settings"),
        types.InlineKeyboardButton("🎙 Recordings", callback_data="adm:recordings"),
    )
    kb.add(
        types.InlineKeyboardButton("📊 Campaigns", callback_data="adm:campaigns"),
        types.InlineKeyboardButton("🩺 Health", callback_data="adm:health"),
    )
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="adm:help"))
    kb.add(types.InlineKeyboardButton("❌ Close", callback_data="close"))

    text = "🛠 *Admin Panel*\n\nManage scripts, users, settings, and review campaigns."
    if edit:
        try:
            bot.edit_message_text(text, chat_id=message.chat.id,
                                  message_id=message.message_id,
                                  parse_mode="Markdown", reply_markup=kb)
            return
        except Exception:
            pass
    send(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "adm:menu")
def cb_adm_menu(call):
    safe_answer(call)
    show_admin_menu(call.message, edit=True)


@bot.callback_query_handler(func=lambda c: c.data == "adm:help")
def cb_adm_help(call):
    safe_answer(call)
    clean_previous(call)
    send(
        call.message.chat.id,
        "📖 *Admin Help*\n\n"
        "• *Scripts* - upload, list, delete TwiML templates\n"
        "• *Users* - add, list, remove users\n"
        "• *Settings* - set default company, voice, record notice\n"
        "• *Recordings* - fetch a call recording by SID\n"
        "• *Campaigns* - last 10 outbound calls\n"
        "• *Health* - server ping\n\n"
        "Use /start to return.",
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu")
        ),
    )


@bot.callback_query_handler(func=lambda c: c.data == "adm:health")
def cb_adm_health(call):
    safe_answer(call, "OK")
    clean_previous(call)
    send(
        call.message.chat.id,
        "🩺 Server is up.",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu")
        ),
    )


# ---------- Scripts ----------

@bot.callback_query_handler(func=lambda c: c.data == "adm:scripts")
def cb_adm_scripts(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Upload New Script", callback_data="scr:upload"),
        types.InlineKeyboardButton("📜 List Scripts", callback_data="scr:list"),
        types.InlineKeyboardButton("🗑 Delete Script", callback_data="scr:delete"),
        types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu"),
    )
    send(call.message.chat.id, "📄 *Scripts*", parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "scr:upload")
def cb_scr_upload(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    flow_custom_script_start(call.message)


@bot.callback_query_handler(func=lambda c: c.data == "scr:list")
def cb_scr_list(call):
    safe_answer(call)
    clean_previous(call)
    scripts = all_available_scripts()
    if not scripts:
        send(call.message.chat.id, "No scripts available.")
        return
    text = "*Available scripts:*\n" + "\n".join(f"• `{s}`" for s in scripts)
    send(call.message.chat.id, text, parse_mode="Markdown",
         reply_markup=types.InlineKeyboardMarkup().add(
             types.InlineKeyboardButton("⬅ Back", callback_data="adm:scripts")))


@bot.callback_query_handler(func=lambda c: c.data == "scr:delete")
def cb_scr_delete(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    scripts = all_available_scripts()
    if not scripts:
        safe_answer(call, "No scripts.")
        return
    safe_answer(call)
    clean_previous(call)
    kb = types.InlineKeyboardMarkup(row_width=2)
    for s in scripts:
        kb.add(types.InlineKeyboardButton(s, callback_data=f"scr:del:{s}"))
    kb.row(types.InlineKeyboardButton("⬅ Back", callback_data="adm:scripts"))
    send(call.message.chat.id, "Pick a script to delete:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("scr:del:"))
def cb_scr_del(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    name = call.data.split(":", 2)[2]
    db.delete_script(name)
    path = os.path.join(TEMPLATES_DIR, f"{name}.xml")
    if os.path.exists(path):
        os.remove(path)
    safe_answer(call, f"Deleted {name}")
    delete_previous(call)
    send(call.message.chat.id, f"🗑 Deleted `{name}`.", parse_mode="Markdown",
         reply_markup=types.InlineKeyboardMarkup().add(
             types.InlineKeyboardButton("⬅ Back", callback_data="adm:scripts")))


# ---------- Users ----------

@bot.callback_query_handler(func=lambda c: c.data == "adm:users")
def cb_adm_users(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📜 List Users", callback_data="usr:list"),
        types.InlineKeyboardButton("➕ Add User", callback_data="usr:add"),
        types.InlineKeyboardButton("🗑 Remove User", callback_data="usr:del"),
        types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu"),
    )
    send(call.message.chat.id, "👥 *Users*", parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "usr:list")
def cb_usr_list(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    rows = db.all_users()
    if not rows:
        send(call.message.chat.id, "No users.")
        return
    lines = []
    for uid, uname, role, exp in rows:
        default = db.get_default_script(uid) or "-"
        lines.append(f"• `{uid}` @{uname or '-'} [{role}] exp {exp}  default={default}")
    send(call.message.chat.id, "\n".join(lines), parse_mode="Markdown",
         reply_markup=types.InlineKeyboardMarkup().add(
             types.InlineKeyboardButton("⬅ Back", callback_data="adm:users")))


@bot.callback_query_handler(func=lambda c: c.data == "usr:add")
def cb_usr_add(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    sent = send(call.message.chat.id,
                "Send: `<user_id> <days> [role]`\nrole = user|admin\n\nOr `cancel`.",
                parse_mode="Markdown",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅ Back", callback_data="adm:users")))
    bot.register_next_step_handler(sent, add_user_do)


def add_user_do(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw):
        return show_admin_menu(message)
    parts = raw.split()
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        send(message.chat.id, "Format: <user_id> <days> [role]")
        return
    uid, days = int(parts[0]), int(parts[1])
    role = parts[2] if len(parts) > 2 and parts[2] in ("user", "admin") else "user"
    db.upsert_user(uid, username=None, role=role, days=days)
    send(message.chat.id, f"✅ `{uid}` added ({role}, {days}d).",
         parse_mode="Markdown",
         reply_markup=types.InlineKeyboardMarkup().add(
             types.InlineKeyboardButton("⬅ Back", callback_data="adm:users")))


@bot.callback_query_handler(func=lambda c: c.data == "usr:del")
def cb_usr_del(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    sent = send(call.message.chat.id, "Send the user_id to remove, or `cancel`:")
    bot.register_next_step_handler(sent, remove_user_do)


def remove_user_do(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw):
        return show_admin_menu(message)
    if not raw.isdigit():
        send(message.chat.id, "Invalid user_id.")
        return
    db.delete_user(int(raw))
    send(message.chat.id, "🗑 Removed.",
         reply_markup=types.InlineKeyboardMarkup().add(
             types.InlineKeyboardButton("⬅ Back", callback_data="adm:users")))


# ---------- Settings ----------

@bot.callback_query_handler(func=lambda c: c.data == "adm:settings")
def cb_adm_settings(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    company = db.get_company_name() or "_(not set)_"
    voice = db.get_voice_name()
    notice = db.get_record_notice()
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✏ Set company name", callback_data="set:company"),
        types.InlineKeyboardButton("✏ Set voice", callback_data="set:voice"),
        types.InlineKeyboardButton("✏ Set record notice", callback_data="set:notice"),
        types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu"),
    )
    send(
        call.message.chat.id,
        f"⚙ *Settings*\n\n"
        f"*Company:* {company}\n"
        f"*Voice:* `{voice}`\n"
        f"*Record notice:* {notice}",
        parse_mode="Markdown",
        reply_markup=kb,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("set:"))
def cb_set(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    field = call.data.split(":", 1)[1]
    prompts = {
        "company": "Send the new *company name*, or `cancel`:",
        "voice": "Send the new *Polly voice* (e.g. `Polly.Joanna`), or `cancel`:",
        "notice": "Send the new *record notice* line, or `cancel`:",
    }
    sent = send(call.message.chat.id, prompts[field], parse_mode="Markdown")
    bot.register_next_step_handler(sent, settings_set_value, field)


def settings_set_value(message, field):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw):
        return show_admin_menu(message)
    if not raw:
        send(message.chat.id, "Empty value. Aborted.")
        return
    cfg = configparser.ConfigParser()
    cfg.read("settings.ini")
    if field == "company":
        if "company" not in cfg:
            cfg["company"] = {}
        cfg["company"]["name"] = raw
    elif field == "voice":
        if "voice" not in cfg:
            cfg["voice"] = {}
        cfg["voice"]["polly_voice"] = raw
    elif field == "notice":
        if "call" not in cfg:
            cfg["call"] = {}
        cfg["call"]["record_notice"] = raw
    with open("settings.ini", "w", encoding="utf-8") as f:
        cfg.write(f)
    send(message.chat.id, f"✅ Updated *{field}*.",
         parse_mode="Markdown",
         reply_markup=types.InlineKeyboardMarkup().add(
             types.InlineKeyboardButton("⬅ Back", callback_data="adm:settings")))


# ---------- Recordings ----------

@bot.callback_query_handler(func=lambda c: c.data == "adm:recordings")
def cb_adm_recordings(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)
    sent = send(call.message.chat.id, "Send a Call SID to fetch its recording, or `cancel`:")
    bot.register_next_step_handler(sent, fetch_recording)


def fetch_recording(message):
    track_user_message(message)
    raw = (message.text or "").strip()
    if is_cancel(raw):
        return show_admin_menu(message)
    row = db.get_campaign_by_sid(raw)
    if not row:
        send(message.chat.id, "No campaign with that SID.")
        return
    _, _, _, _, recording = row
    if not recording:
        send(message.chat.id, "No recording available yet.")
        return
    bot.send_audio(message.chat.id, f"{recording}.mp3")


# ---------- Campaigns ----------

@bot.callback_query_handler(func=lambda c: c.data == "adm:campaigns")
def cb_adm_campaigns(call):
    if not db.is_admin(call.from_user.id):
        safe_answer(call, "Admin only.")
        return
    safe_answer(call)
    clean_previous(call)

    rows = db.list_campaigns(limit=10)
    if not rows:
        send(call.message.chat.id, "No campaigns yet.",
             reply_markup=types.InlineKeyboardMarkup().add(
                 types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu")))
        return

    lines = []
    for row in rows:
        _id, uid, script, target, status, sid, recording, ts = row
        lines.append(f"• `{target}` | {script} | {status} | {ts}")

    send(
        call.message.chat.id,
        "*Last 10 campaigns:*\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅ Back", callback_data="adm:menu")
        ),
    )


# ---------- Close ----------

@bot.callback_query_handler(func=lambda c: c.data == "close")
def cb_close(call):
    delete_previous(call)
    safe_answer(call)
    start_from_callback(call)