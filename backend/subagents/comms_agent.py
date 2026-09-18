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

    Accepts '+919876543210', '919876543210' or bare digits; None when the
    register has no usable number.
    """
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    return f"whatsapp:+{digits}" if digits else None


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

    if not phone:
        result["detail"] = "no vendor phone on file"
        db.record_dispatch(period, invoice_no, supplier, phone,
                           result["mode"], message, error=result["detail"])
        return result

    if result["mode"] == "simulated":
        result["ok"] = True
        result["detail"] = "simulated dispatch (Twilio keys not configured)"
        db.record_dispatch(period, invoice_no, supplier, phone,
                           "simulated", message)
        return result

    try:
        sid = _twilio_send(normalize_phone(phone), message)
    except Exception as exc:  # noqa: BLE001 — provider errors are audit rows
        result["detail"] = f"{type(exc).__name__}: {exc}"
        db.record_dispatch(period, invoice_no, supplier, phone,
                           "twilio", message, error=result["detail"])
        return result

    result["ok"] = True
    result["message_id"] = sid
    result["detail"] = "sent via Twilio WhatsApp API"
    db.record_dispatch(period, invoice_no, supplier, phone,
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
