#!/usr/bin/env python3
"""One-off: minimal freeform WhatsApp send inside the 24h session window.

The Tryout-UI sends at 18:42-18:43 UTC succeeded as body-only to the Indian
recipient; our Rule-88D freeform failed with "ContentSid Required" ~55 minutes
after the last inbound. This isolates whether ANY API freeform works inside
the window on this Trial account, or whether only Twilio-internal sends do.
"""

import os

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

try:
    m = c.messages.create(
        to="whatsapp:+918900511716",
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        body="Recon-Agent probe: freeform send inside the session window.",
    )
    print(f"SENT OK: {m.sid} status={m.status}")
except Exception as e:
    print("send failed:", type(e).__name__, str(e)[:300])