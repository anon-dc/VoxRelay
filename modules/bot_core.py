"""
Telegram bot instance plus message send/track helpers.
Imported by every flow module that needs to talk to Telegram.
"""

import threading
import time
from collections import defaultdict, deque

import telebot
from telebot import types

from cred import API_TOKEN, PUBLIC_URL
from modules import call_state as cs  # noqa: F401  (imported for side access)

# ============================================================
# Bot instance
# ============================================================

bot = telebot.TeleBot(API_TOKEN, threaded=False)

bot.remove_webhook()
bot.set_webhook(
    url=f"{PUBLIC_URL}/telegram",
    drop_pending_updates=True,
    allowed_updates=["message", "callback_query", "edited_message"],
)

# ============================================================
# Auto-delete tracking
# ============================================================

AUTO_DELETE_SECONDS = 30

_last_message = {}
_last_user_message = {}

_handled_updates = deque(maxlen=200)

TRAFFIC = defaultdict(lambda: deque(maxlen=50))


def _safe_delete(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass


def send(chat_id, text, **kwargs):
    prev_bot = _last_message.get(chat_id)
    if prev_bot:
        threading.Timer(AUTO_DELETE_SECONDS, _safe_delete,
                        args=(chat_id, prev_bot)).start()

    prev_user = _last_user_message.get(chat_id)
    if prev_user:
        threading.Timer(AUTO_DELETE_SECONDS, _safe_delete,
                        args=(chat_id, prev_user)).start()

    msg = bot.send_message(chat_id, text, **kwargs)
    _last_message[chat_id] = msg.message_id
    return msg


def track_user_message(message):
    if not message or not message.text:
        return
    if message.text.startswith("/"):
        return
    _last_user_message[message.chat.id] = message.message_id


def safe_answer(call, text=None, alert=False):
    try:
        bot.answer_callback_query(call.id, text=text, show_alert=alert)
    except Exception:
        pass


def clean_previous(call):
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass


def delete_previous(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass


def update_id_seen(update_id):
    if update_id in _handled_updates:
        return True
    _handled_updates.append(update_id)
    return False


def log_traffic(update_type, uid, username, chat_id, extra=""):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    uname = f"@{username}" if username else "@-"
    line = f"[TG] {ts} | {update_type:8s} | uid={uid} | {uname} | chat={chat_id}"
    if extra:
        line += f" | {extra}"
    print(line, flush=True)

    TRAFFIC[uid].append({
        "ts": ts, "type": update_type,
        "username": uname, "chat_id": chat_id, "extra": extra,
    })


# ============================================================
# Shared UI helpers
# ============================================================

def back_button(callback_data="back:main", label="⬅ Back"):
    return types.InlineKeyboardButton(label, callback_data=callback_data)


def cancel_button():
    return types.InlineKeyboardButton("✖ Cancel", callback_data="back:main")


def is_cancel(text):
    t = (text or "").strip().lower()
    return t in ("cancel", "/cancel", "exit", "quit", "stop", "✖ cancel")


def is_back(text):
    t = (text or "").strip().lower()
    return t in ("back", "⬅ back", "/back")