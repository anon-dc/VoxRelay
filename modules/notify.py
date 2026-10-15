"""
Outbound call notification helpers. Push formatted call events to Telegram.
"""

import threading

import dbase as db
from modules.bot_core import send

_call_events_seen = set()
_call_events_lock = threading.Lock()


def notify_caller(call_sid, message, **kwargs):
    try:
        chat_id, _uid = db.get_call_owner(call_sid)
        if chat_id:
            send(chat_id, message, **kwargs)
            return chat_id
    except Exception as e:
        print(f"[notify] failed for {call_sid}: {e}", flush=True)
    return None


def format_digits(digits):
    if not digits:
        return "_no input_"
    safe = str(digits).replace("`", "'")
    return f"`{safe}`"


def mark_event_once(sid, status):
    """Return True the first time we see (sid, status); False on retries."""
    key = (sid, status)
    with _call_events_lock:
        if key in _call_events_seen:
            return False
        _call_events_seen.add(key)
        if len(_call_events_seen) > 5000:
            _call_events_seen.clear()
            _call_events_seen.add(key)
        return True


def _client_lines(call_sid):
    """Return pre-formatted 'Client:' / 'Email:' lines or empty string."""
    try:
        client_name, client_email = db.get_call_client(call_sid)
    except Exception:
        return ""
    if not (client_name or client_email):
        return ""
    return (
        f"\nClient: *{client_name or '-'}*"
        f"\nEmail: `{client_email or '-'}`"
    )