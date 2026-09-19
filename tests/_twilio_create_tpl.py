#!/usr/bin/env python3
"""One-off: create (or reuse) the WhatsApp content template.

India recipients require template-based business-initiated sends. We wrap the
full rendered Rule 88D message in one variable, so the app's existing message
construction is untouched; production should later adopt structured templates
with per-field variables (noted in comms_agent's docstring).

Run:  .venv/bin/python tests/_twilio_create_tpl.py
Prints the ContentSid to set as ``TWILIO_CONTENT_SID``.
"""

import os

from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

existing = []
try:
    existing = [
        t for t in c.content.v1.content_and_approvals.list()
        if getattr(t, "friendly_name", "") == "recon_rule88d_recovery"
    ]
except Exception as exc:
    # Trial accounts cannot list templates (error 20003) — create blind and
    # surface the friendly-name-collision error if one already exists.
    print(f"listing skipped ({type(exc).__name__}: {str(exc)[:120]})")

if existing:
    tpl = existing[0]
    print(f"template already exists: {tpl.sid} ({tpl.friendly_name!r}, {tpl.language})")
else:
    # twilio 9.x: create() takes a ContentCreateRequest built from this dict
    # shape (types key is the Content API's 'twilio/text').
    class _CreateRequest:
        def __init__(self, payload: dict):
            self.payload = payload

        def to_dict(self):
            return self.payload

    tpl = c.content.v1.contents.create(_CreateRequest({
        "friendly_name": "recon_rule88d_recovery",
        "variables": {"1": "message"},
        "language": "en",
        "types": {"twilio/text": {"body": "GST ITC Recovery Notice: {{1}}"}},
    }))
    print(f"template created: {tpl.sid}")

print("\nSet this in .env.local / your environment:")
print(f"  TWILIO_CONTENT_SID={tpl.sid}")