#!/usr/bin/env python3
"""One-off diagnostic: inspect the raw construct of recent WhatsApp sends."""

import os

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

for m in c.messages.list(limit=6):
    print(f"{m.sid}  {m.direction:>9}  {m.status:>10}")
    print(f"  from={m.from_}  to={m.to}")
    body = (m.body or "")[:90]
    print(f"  body={body!r}")
    for attr in ("content_sid", "content_variables", "messaging_service_sid",
                 "error_code", "error_message", "num_media", "num_segments"):
        v = getattr(m, attr, "<n/a>")
        if v not in (None, "", "<n/a>", 0):
            print(f"  {attr}={v!r}")
    print()
