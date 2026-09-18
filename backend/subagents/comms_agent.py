"""A2A Comms Agent — WhatsApp recovery notices to defaulting suppliers.

Production path is Twilio's WhatsApp API; until ``TWILIO_ACCOUNT_SID`` /
``TWILIO_AUTH_TOKEN`` / ``TWILIO_WHATSAPP_FROM`` are configured the agent
runs in clearly-labelled simulation mode (identical audit trail, no send).
The mode is decided per call, surfaced in the UI, and recorded in the
DynamoDB audit trail either way — a simulated dispatch must never be
mistaken for a delivered message.
"""

from __future__ import annotations

import os
from typing import Any

from backend.db import results as db

_TWILIO_ENV = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")


def mode() -> str:
    """'twilio' when fully configured, otherwise 'simulated'."""
    return "twilio" if all(os.environ.get(k) for k in _TWILIO_ENV) else "simulated"


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


def send_recovery_notice(
    *,
    period: str,
    invoice_no: str,
    supplier: str,
    phone: str | None,
    message: str,
) -> dict[str, Any]:
    """Dispatch one recovery notice; record the attempt in the audit trail.

    Returns ``{"ok": bool, "mode": str, "detail": str, "message_id": str|None}``.
    Never raises: a provider failure is an ``ok=False`` audit record.
    """
    result: dict[str, Any] = {"ok": False, "mode": mode(),
                              "detail": "", "message_id": None}

    # Normalise BEFORE the mode branch, so both paths audit the number they
    # would actually use: simulation must not record ok=True for a phone the
    # live provider would reject.
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

    if result["mode"] == "simulated":
        result["ok"] = True
        result["detail"] = "simulated dispatch (Twilio keys not configured)"
        db.record_dispatch(period, invoice_no, supplier, to,
                           "simulated", message)
        return result

    try:
        sid = _twilio_send(to, message)
    except Exception as exc:  # noqa: BLE001 — provider errors are audit rows
        result["detail"] = f"{type(exc).__name__}: {exc}"
        db.record_dispatch(period, invoice_no, supplier, to,
                           "twilio", message, error=result["detail"])
        return result

    result["ok"] = True
    result["message_id"] = sid
    result["detail"] = "sent via Twilio WhatsApp API"
    db.record_dispatch(period, invoice_no, supplier, to,
                       "twilio", message, provider_message_id=sid)
    return result


def _twilio_send(to: str | None, body: str) -> str:
    """Real Twilio WhatsApp send; returns the provider message SID."""
    if not to:
        raise ValueError("normalized phone is empty")
    client = _twilio_client()
    msg = client.messages.create(
        to=to,
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        body=body,
    )
    return getattr(msg, "sid", "")


def _twilio_client() -> Any:
    """Lazy Twilio REST client (kept injectable for tests)."""
    from twilio.rest import Client

    return Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
