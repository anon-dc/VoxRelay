"""
Telegram webhook entry point plus /debug/* and /health.
"""

from flask import Blueprint, request, abort
import telebot

from modules import call_state as cs
from modules.bot_core import bot, log_traffic, update_id_seen, TRAFFIC

tg_bp = Blueprint("telegram_entry", __name__)


@tg_bp.route("/telegram", methods=["POST"])
def telegram_webhook():
    if request.headers.get("content-type") != "application/json":
        abort(403)

    raw = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(raw)

    if update_id_seen(update.update_id):
        print(f"[TG] duplicate update_id={update.update_id} skipped", flush=True)
        return "", 200

    try:
        if getattr(update, "message", None):
            m = update.message
            log_traffic("message", m.from_user.id,
                        m.from_user.username or m.from_user.first_name or "",
                        m.chat.id, extra=f"text={m.text!r}")
        elif getattr(update, "callback_query", None):
            c_ = update.callback_query
            log_traffic("callback", c_.from_user.id,
                        c_.from_user.username or c_.from_user.first_name or "",
                        c_.message.chat.id, extra=f"data={c_.data!r}")
        elif getattr(update, "edited_message", None):
            m = update.edited_message
            log_traffic("edit", m.from_user.id,
                        m.from_user.username or m.from_user.first_name or "",
                        m.chat.id, extra="edited")
    except Exception as e:
        print(f"[TG] log error: {e}", flush=True)

    bot.process_new_updates([update])
    return "", 200


@tg_bp.route("/debug/traffic", methods=["GET"])
def debug_traffic():
    return {
        "unique_users": len(TRAFFIC),
        "per_user": {uid: list(events) for uid, events in TRAFFIC.items()},
    }, 200


@tg_bp.route("/debug/calls", methods=["GET"])
def debug_calls():
    """Live call states. Protect at the proxy/ingress."""
    return {"live_calls": cs._state}, 200


@tg_bp.route("/health", methods=["GET"])
def health():
    return {"ok": True}, 200