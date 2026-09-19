#!/usr/bin/env python3
"""One-off LIVE Twilio verification — sends a real WhatsApp message.

Run: .venv/bin/python tests/_twilio_live.py
Uses the configured TWILIO_* keys; the message goes to the phone that joined
the sandbox (the only permitted trial recipient).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.subagents import comms_agent as ca  # noqa: E402

mode = ca.mode()
print(f"comms agent mode: {mode}")
assert mode == "twilio", "mode did not flip — keys not picked up?"

# The sandbox-joined recipient from your screenshot.
phone = "+918900511716"
result = ca.send_recovery_notice(
    period="August 2026",
    invoice_no="INV/24-25/088",
    supplier="Vertex Industrial Supplies",
    phone=phone,
    message=(
        "Dear Vertex, Invoice INV/24-25/088 of 82500 is missing from our "
        "GSTR-2B for August 2026. Please file your GSTR-1 before the 11th "
        "to prevent credit blockage under Rule 88D."
    ),
)
print(f"result: ok={result['ok']} mode={result['mode']} id={result['message_id']}")
print(f"detail: {result['detail']}")
assert result["ok"], f"send failed: {result['detail']}"
assert result["mode"] == "twilio" and (result["message_id"] or "").startswith("SM"), \
    "expected a real Twilio message SID"

# Confirm the audit row landed in the real DynamoDB trail. Without AWS
# credentials/table access record_dispatch degrades to False by design —
# report it, don't fail the send verification.
from backend.db import results as db  # noqa: E402
recorded = db.record_dispatch(
    period="August 2026",
    invoice_no="INV/24-25/088",
    supplier="Vertex Industrial Supplies",
    phone=phone,
    mode="twilio",
    message="live verification send",
    provider_message_id=result["message_id"],
)
print(f"audit row recorded: {recorded}"
      + ("" if recorded else "  (DynamoDB not reachable from this environment — "
                           "expected when the table/creds are not wired yet)"))

print(f"LIVE TWILIO SEND VERIFIED — sid {result['message_id']}")
