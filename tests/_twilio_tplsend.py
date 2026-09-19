#!/usr/bin/env python3
"""One-off: can this Trial account SEND with a ContentSid (vs create templates)?

Twilio's docs use a public sample template SID in their WhatsApp quickstart
("HXb5b5b62575e6e4ff6219e68c9c595ba8ba"-family). If fetch + send work, the
comms agent's template path is verified on Trial and the only remaining step
is creating the Rule 88D template (console or paid upgrade).
"""

import os

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

SAMPLE_SID = "HXb5b62575e6e4ff6219e68c9c595ba8ba"  # Twilio docs sample template

print("== fetch sample template ==")
try:
    tpl = c.content.v1.contents(SAMPLE_SID).fetch()
    print(f"fetched: {tpl.sid}")
    types = getattr(tpl, "types", None)
    print(f"types: {types}")
    v = getattr(tpl, "variables", None)
    print(f"variables: {v}")
except Exception as e:
    print("fetch failed:", type(e).__name__, str(e)[:300])

print("\n== send with content_sid (session still open) ==")
try:
    m = c.messages.create(
        to="whatsapp:+918900511716",
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        content_sid=SAMPLE_SID,
        content_variables='{"1": "Recon-Agent live test"}',
    )
    print(f"sent: {m.sid} status={m.status}")
except Exception as e:
    print("send failed:", type(e).__name__, str(e)[:300])
