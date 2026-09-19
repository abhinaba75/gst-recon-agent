#!/usr/bin/env python3
"""One-off LIVE email verification — delivers a real recovery notice.

Run:  .venv/bin/python tests/_email_live.py

Requires SENDGRID_API_KEY + RECOVERY_EMAIL_FROM (or RECOVERY_SMTP_* creds)
in the environment. Sends to RECOVERY_TEST_EMAIL if set, otherwise the
RECOVERY_EMAIL_FROM address itself (a verified sender can always receive).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.subagents import comms_agent as ca  # noqa: E402

mode = ca.mode()
print(f"comms agent mode: {mode}")
assert mode == "email", "email mode not active — need SENDGRID_API_KEY (or SMTP) + RECOVERY_EMAIL_FROM"

recipient = os.environ.get("RECOVERY_TEST_EMAIL") or ca._bare_address(
    os.environ["RECOVERY_EMAIL_FROM"])
print(f"sending to: {recipient}")

result = ca.send_recovery_notice(
    period="August 2026",
    invoice_no="INV/24-25/088",
    supplier="Vertex Industrial Supplies",
    phone=None,
    email=recipient,
    message=(
        "Dear Vertex, Invoice INV/24-25/088 of ₹82,500 is missing from our "
        "GSTR-2B for August 2026. Please file your GSTR-1 before the 11th "
        "to prevent credit blockage under Rule 88D."
    ),
)
print(f"result: ok={result['ok']} mode={result['mode']} id={result['message_id']}")
print(f"detail: {result['detail']}")
assert result["ok"], f"send failed: {result['detail']}"
assert result["mode"] == "email" and result["message_id"], \
    "expected a provider message id"

print(f"LIVE EMAIL SEND VERIFIED — id {result['message_id']}")
