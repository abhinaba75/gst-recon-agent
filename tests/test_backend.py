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

from backend.db import results as db  # noqa: E402
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

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
