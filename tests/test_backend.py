#!/usr/bin/env python3
"""Test suite for the backend layer: DynamoDB persistence + A2A comms agent.

Run directly (no pytest needed):  .venv/bin/python tests/test_backend.py

All external clients are stubbed or injected, so the suite is free and
deterministic; the live DynamoDB path was verified against the deployed
recon-agent-results-demo table separately.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json  # noqa: E402
from datetime import datetime  # noqa: E402

from backend.db import results as db  # noqa: E402
from backend.db import uploads as up  # noqa: E402
from backend.parser import gstr2b  # noqa: E402
from backend.subagents import comms_agent as ca  # noqa: E402


@dataclass
class _M:
    """Minimal Match stand-in with the attributes persist_run reads."""
    register_no: str
    portal_no: str
    supplier_name: str
    supplier_gstin: str
    tax: float
    status: str
    ai_conf: int = 80
    reason: str = "unit-test row"


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    matches = [
        _M("INV/24-25/081", "INV-081", "Acme Corporation Pvt Ltd",
           "27AABCA1234F1Z5", 18_000.0, "ai", 82, "serial evidence"),
        _M("INV/24-25/075", "INV/24-25/075", "Sunrise Polymers Pvt Ltd",
           "27AAECS4821K1ZP", 15_210.0, "exact", 0, "identical"),
    ]

    print("== Persistence guards (no table configured) ==")
    saved = os.environ.pop("RECON_RESULTS_TABLE", None)
    try:
        check("persist_run → None without a table",
              db.persist_run("August 2026", 2, 2, matches, {"total": 1}) is None)
        check("record_dispatch → False without a table",
              db.record_dispatch("August 2026", "X", "S", None, "simulated", "m") is False)
        check("recent_runs → [] without a table", db.recent_runs("August 2026") == [])
    finally:
        if saved:
            os.environ["RECON_RESULTS_TABLE"] = saved

    print("== Persistence with a stubbed DynamoDB client ==")
    captured: dict = {}

    class _StubDB:
        def put_item(self, TableName, Item):
            captured["table"] = TableName
            captured["items"] = captured.get("items", []) + [Item]
            return {}

        def query(self, **kwargs):
            captured["query"] = kwargs
            return {"Items": [captured["items"][-1]]}

    orig_client = db._client
    db._client = lambda: _StubDB()
    os.environ["RECON_RESULTS_TABLE"] = "recon-agent-results-demo"
    try:
        run_id = db.persist_run("August 2026", 2, 2, matches,
                                {"total": 33_210.0, "exact": 15_210.0,
                                 "ai": 18_000.0, "risk": 0.0})
        check("persist_run returns a run id", bool(run_id), str(run_id))
        item = captured["items"][-1]
        check("item keyed as run#<period>", item["pk"]["S"] == "run#August 2026")
        check("totals stored", item["rescued_itc"]["N"] == "18000.00"
              and item["reconciled_itc"]["N"] == "15210.00")
        check("full ledger embedded as JSON", '"status": "ai"' in item["results"]["S"]
              or '"status":"ai"' in item["results"]["S"])
        runs = db.recent_runs("August 2026")
        check("recent_runs queries newest-first shape", runs and runs[0]["run_id"] == run_id,
              str(runs))

        db.persist_run("August 2026", 2, 2, matches,
                       {"total": 33_210.0}, degraded=True)
        healthy_item, degraded_item = captured["items"][-2], captured["items"][-1]
        check("healthy run stored degraded=False", healthy_item["degraded"]["BOOL"] is False)
        check("degraded run stored degraded=True", degraded_item["degraded"]["BOOL"] is True)
        check("recent_runs surfaces the degraded flag",
              db.recent_runs("August 2026")[0]["degraded"] is True)

        ok = db.record_dispatch("August 2026", "INV/24-25/088", "Vertex Industrial",
                                "+919820177890", "simulated", "Dear Vertex…")
        check("record_dispatch writes an audit row", ok and captured["items"][-1]["pk"]["S"]
              == "dispatch#August 2026")
    finally:
        db._client = orig_client

    print("== Comms agent: phone normalisation ==")
    check("+91 form → whatsapp:+91…",
          ca.normalize_phone("+919876543210") == "whatsapp:+919876543210")
    check("bare digits → whatsapp:+…",
          ca.normalize_phone("919820177890") == "whatsapp:+919820177890")
    check("empty → None", ca.normalize_phone("") is None
          and ca.normalize_phone(None) is None)
    check("junk digits rejected, not mangled into whatsapp: form",
          ca.normalize_phone("12345") is None and ca.normalize_phone("999") is None
          and ca.normalize_phone("call 1800 GET LOST") is None)
    check("10-digit Indian local gains the 91 prefix",
          ca.normalize_phone("9820177890") == "whatsapp:+919820177890")
    check("trunk-prefixed '091 …' form → E.164 without the leading zero",
          ca.normalize_phone("091 9820177890") == "whatsapp:+919820177890")
    check("numbers that would start with 0 are rejected (E.164 never does)",
          ca.normalize_phone("09820177890") is None)

    print("== Comms agent: simulated mode (no Twilio keys) ==")
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"):
        os.environ.pop(k, None)
    dispatches: list[tuple] = []

    def _capture_dispatch(*a, **k):
        dispatches.append((a, k))
        return True

    orig_record = ca.db.record_dispatch
    ca.db.record_dispatch = _capture_dispatch
    try:
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-1",
                                    supplier="Vendor", phone="+919820177890",
                                    message="Hello")
        check("simulated dispatch ok", r["ok"] is True and r["mode"] == "simulated",
              str(r))
        check("simulated dispatch recorded in audit trail", len(dispatches) == 1)
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-2",
                                    supplier="Vendor", phone=None, message="Hello")
        check("missing phone → ok=False with reason",
              r["ok"] is False and "phone" in r["detail"], str(r))
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-4",
                                    supplier="Vendor", phone="12345", message="Hello")
        check("junk phone rejected in simulated mode too (mode parity)",
              r["ok"] is False and "E.164" in r["detail"], str(r))
        check("junk-phone attempt audited as an error row, not a success",
              dispatches and dispatches[-1][1].get("error"),
              str(dispatches[-1][1] if dispatches else None))
    finally:
        ca.db.record_dispatch = orig_record

    print("== Comms agent: twilio mode via injected client ==")
    sids: list[dict] = []

    class _Msg:
        sid = "SM999"

    class _Msgs:
        def create(self, **kwargs):
            sids.append(kwargs)
            return _Msg()

    class _Tw:
        messages = _Msgs()

    os.environ["TWILIO_ACCOUNT_SID"] = "ACxxxx"
    os.environ["TWILIO_AUTH_TOKEN"] = "tok"
    os.environ["TWILIO_WHATSAPP_FROM"] = "whatsapp:+14155238886"
    orig_twilio = ca._twilio_client
    ca._twilio_client = lambda: _Tw()
    ca.db.record_dispatch = _capture_dispatch
    try:
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-3",
                                    supplier="Vendor", phone="+919820177890",
                                    message="Hello")
        check("twilio mode sends with whatsapp:+ form",
              r["ok"] is True and r["mode"] == "twilio"
              and sids[0]["to"] == "whatsapp:+919820177890", str(r))
        check("provider sid recorded", r["message_id"] == "SM999")
        check("twilio dispatch recorded with sid",
              dispatches[-1][1].get("provider_message_id") == "SM999")
    finally:
        ca._twilio_client = orig_twilio
        ca.db.record_dispatch = orig_record
        for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"):
            os.environ.pop(k, None)

    print("== Comms agent: meta mode via stubbed Graph API ==")
    # Meta (WhatsApp Cloud API) takes precedence over Twilio when both are set.
    os.environ["WHATSAPP_ACCESS_TOKEN"] = "eaag-token"
    os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "1234567890"
    os.environ["TWILIO_ACCOUNT_SID"] = "ACdup"
    os.environ["TWILIO_AUTH_TOKEN"] = "tok"
    os.environ["TWILIO_WHATSAPP_FROM"] = "whatsapp:+14155238886"
    check("meta takes precedence when both providers are configured",
          ca.mode() == "meta", ca.mode())
    os.environ.pop("TWILIO_ACCOUNT_SID", None)
    os.environ.pop("TWILIO_AUTH_TOKEN", None)
    os.environ.pop("TWILIO_WHATSAPP_FROM", None)

    posts: list[dict] = []

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"messages": [{"id": "wamid.TEST123"}]}

    def _fake_post(url, headers=None, json=None, timeout=None):
        posts.append({"url": url, "headers": headers, "json": json,
                      "timeout": timeout})
        return _Resp()

    import requests as _requests
    orig_post = _requests.post
    _requests.post = _fake_post
    ca.db.record_dispatch = _capture_dispatch
    try:
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-5",
                                    supplier="Vendor", phone="+919820177890",
                                    message="Hello")
        check("meta mode sends via Graph API",
              r["ok"] is True and r["mode"] == "meta" and posts, str(r))
        check("graph url carries phone number id and a version",
              posts[0]["url"].startswith("https://graph.facebook.com/v")
              and "1234567890/messages" in posts[0]["url"], posts[0]["url"])
        check("bearer token used",
              posts[0]["headers"]["Authorization"] == "Bearer eaag-token")
        p = posts[0]["json"]
        check("freeform payload targets the bare E.164 number",
              p["messaging_product"] == "whatsapp" and p["to"] == "+919820177890"
              and p["type"] == "text" and p["text"]["body"] == "Hello", str(p))
        check("provider wamid recorded", r["message_id"] == "wamid.TEST123")

        os.environ["WHATSAPP_TEMPLATE_NAME"] = "recon_rule88d_recovery"
        posts.clear()
        ca.send_recovery_notice(period="August 2026", invoice_no="X-6",
                                supplier="Vendor", phone="+919820177890",
                                message="Hello 88D")
        p = posts[0]["json"]
        check("template send wraps the notice in the body parameter",
              p["type"] == "template"
              and p["template"]["name"] == "recon_rule88d_recovery"
              and p["template"]["components"][0]["parameters"][0]["text"] == "Hello 88D",
              str(p))
        os.environ.pop("WHATSAPP_TEMPLATE_NAME", None)

        def _boom_post(*a, **k):
            raise RuntimeError("graph api down")

        _requests.post = _boom_post
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-7",
                                    supplier="Vendor", phone="+919820177890",
                                    message="Hello")
        check("meta provider failure → ok=False, audited (never raises)",
              r["ok"] is False and "RuntimeError" in r["detail"]
              and dispatches[-1][1].get("error"), str(r))
    finally:
        _requests.post = orig_post
        ca.db.record_dispatch = orig_record
        for k in ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
                  "WHATSAPP_TEMPLATE_NAME"):
            os.environ.pop(k, None)

    print("== Comms agent: email mode (SendGrid via stubbed HTTP) ==")
    os.environ["SENDGRID_API_KEY"] = "SG.test"
    os.environ["RECOVERY_EMAIL_FROM"] = "Acme Recovery <ops@acme.in>"
    posts.clear()

    class _SgResp:
        status_code = 202
        headers = {"X-Message-Id": "msg-abc123"}

        def raise_for_status(self):
            pass

    def _sg_post(url, headers=None, json=None, timeout=None):
        posts.append({"url": url, "headers": headers, "json": json})
        return _SgResp()

    _requests.post = _sg_post
    ca.db.record_dispatch = _capture_dispatch
    check("email mode active with sendgrid + from", ca.mode() == "email", ca.mode())
    try:
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-8",
                                    supplier="Vendor", phone=None,
                                    email="accounts@vertexindustrial.in",
                                    message="Hello by mail")
        check("email mode delivers via sendgrid",
              r["ok"] is True and r["mode"] == "email" and posts, str(r))
        check("sendgrid request carries key, subject and recipient",
              posts[0]["headers"]["Authorization"] == "Bearer SG.test"
              and posts[0]["json"]["personalizations"][0]["to"] == [{"email": "accounts@vertexindustrial.in"}]
              and posts[0]["json"]["from"]["email"] == "ops@acme.in"
              and posts[0]["json"]["content"][0]["value"] == "Hello by mail",
              str(posts[0]["json"]))
        check("provider message id from X-Message-Id header",
              r["message_id"] == "msg-abc123", str(r))
        check("audit row records email mode",
              dispatches[-1][0][4] == "email" and not dispatches[-1][1].get("error"),
              str(dispatches[-1]))
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-9",
                                    supplier="Vendor", phone=None,
                                    email="not-an-email",
                                    message="Hello by mail")
        check("junk email fails closed", r["ok"] is False and "not valid" in r["detail"], str(r))
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-10",
                                    supplier="Vendor", phone=None, email=None,
                                    message="Hello by mail")
        check("missing email fails closed", r["ok"] is False
              and "no vendor email" in r["detail"], str(r))

        def _sg_boom(*a, **k):
            raise RuntimeError("sendgrid down")

        _requests.post = _sg_boom
        r = ca.send_recovery_notice(period="August 2026", invoice_no="X-11",
                                    supplier="Vendor", phone=None,
                                    email="accounts@vertexindustrial.in",
                                    message="Hello by mail")
        check("sendgrid failure → ok=False, audited (never raises)",
              r["ok"] is False and "RuntimeError" in r["detail"]
              and dispatches[-1][1].get("error"), str(r))
    finally:
        os.environ.pop("SENDGRID_API_KEY", None)
        os.environ.pop("RECOVERY_EMAIL_FROM", None)
        ca.db.record_dispatch = orig_record

    print("== GSTR-2B parser: real GSTN download schema ==")
    fixture = json.loads((ROOT / "fixtures" / "sample_gstr2b.json").read_text())
    frows = gstr2b.parse_gstr2b(fixture)
    check("fixture payload parses to 11 invoices", len(frows) == 11, str(len(frows)))
    check("fixture numerics preserved through the parser",
          frows[0]["inum"] == "INV/24-25/075" and frows[0]["igst"] == 15_210.0)

    # Versioned envelope (b2b_5 with period groups) + string numerics + blanks.
    envelope = {"gstin": "29AAACD5678M1Z2", "fp": "082026",
                "b2b_5": [{"oppattr": "082026",
                           "b2b": [{"ctin": "27AABCA1234F1Z5", "trdnm": "Acme Corp",
                                    "inv": [{"inum": "INV-081", "idt": "15-08-2026",
                                             "itcavl": "Y",
                                             "items": [{"txval": "100000.00", "rt": "18",
                                                        "iamt": "18,000", "camt": "",
                                                        "samt": None}]}]}]}]}
    erows = gstr2b.parse_gstr2b(envelope)
    check("versioned b2b_5 envelope unwrapped to supplier tables",
          len(erows) == 1 and erows[0]["ctin"] == "27AABCA1234F1Z5")
    check("string numerics coerced (including thousands separators)",
          erows[0]["txval"] == 100_000.0 and erows[0]["igst"] == 18_000.0)
    check("absent invoice val rebuilt from components",
          erows[0]["val"] == 118_000.0, str(erows[0]["val"]))

    junk = gstr2b.parse_gstr2b({"b2b": [{"ctin": None, "trdnm": 5,
                                         "inv": [{"inum": None, "val": "junk",
                                                  "items": [{"txval": "NaN",
                                                             "iamt": "x"}]}]}]})
    check("junk payload degrades to zeros, never raises",
          junk[0]["txval"] == 0.0 and junk[0]["val"] == 0.0 and junk[0]["inum"] == "",
          str(junk[0]))
    check("empty payload → empty invoice list", gstr2b.parse_gstr2b({}) == [])

    print("== S3 uploads archive: content-addressed, graceful, least-privilege ==")
    saved_bucket = os.environ.pop("RECON_UPLOADS_BUCKET", None)
    try:
        check("archive_upload → None without a bucket",
              up.archive_upload(b"x", "f.csv") is None)
        check("list_archive → [] without a bucket", up.list_archive() == [])

        puts: list[dict] = []

        class _StubS3:
            def put_object(self, **kwargs):
                puts.append(kwargs)
                return {}

            def list_objects_v2(self, **kwargs):
                return {"Contents": [
                    {"Key": puts[0]["Key"],
                     "LastModified": datetime(2026, 9, 18, 12, 0),
                     "Size": len(puts[0]["Body"])},
                    {"Key": "uploads/2026-08/fake/"},  # folder marker, filtered
                ]}

        orig_s3 = up._client
        up._client = lambda: _StubS3()
        os.environ["RECON_UPLOADS_BUCKET"] = "recon-agent-uploads-demo-204284492326"
        try:
            key1 = up.archive_upload(b"2b-bytes", "gstr2b.json", period="August 2026")
            check("archive_upload stores AES256-encrypted in the configured bucket",
                  bool(key1) and puts[0]["Bucket"] == "recon-agent-uploads-demo-204284492326"
                  and puts[0]["ServerSideEncryption"] == "AES256", str(key1))
            check("key is content-addressed under the period prefix",
                  key1.startswith("uploads/August-2026/") and key1.endswith("/gstr2b.json"))
            key2 = up.archive_upload(b"2b-bytes", "gstr2b.json", period="August 2026")
            check("identical re-upload lands on the same object (idempotent)",
                  key1 == key2 and len(puts) == 2)
            key3 = up.archive_upload(b"corrected", "gstr2b.json", period="August 2026")
            check("corrected file gets a new archive key (original preserved)",
                  key3 != key1)
            listed = up.list_archive()
            check("list_archive returns objects, filters folder markers",
                  len(listed) == 1 and listed[0]["bytes"] == str(len(b"2b-bytes"))
                  and listed[0]["at"] == "2026-09-18 12:00", str(listed))
        finally:
            up._client = orig_s3
    finally:
        if saved_bucket:
            os.environ["RECON_UPLOADS_BUCKET"] = saved_bucket
        else:
            os.environ.pop("RECON_UPLOADS_BUCKET", None)

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
