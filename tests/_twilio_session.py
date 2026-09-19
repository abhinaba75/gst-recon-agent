#!/usr/bin/env python3
"""One-off diagnostic: how stale is the WhatsApp 24h session window?

Trial accounts cannot use the Content API, so freeform sends only work inside
24 hours of the recipient's last inbound message to the sandbox. This lists
recent messages with ages so we know whether a business-initiated freeform
send is currently possible and when it expires.

Run:  .venv/bin/python tests/_twilio_session.py
"""

import os
from datetime import datetime, timezone

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
now = datetime.now(timezone.utc)

last_inbound = None
print(f"now: {now:%Y-%m-%d %H:%M} UTC\n")
for m in c.messages.list(limit=15):
    age_h = (now - m.date_created).total_seconds() / 3600 if m.date_created else None
    age = f"{age_h:5.1f}h ago" if age_h is not None else "      ?"
    print(f"{m.date_created:%m-%d %H:%M}  {m.direction:>9}  {m.status:>10}  {age}  {m.sid[:16]}")
    if m.error_message:
        print(f"    error: {m.error_message[:140]}")
    if m.direction == "inbound" and last_inbound is None:
        last_inbound = m.date_created

print()
if last_inbound:
    age = (now - last_inbound).total_seconds() / 3600
    left = 24 - age
    if left > 0:
        print(f"SESSION OPEN: last inbound {age:.1f}h ago; freeform window for "
              f"{left:.1f}h more")
    else:
        print(f"SESSION CLOSED: last inbound {age:.1f}h ago (>24h). A business-"
              f"initiated freeform send will be rejected (63016); a new inbound "
              f"message to the sandbox reopens it for 24h.")
else:
    print("no inbound messages found")
