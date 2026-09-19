#!/usr/bin/env python3
"""One-off diagnostic: what can this Twilio account actually send?"""

import os

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

print("== Content templates ==")
try:
    tpls = list(c.content.v1.content_and_approvals.list())
    print(f"{len(tpls)} templates:")
    for t in tpls[:20]:
        print(f"  {t.sid}  lang={getattr(t, 'language', '?')}  name={t.friendly_name!r}")
except Exception as e:
    print("list failed:", type(e).__name__, str(e)[:200])

print()
print("== WhatsApp-enabled senders ==")
try:
    for p in c.incoming_phone_numbers.list():
        print(f"  number: {p.phone_number}  capabilities={p.capabilities}")
except Exception as e:
    print("sender list failed:", type(e).__name__, str(e)[:150])

print()
print("== Recent messages (last 5) ==")
try:
    for m in c.messages.list(limit=5):
        print(f"  {m.sid} {m.status:>10} dir={m.direction} from={m.from_} to={m.to}")
        if m.error_message:
            print(f"      error: {m.error_message}")
except Exception as e:
    print("message list failed:", type(e).__name__, str(e)[:150])
