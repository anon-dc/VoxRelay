"""
TwiML template loading, placeholder substitution, and <Gather> instrumentation.
"""

import os
import xml.etree.ElementTree as ET

from flask import abort

import dbase as db

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates"
)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

PAGE_SIZE = 6


# ============================================================
# Template registry
# ============================================================

def list_template_files():
    try:
        names = []
        for f in os.listdir(TEMPLATES_DIR):
            if not f or f.startswith("."):
                continue
            if f.lower().endswith(".xml") and len(f) > 4:
                names.append(f[:-4])
        return sorted(names)
    except FileNotFoundError:
        return []


def all_available_scripts():
    db_names = {name for _, name, _ in db.list_scripts()}
    file_names = set(list_template_files())
    return sorted(db_names | file_names)


# ============================================================
# Placeholder substitution
# ============================================================

def _spoken_email(email):
    """Turn 'jsmith@example.com' into a TTS-friendly phrase."""
    if not email:
        return ""
    e = email.strip()
    at = e.find("@")
    if at < 0:
        return f" {e} "
    local = " ".join(e[:at])
    domain = e[at + 1:].replace(".", " dot ")
    return f", for the account registered to {local} at {domain}, "


def _substitute(twiml, company, client_name=None, client_email=None):
    company = (company or "").strip()
    voice = db.get_voice_name()
    notice = db.get_record_notice()
    website = db.get_company_website()
    support = db.get_company_support_phone()

    name = (client_name or "").strip() or "valued customer"
    spoken_email = _spoken_email(client_email)

    twiml = twiml.replace("{{company}}", company)
    twiml = twiml.replace("{{voice}}", voice)
    twiml = twiml.replace("{{record_notice}}", notice)
    twiml = twiml.replace("{{website}}", website)
    twiml = twiml.replace("{{support_phone}}", support)
    twiml = twiml.replace("{{client_name}}", name)
    twiml = twiml.replace("{{client_email}}", spoken_email)
    return twiml


# ============================================================
# <Gather> instrumentation (step/script/company query params)
# ============================================================

def _instrument_twiml(xml_text, script_name=None, company=None):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text

    def _local(tag):
        return tag.split("}", 1)[-1] if "}" in tag else tag

    step_idx = 0
    for elem in root.iter():
        if _local(elem.tag) != "Gather":
            continue
        step_idx += 1
        action = elem.get("action") or "/webhooks/voice/gather"
        sep = "&" if "?" in action else "?"
        extra = f"step={step_idx}"
        if script_name:
            extra += f"&script={script_name}"
        if company:
            extra += f"&company={company}"
        if "step=" not in action:
            elem.set("action", f"{action}{sep}{extra}")

    try:
        return ET.tostring(root, encoding="unicode")
    except Exception:
        return xml_text


# ============================================================
# Resolution
# ============================================================

def resolve_twiml(name, call_sid=None):
    twiml = db.get_script(name)
    if not twiml:
        path = os.path.join(TEMPLATES_DIR, f"{name}.xml")
        if not os.path.exists(path):
            for f in os.listdir(TEMPLATES_DIR):
                if f.lower() == f"{name}.xml".lower():
                    path = os.path.join(TEMPLATES_DIR, f)
                    break
        if not os.path.exists(path):
            abort(404)
        with open(path, "r", encoding="utf-8") as f:
            twiml = f.read()

    company = None
    client_name = None
    client_email = None
    if call_sid:
        company = db.get_call_company(call_sid)
        client_name, client_email = db.get_call_client(call_sid)
    if not company:
        company = db.get_company_name()

    twiml = _substitute(twiml, company,
                        client_name=client_name,
                        client_email=client_email)
    twiml = _instrument_twiml(twiml, script_name=name, company=company)
    return twiml