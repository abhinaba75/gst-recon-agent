#!/usr/bin/env python3
"""One-off probe: does this Trial account deliver plain SMS to an Indian number?

WhatsApp is template-locked for India on Trial, but SMS has no Meta template
rule. Trial accounts can only SMS verified numbers, and India additionally
requires DLT registration on some routes — this single send (1 of the 100
free units) tells us whether an SMS recovery channel is viable at zero cost.
"""

import os

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

try:
    m = c.messages.create(
        to="+918900511716",
        from_="+17372508034",  # the trial number behind the WhatsApp sender
        body=("Recon-Agent probe: Rule 88D recovery notices can also travel "
              "by SMS. This is a one-off channel test."),
    )
    print(f"queued: {m.sid} status={m.status}")
except Exception as e:
    print("sms send failed:", type(e).__name__, str(e)[:300])
