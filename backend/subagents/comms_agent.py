"""A2A Comms Agent — recovery notices to defaulting suppliers.

Provider ladder, decided per call and recorded in the audit trail either way:

1. ``meta``     — Meta's WhatsApp Cloud API (free tier): fully configured when
   ``WHATSAPP_ACCESS_TOKEN`` + ``WHATSAPP_PHONE_NUMBER_ID`` are set. Indian
   recipients need an approved template, so with ``WHATSAPP_TEMPLATE_NAME``
   set the rendered Rule 88D notice rides in the template's body variable;
   without it the send is freeform (works inside 24h session windows and for
   non-India recipients).
2. ``email``    — recovery notice by email: SendGrid when ``SENDGRID_API_KEY``
   is set, otherwise plain SMTP via ``RECOVERY_SMTP_HOST``. Needs
   ``RECOVERY_EMAIL_FROM`` either way. This outranks Twilio because Twilio's
   India WhatsApp path is Trial-blocked (Content API template creation needs
   an upgraded account); if that upgrade lands, unset the SendGrid key to
   hand the channel back to Twilio.
3. ``twilio``   — Twilio's WhatsApp API when ``TWILIO_ACCOUNT_SID`` /
   ``TWILIO_AUTH_TOKEN`` / ``TWILIO_WHATSAPP_FROM`` are configured. India also
   requires ``TWILIO_CONTENT_SID`` (Content API template).
4. ``simulated`` — no provider keys: identical audit trail, no send.

WhatsApp channels validate the vendor phone (E.164 normalisation); the email
channel validates the vendor email instead — a dispatch attempt without the
address its channel needs fails closed and is audited. The mode is surfaced
in the UI, and every attempt — delivered, simulated, failed, invalid
recipient, missing recipient — becomes a DynamoDB audit row. A simulated
dispatch must never be mistaken for a delivered message.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from backend.db import results as db

_TWILIO_ENV = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")
_META_ENV = ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")
_EMAIL_ENV = ("RECOVERY_EMAIL_FROM",)
_EMAIL_SUBJECT = "GST ITC Recovery Notice (Rule 88D)"


def mode() -> str:
    """'meta' | 'email' | 'twilio' when fully configured, else 'simulated'."""
    if all(os.environ.get(k) for k in _META_ENV):
        return "meta"
    if os.environ.get("SENDGRID_API_KEY") and all(os.environ.get(k) for k in _EMAIL_ENV):
        return "email"
    if os.environ.get("RECOVERY_SMTP_HOST") and all(os.environ.get(k) for k in _EMAIL_ENV):
        return "email"
    if all(os.environ.get(k) for k in _TWILIO_ENV):
        return "twilio"
    return "simulated"


def normalize_phone(raw: str | None) -> str | None:
    """Vendor register phones → Twilio WhatsApp form (``whatsapp:+9198…``).

    Accepts '+919876543210' and '919876543210' as-is; a bare 10-digit Indian
    local number is prefixed with 91 (every vendor here is Indian); the common
    trunk-prefixed form ``091 98201 77890`` loses the leading zero (E.164
    country codes never start with one). Anything else — short junk, over-long
    strings, numbers that would start with 0, non-phone garbage — is rejected
    as None rather than becoming a noisy ``whatsapp:`` audit row Twilio would
    bounce anyway.
    """
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) == 13 and digits.startswith("091"):
        digits = digits[1:]  # trunk-prefixed country code → E.164
    if len(digits) == 10:  # Indian local mobile → E.164 with the country code
        digits = "91" + digits
    if not 12 <= len(digits) <= 15 or digits.startswith("0"):
        return None
    return f"whatsapp:+{digits}"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(raw: str | None) -> str | None:
    """Vendor register emails → a sane address, or None for junk."""
    if not raw:
        return None
    addr = str(raw).strip()
    return addr if _EMAIL_RE.match(addr) and len(addr) <= 254 else None


def send_recovery_notice(
    *,
    period: str,
    invoice_no: str,
    supplier: str,
    phone: str | None,
    message: str,
    email: str | None = None,
) -> dict[str, Any]:
    """Dispatch one recovery notice; record the attempt in the audit trail.

    WhatsApp channels use ``phone``; the email channel uses ``email``. The
    active channel must have its recipient: an email-mode dispatch without a
    valid vendor address fails closed exactly like a WhatsApp dispatch
    without a phone. Returns
    ``{"ok": bool, "mode": str, "detail": str, "message_id": str|None}``.
    Never raises: a provider failure is an ``ok=False`` audit record.
    """
    result: dict[str, Any] = {"ok": False, "mode": mode(),
                              "detail": "", "message_id": None}

    if result["mode"] == "email":
        to = normalize_email(email)
        if not to:
            result["detail"] = ("no vendor email on file" if not email
                                else f"vendor email {email!r} is not valid")
            db.record_dispatch(period, invoice_no, supplier, phone,
                               result["mode"], message, error=result["detail"])
            return result
    else:
        # WhatsApp channels (and simulation, which mirrors their validation):
        # normalise BEFORE the mode branch, so every path audits the number
        # it would actually use — simulation must not record ok=True for a
        # phone the live provider would reject.
        to = normalize_phone(phone)
        if not phone:
            result["detail"] = "no vendor phone on file"
            db.record_dispatch(period, invoice_no, supplier, phone,
                               result["mode"], message, error=result["detail"])
            return result
        if not to:
            result["detail"] = f"vendor phone {phone!r} is not a valid E.164 number"
            db.record_dispatch(period, invoice_no, supplier, phone,
                               result["mode"], message, error=result["detail"])
            return result

    try:
        sid = _dispatch(result, to, message)
    except Exception as exc:  # noqa: BLE001 — provider errors are audit rows
        result["detail"] = f"{type(exc).__name__}: {exc}"
        db.record_dispatch(period, invoice_no, supplier, to,
                           result["mode"], message, error=result["detail"])
        return result

    result["ok"] = True
    result["message_id"] = sid
    db.record_dispatch(period, invoice_no, supplier, to,
                       result["mode"], message, provider_message_id=sid)
    return result


def _dispatch(result: dict[str, Any], to: str, message: str) -> str | None:
    """Send through the active provider; None when simulated.

    Provider errors raise; the caller turns them into ok=False audit rows.
    On success ``result["detail"]`` names the provider that delivered.
    """
    if result["mode"] == "simulated":
        result["detail"] = "simulated dispatch (no provider keys configured)"
        return None
    if result["mode"] == "meta":
        sid = _meta_send(to, message)
        result["detail"] = "sent via Meta WhatsApp Cloud API"
        return sid
    if result["mode"] == "email":
        sid = _email_send(to, message)
        result["detail"] = ("sent via SendGrid" if os.environ.get("SENDGRID_API_KEY")
                            else f"sent via SMTP ({os.environ.get('RECOVERY_SMTP_HOST')})")
        return sid
    sid = _twilio_send(to, message)
    result["detail"] = "sent via Twilio WhatsApp API"
    return sid


def _email_send(to: str, body: str) -> str:
    """Deliver the notice by email; returns a provider message id.

    SendGrid v3 when ``SENDGRID_API_KEY`` is set (returns the X-Message-Id
    header), otherwise plain SMTP (``RECOVERY_SMTP_HOST`` + optional
    ``RECOVERY_SMTP_PORT``/``_USER``/``_PASS``; 587 STARTTLS by default,
    465 implicit TLS). Raises on any failure — the caller audits it.
    """
    sender = _bare_address(os.environ["RECOVERY_EMAIL_FROM"])
    if os.environ.get("SENDGRID_API_KEY"):
        import requests

        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {os.environ['SENDGRID_API_KEY']}"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": sender},
                "subject": _EMAIL_SUBJECT,
                "content": [{"type": "text/plain", "value": body}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.headers.get("X-Message-Id", "")

    import smtplib
    from email.message import EmailMessage

    host = os.environ["RECOVERY_SMTP_HOST"]
    port = int(os.environ.get("RECOVERY_SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["From"] = os.environ["RECOVERY_EMAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = _EMAIL_SUBJECT
    msg.set_content(body)
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        smtp = smtplib.SMTP(host, port, timeout=15)
        smtp.starttls()
    try:
        user, password = os.environ.get("RECOVERY_SMTP_USER"), os.environ.get("RECOVERY_SMTP_PASS")
        if user and password:
            smtp.login(user, password)
        return smtp.send_message(msg) or ""
    finally:
        smtp.quit()


def _bare_address(value: str) -> str:
    """'Acme Recovery <ops@acme.in>' → 'ops@acme.in'; bare addresses pass through."""
    m = re.search(r"<([^>]+)>", value)
    return (m.group(1) if m else value).strip()


def _meta_send(to: str | None, body: str) -> str:
    """Meta WhatsApp Cloud API send; returns the provider message id.

    With ``WHATSAPP_TEMPLATE_NAME`` set the notice rides in the template's
    body variable — the only path Meta accepts for business-initiated
    WhatsApp to Indian numbers. Without it the send is freeform, which works
    inside a 24h session window and for non-India recipients.
    """
    import requests  # lazy — keeps the module import free of network deps

    if not to:
        raise ValueError("normalized phone is empty")
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {os.environ['WHATSAPP_ACCESS_TOKEN']}"}
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.replace("whatsapp:", ""),
    }
    tpl = os.environ.get("WHATSAPP_TEMPLATE_NAME")
    if tpl:
        payload["type"] = "template"
        payload["template"] = {
            "name": tpl,
            "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANG", "en")},
            "components": [{"type": "body",
                            "parameters": [{"type": "text", "text": body}]}],
        }
    else:
        payload["type"] = "text"
        payload["text"] = {"preview_url": False, "body": body}
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    messages = resp.json().get("messages") or []
    return messages[0].get("id", "") if messages else ""


def _twilio_send(to: str | None, body: str) -> str:
    """Real Twilio WhatsApp send; returns the provider message SID.

    With ``TWILIO_CONTENT_SID`` set the message is sent through the Content
    API with the rendered notice in variable ``{{1}}`` — the only path
    Twilio accepts for business-initiated WhatsApp to Indian numbers. The
    plain-body fallback covers sandboxes and non-India senders.
    """
    if not to:
        raise ValueError("normalized phone is empty")
    client = _twilio_client()
    kwargs: dict[str, Any] = {"to": to, "from_": os.environ["TWILIO_WHATSAPP_FROM"]}
    content_sid = os.environ.get("TWILIO_CONTENT_SID")
    if content_sid:
        kwargs["content_sid"] = content_sid
        kwargs["content_variables"] = json.dumps({"1": body})
    else:
        kwargs["body"] = body
    msg = client.messages.create(**kwargs)
    return getattr(msg, "sid", "")


def _twilio_client() -> Any:
    """Lazy Twilio REST client (kept injectable for tests)."""
    from twilio.rest import Client

    return Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
