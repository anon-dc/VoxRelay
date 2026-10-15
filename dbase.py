import sqlite3
import configparser
import threading
from datetime import date, timedelta

DB_PATH = "UserDetails.db"
SETTINGS_PATH = "settings.ini"

# ============================================================
# Thread-local connection management
# ============================================================
#
# Each thread gets its own sqlite3.Connection. This is required
# because Flask handles requests on one thread and telebot may
# dispatch handler callbacks on another — sharing one connection
# causes "Recursive use of cursors not allowed".
#
# WAL mode + busy_timeout lets concurrent readers coexist with
# the single writer.

_tls = threading.local()
_schema_lock = threading.Lock()
_schema_ready = False


def get_conn():
    """Return a per-thread sqlite3 connection, creating it on first use."""
    conn = getattr(_tls, "conn", None)
    if conn is None:
        conn = sqlite3.connect(
            DB_PATH,
            timeout=30,
            check_same_thread=False,
            isolation_level=None,   # autocommit off; we use explicit BEGIN
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA foreign_keys=ON;")
        except sqlite3.Error:
            pass
        _tls.conn = conn
    return conn


def cursor():
    """Fresh cursor for the current thread."""
    return get_conn().cursor()


def commit():
    try:
        get_conn().commit()
    except sqlite3.Error:
        pass


def rollback():
    try:
        get_conn().rollback()
    except sqlite3.Error:
        pass


def _execute(sql, params=(), fetch=None):
    """
    Run a single statement on a fresh cursor and return the result.
    fetch: None | 'one' | 'all' | 'lastrowid'
    Uses an explicit transaction so writes are atomic.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        if fetch == "lastrowid":
            conn.commit()
            return cur.lastrowid
        conn.commit()
        return None
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ============================================================
# Schema
# ============================================================

def _init_schema():
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    role        TEXT DEFAULT 'user',
                    expiry_date TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Scripts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id    INTEGER,
                    name        TEXT UNIQUE,
                    twiml       TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Campaigns (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER,
                    script_name TEXT,
                    target_no   TEXT,
                    status      TEXT,
                    call_sid    TEXT,
                    recording   TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS OtpRequests (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id  TEXT,
                    phone       TEXT,
                    user_id     INTEGER,
                    verified    INTEGER DEFAULT 0,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS UserDefaults (
                    user_id  INTEGER PRIMARY KEY,
                    script   TEXT
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS VerifySessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER,
                    target_no  TEXT,
                    method     TEXT,
                    attempts   INTEGER DEFAULT 0,
                    verified   INTEGER DEFAULT 0,
                    request_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS VerifyAudit (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  INTEGER,
                    target_no   TEXT,
                    method      TEXT,
                    result      TEXT,
                    csr_id      INTEGER,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS PendingFlow (
                    user_id       INTEGER PRIMARY KEY,
                    number        TEXT,
                    mode          TEXT,
                    script        TEXT,
                    service       TEXT,
                    provider      TEXT,
                    sms_body      TEXT,
                    client_name   TEXT,
                    client_email  TEXT
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS CallContext (
                    call_sid        TEXT PRIMARY KEY,
                    company         TEXT,
                    client_name     TEXT,
                    client_email    TEXT,
                    owner_chat_id   INTEGER,
                    owner_uid       INTEGER,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
            conn.commit()
        finally:
            cur.close()

        # One-time migrations for older DBs (safe to re-run).
        for tbl, col_def in (
            ("CallContext", "owner_chat_id INTEGER"),
            ("CallContext", "owner_uid INTEGER"),
            ("CallContext", "client_name TEXT"),
            ("CallContext", "client_email TEXT"),
            ("PendingFlow", "sms_body TEXT"),
            ("PendingFlow", "client_name TEXT"),
            ("PendingFlow", "client_email TEXT"),
        ):
            cur = conn.cursor()
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_def}")
                conn.commit()
            except sqlite3.Error:
                pass
            finally:
                cur.close()

        _schema_ready = True


_init_schema()


# ============================================================
# Users
# ============================================================

def upsert_user(user_id, username=None, role="user", days=30):
    exp = (date.today() + timedelta(days=days)).isoformat()
    row = _execute("SELECT user_id FROM Users WHERE user_id=?",
                   (user_id,), fetch="one")
    if row:
        _execute("UPDATE Users SET username=?, expiry_date=? WHERE user_id=?",
                 (username, exp, user_id))
    else:
        _execute(
            "INSERT INTO Users (user_id, username, role, expiry_date) VALUES (?,?,?,?)",
            (user_id, username, role, exp),
        )


def get_user(user_id):
    return _execute(
        "SELECT user_id, username, role, expiry_date FROM Users WHERE user_id=?",
        (user_id,), fetch="one",
    )


def is_admin(user_id):
    row = get_user(user_id)
    return bool(row and row[2] == "admin")


def is_active(user_id):
    row = get_user(user_id)
    if not row or not row[3]:
        return False
    try:
        return date.fromisoformat(row[3]) >= date.today()
    except Exception:
        return False


def delete_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Users WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM UserDefaults WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM PendingFlow WHERE user_id=?", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def all_users():
    return _execute(
        "SELECT user_id, username, role, expiry_date FROM Users",
        fetch="all",
    )


# ============================================================
# Scripts
# ============================================================

def save_script(owner_id, name, twiml):
    _execute(
        "INSERT OR REPLACE INTO Scripts (owner_id, name, twiml) VALUES (?,?,?)",
        (owner_id, name, twiml),
    )


def get_script(name):
    row = _execute("SELECT twiml FROM Scripts WHERE name=?",
                   (name,), fetch="one")
    return row[0] if row else None


def list_scripts():
    return _execute("SELECT id, name, owner_id FROM Scripts", fetch="all")


def delete_script(name):
    _execute("DELETE FROM Scripts WHERE name=?", (name,))


# ============================================================
# Campaigns
# ============================================================

def log_campaign(user_id, script_name, target_no, call_sid, status="initiated"):
    _execute(
        """INSERT INTO Campaigns (user_id, script_name, target_no, status, call_sid)
           VALUES (?,?,?,?,?)""",
        (user_id, script_name, target_no, status, call_sid),
    )


def update_campaign(call_sid, status=None, recording=None):
    if status and recording:
        _execute("UPDATE Campaigns SET status=?, recording=? WHERE call_sid=?",
                 (status, recording, call_sid))
    elif status:
        _execute("UPDATE Campaigns SET status=? WHERE call_sid=?",
                 (status, call_sid))
    elif recording:
        _execute("UPDATE Campaigns SET recording=? WHERE call_sid=?",
                 (recording, call_sid))


def get_campaign_by_sid(call_sid):
    return _execute(
        """SELECT user_id, script_name, target_no, status, recording
           FROM Campaigns WHERE call_sid=?""",
        (call_sid,), fetch="one",
    )


def list_campaigns(limit=10, user_id=None):
    if user_id is None:
        return _execute(
            """SELECT id, user_id, script_name, target_no, status,
                      call_sid, recording, created_at
               FROM Campaigns ORDER BY id DESC LIMIT ?""",
            (limit,), fetch="all",
        )
    return _execute(
        """SELECT id, user_id, script_name, target_no, status,
                  call_sid, recording, created_at
           FROM Campaigns WHERE user_id=? ORDER BY id DESC LIMIT ?""",
        (user_id, limit), fetch="all",
    )


# ============================================================
# OTP requests
# ============================================================

def save_otp_request(request_id, phone, user_id):
    _execute(
        "INSERT INTO OtpRequests (request_id, phone, user_id) VALUES (?,?,?)",
        (request_id, phone, user_id),
    )


def mark_otp_verified(request_id):
    _execute("UPDATE OtpRequests SET verified=1 WHERE request_id=?",
             (request_id,))


def get_otp_request(request_id):
    return _execute(
        """SELECT request_id, phone, user_id, verified
           FROM OtpRequests WHERE request_id=?""",
        (request_id,), fetch="one",
    )


def latest_otp_for(phone):
    return _execute(
        """SELECT id, request_id, verified FROM OtpRequests
           WHERE phone=? ORDER BY id DESC LIMIT 1""",
        (phone,), fetch="one",
    )


# ============================================================
# Per-user default script
# ============================================================

def set_default_script(user_id, script):
    _execute(
        "INSERT OR REPLACE INTO UserDefaults (user_id, script) VALUES (?,?)",
        (user_id, script),
    )


def get_default_script(user_id):
    row = _execute("SELECT script FROM UserDefaults WHERE user_id=?",
                   (user_id,), fetch="one")
    return row[0] if row else None


def clear_default_script(user_id):
    _execute("DELETE FROM UserDefaults WHERE user_id=?", (user_id,))


# ============================================================
# Verification sessions
# ============================================================

def new_verify_session(user_id, target_no, method):
    return _execute(
        "INSERT INTO VerifySessions (user_id, target_no, method) VALUES (?,?,?)",
        (user_id, target_no, method), fetch="lastrowid",
    )


def attach_otp_request(session_id, request_id):
    _execute("UPDATE VerifySessions SET request_id=? WHERE id=?",
             (request_id, session_id))


def get_session(session_id):
    return _execute(
        """SELECT id, user_id, target_no, method, attempts, verified, request_id
           FROM VerifySessions WHERE id=?""",
        (session_id,), fetch="one",
    )


def latest_session_for(target_no):
    return _execute(
        """SELECT id, user_id, target_no, method, attempts, verified, request_id
           FROM VerifySessions WHERE target_no=?
           ORDER BY id DESC LIMIT 1""",
        (target_no,), fetch="one",
    )


def record_verify_attempt(session_id, verified):
    _execute(
        """UPDATE VerifySessions SET attempts = attempts + 1, verified = ?
           WHERE id = ?""",
        (1 if verified else 0, session_id),
    )


# ============================================================
# Verification audit log
# ============================================================

def audit_verify(session_id, target_no, method, result, csr_id=None):
    _execute(
        """INSERT INTO VerifyAudit (session_id, target_no, method, result, csr_id)
           VALUES (?,?,?,?,?)""",
        (session_id, target_no, method, result, csr_id),
    )


def list_audit(target_no=None, limit=100):
    if target_no is None:
        return _execute(
            """SELECT id, session_id, target_no, method, result, csr_id, created_at
               FROM VerifyAudit ORDER BY id DESC LIMIT ?""",
            (limit,), fetch="all",
        )
    return _execute(
        """SELECT id, session_id, target_no, method, result, csr_id, created_at
           FROM VerifyAudit WHERE target_no=? ORDER BY id DESC LIMIT ?""",
        (target_no, limit), fetch="all",
    )


# ============================================================
# Pending flow state
# ============================================================

_PENDING_COLUMNS = {
    "number", "mode", "script", "service", "provider",
    "sms_body", "client_name", "client_email",
}


def _pending_upsert(user_id, column, value):
    if column not in _PENDING_COLUMNS:
        raise ValueError(f"bad column: {column}")

    row = _execute("SELECT user_id FROM PendingFlow WHERE user_id=?",
                   (user_id,), fetch="one")
    if row:
        _execute(f"UPDATE PendingFlow SET {column}=? WHERE user_id=?",
                 (value, user_id))
    else:
        _execute(f"INSERT INTO PendingFlow (user_id, {column}) VALUES (?, ?)",
                 (user_id, value))


def set_pending_number(user_id, number):   _pending_upsert(user_id, "number",   number)
def set_pending_mode(user_id, mode):       _pending_upsert(user_id, "mode",     mode)
def set_pending_script(user_id, script):   _pending_upsert(user_id, "script",   script)
def set_pending_service(user_id, service): _pending_upsert(user_id, "service",  service)
def set_pending_provider(user_id, prov):   _pending_upsert(user_id, "provider", prov)
def set_pending_sms_body(user_id, body):   _pending_upsert(user_id, "sms_body", body)
def set_pending_client_name(user_id, v):   _pending_upsert(user_id, "client_name",  v)
def set_pending_client_email(user_id, v):  _pending_upsert(user_id, "client_email", v)


def _pending_get(user_id, column):
    if column not in _PENDING_COLUMNS:
        raise ValueError(f"bad column: {column}")
    row = _execute(f"SELECT {column} FROM PendingFlow WHERE user_id=?",
                   (user_id,), fetch="one")
    return row[0] if row else None


def get_pending_number(user_id):       return _pending_get(user_id, "number")
def get_pending_mode(user_id):         return _pending_get(user_id, "mode")
def get_pending_script(user_id):       return _pending_get(user_id, "script")
def get_pending_service(user_id):      return _pending_get(user_id, "service")
def get_pending_provider(user_id):     return _pending_get(user_id, "provider")
def get_pending_sms_body(user_id):     return _pending_get(user_id, "sms_body")
def get_pending_client_name(user_id):  return _pending_get(user_id, "client_name")
def get_pending_client_email(user_id): return _pending_get(user_id, "client_email")


def clear_pending(user_id):
    _execute("DELETE FROM PendingFlow WHERE user_id=?", (user_id,))


# ============================================================
# Settings (settings.ini)
# ============================================================

def _load_settings():
    cfg = configparser.ConfigParser()
    cfg.read(SETTINGS_PATH)
    return cfg


def _save_settings(cfg):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        cfg.write(f)


def get_company_name():
    return _load_settings().get("company", "name", fallback="").strip()


def set_company_name(value):
    cfg = _load_settings()
    if "company" not in cfg:
        cfg["company"] = {}
    cfg["company"]["name"] = (value or "").strip()
    _save_settings(cfg)


def get_company_website():
    return _load_settings().get("company", "website", fallback="").strip()


def get_company_support_phone():
    return _load_settings().get("company", "support_phone", fallback="").strip()


def get_voice_name():
    return _load_settings().get("voice", "polly_voice", fallback="Polly.Joanna")


def get_record_notice():
    return _load_settings().get("call", "record_notice",
                                fallback="This call may be recorded.")


# ============================================================
# Support links
# ============================================================

def get_support_contact():
    return _load_settings().get("support", "contact",
                                fallback="https://t.me/dc_aisupport").strip()


def get_purchase_url():
    return _load_settings().get("support", "purchase_url",
                                fallback="https://t.me/dc_aisupport").strip()


def get_usage_url():
    return _load_settings().get("support", "usage_url",
                                fallback="https://t.me/dc_aisupport").strip()


def get_support_label():
    return _load_settings().get("support", "support_label",
                                fallback="@dc_aisupport").strip()


# ============================================================
# Per-call company + owner + client
# ============================================================

def set_call_company(call_sid, company):
    """Store the company used for a call without clobbering owner fields."""
    row = _execute("SELECT call_sid FROM CallContext WHERE call_sid=?",
                   (call_sid,), fetch="one")
    if row:
        _execute("UPDATE CallContext SET company=? WHERE call_sid=?",
                 (company, call_sid))
    else:
        _execute(
            """INSERT INTO CallContext
                   (call_sid, company, client_name, client_email,
                    owner_chat_id, owner_uid)
               VALUES (?, ?, NULL, NULL, NULL, NULL)""",
            (call_sid, company),
        )


def get_call_company(call_sid):
    row = _execute("SELECT company FROM CallContext WHERE call_sid=?",
                   (call_sid,), fetch="one")
    return row[0] if row else None


def set_call_owner(call_sid, chat_id, uid):
    """Store the Telegram chat that initiated this call."""
    row = _execute("SELECT call_sid FROM CallContext WHERE call_sid=?",
                   (call_sid,), fetch="one")
    if row:
        _execute(
            "UPDATE CallContext SET owner_chat_id=?, owner_uid=? WHERE call_sid=?",
            (chat_id, uid, call_sid),
        )
    else:
        _execute(
            """INSERT INTO CallContext
                   (call_sid, company, client_name, client_email,
                    owner_chat_id, owner_uid)
               VALUES (?, NULL, NULL, NULL, ?, ?)""",
            (call_sid, chat_id, uid),
        )


def get_call_owner(call_sid):
    """Return (owner_chat_id, owner_uid) or (None, None)."""
    row = _execute(
        "SELECT owner_chat_id, owner_uid FROM CallContext WHERE call_sid=?",
        (call_sid,), fetch="one",
    )
    return (row[0], row[1]) if row else (None, None)


def set_call_client(call_sid, client_name=None, client_email=None):
    """Store per-call client name/email without clobbering other fields."""
    row = _execute("SELECT call_sid FROM CallContext WHERE call_sid=?",
                   (call_sid,), fetch="one")
    if row:
        _execute(
            "UPDATE CallContext SET client_name=?, client_email=? WHERE call_sid=?",
            (client_name, client_email, call_sid),
        )
    else:
        _execute(
            """INSERT INTO CallContext
                   (call_sid, company, client_name, client_email,
                    owner_chat_id, owner_uid)
               VALUES (?, NULL, ?, ?, NULL, NULL)""",
            (call_sid, client_name, client_email),
        )


def get_call_client(call_sid):
    """Return (client_name, client_email) or (None, None)."""
    row = _execute(
        "SELECT client_name, client_email FROM CallContext WHERE call_sid=?",
        (call_sid,), fetch="one",
    )
    return (row[0], row[1]) if row else (None, None)


# ============================================================
# Maintenance
# ============================================================

def delete_all_users():
    _execute("DELETE FROM Users")


def delete_all_scripts():
    _execute("DELETE FROM Scripts")


def delete_all_campaigns():
    _execute("DELETE FROM Campaigns")


def delete_all_verifications():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM VerifySessions")
        cur.execute("DELETE FROM VerifyAudit")
        cur.execute("DELETE FROM OtpRequests")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()