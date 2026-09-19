#!/usr/bin/env python3
"""API surface tests for the React frontend's backend (api/main.py).

Run directly (no pytest, no server):  .venv/bin/python tests/test_api.py

The endpoints are called as functions, so nothing binds a port and no notice is
ever sent — the comms agent is stubbed and its kwargs are asserted.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["RECON_RESULTS_TABLE"] = ""  # never touch the deployed audit table

# Accounts go to a throwaway file. This suite asserts that the demo pair still
# signs in on an unconfigured build, which is only true while the account store
# is empty — so it must never read the one a developer has been using, and it
# must never write to the project root.
os.environ["RECON_USERS_FILE"] = str(
    Path(tempfile.mkdtemp(prefix="recon-api-")) / "users.json"
)
os.environ["RECON_USERS_TABLE"] = ""

from api import main as api  # noqa: E402
from backend.subagents import comms_agent as ca  # noqa: E402


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print("== Health ==")
    h = api.health()
    check("health ok", h["ok"] is True, str(h))
    check("provider is a real ladder mode",
          h["provider"] in {"meta", "email", "twilio", "simulated"}, str(h["provider"]))
    check("snapshot exported and discoverable", h["snapshot_present"] is True, str(h))

    print("== Snapshot contract (the numbers the page renders) ==")
    snap = api.snapshot()
    totals = snap["totals"]
    check("totals match the engine exactly",
          totals["total"] == 107971.0 and totals["exact"] == 57210.0
          and totals["rescued"] == 30690.0 and totals["risk"] == 20071.0
          and totals["write_off"] == 50761.0, str(totals))
    check("counts match the fixtures",
          snap["counts"] == {"books": 12, "portal": 11, "excel_unmatched": 6,
                             "rescued": 3, "missing": 3, "portal_only": 2},
          str(snap["counts"]))
    check("every ledger row carries its evidence",
          all(m["reason"] for m in snap["matches"] if m["status"] == "ai"))
    check("recovery rows carry a contact for the dialog",
          all(m["phone"] or m["email"] for m in snap["matches"] if m["status"] == "missing"))

    print("== Dispatch: request mapping and pass-through ==")
    captured: dict = {}

    def _stub(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "mode": "sendgrid", "detail": "sent via SendGrid",
                "message_id": "msg-1"}

    orig = ca.send_recovery_notice
    ca.send_recovery_notice = _stub
    try:
        res = api.dispatch(api.DispatchRequest(
            period="August 2026", invoiceNo="INV/24-25/088",
            supplier="Vertex Industrial Supplies", message="Hello",
            phone="+919820177890", email="accounts@vertexindustrial.in",
        ))
    finally:
        ca.send_recovery_notice = orig
    check("camelCase invoiceNo maps to the agent's invoice_no",
          captured.get("invoice_no") == "INV/24-25/088", str(captured))
    check("phone and email both reach the agent",
          captured.get("phone") == "+919820177890"
          and captured.get("email") == "accounts@vertexindustrial.in", str(captured))
    check("response mirrors the agent's result",
          res == {"ok": True, "mode": "sendgrid", "detail": "sent via SendGrid",
                  "message_id": "msg-1"}, str(res))

    print("== Dispatch: failure is reported, never dressed up ==")

    def _fail(**kwargs):
        return {"ok": False, "mode": "meta",
                "detail": "TwilioRestException: 400 ContentSid Required",
                "message_id": None}

    ca.send_recovery_notice = _fail
    try:
        res = api.dispatch(api.DispatchRequest(
            period="August 2026", invoiceNo="X-1", supplier="Vendor",
            message="Hello", phone=None, email="a@b.in",
        ))
    finally:
        ca.send_recovery_notice = orig
    check("provider failure survives the HTTP boundary as ok=false",
          res["ok"] is False and "ContentSid" in res["detail"], str(res))

    print("== Login: server-verified sessions ==")
    from backend import session as sessions  # noqa: E402

    for k in ("RECON_UI_EMAIL", "RECON_UI_PASSWORD"):
        os.environ.pop(k, None)
    check("unconfigured build runs in demo mode",
          api.health()["login_mode"] == "demo" and sessions.mode() == "demo")

    from backend import users  # noqa: E402

    check("the suite reads its own throwaway account store, not a developer's",
          Path(users.file_path()).parent.name.startswith("recon-api-"),
          str(users.file_path()))

    bad = api.login(api.LoginRequest(email="demo@recon-agent.in", password="nope"))
    check("wrong password refused", bad["ok"] is False and "token" not in bad, str(bad))
    unknown = api.login(api.LoginRequest(email="someone@else.in", password="demo-88d"))
    check("wrong email refused with the same message (no user enumeration)",
          unknown["ok"] is False and unknown["detail"] == bad["detail"], str(unknown))
    blank = api.login(api.LoginRequest(email="", password=""))
    check("blank credentials refused", blank["ok"] is False, str(blank))

    good = api.login(api.LoginRequest(email="demo@recon-agent.in", password="demo-88d"))
    check("demo credentials accepted, mode named",
          good["ok"] is True and good["mode"] == "demo" and bool(good["token"]), str(good)[:120])
    check("the token is opaque, not the password",
          "demo-88d" not in good["token"], good["token"][:12] + "…")
    token = good["token"]

    live = api.session_state(api.TokenRequest(token=token))
    check("a live token resolves to its user",
          live["ok"] is True and live["user"]["email"] == "demo@recon-agent.in", str(live))
    check("a junk token resolves to nobody",
          api.session_state(api.TokenRequest(token="not-a-token"))["ok"] is False)
    check("logout drops the session",
          api.logout(api.TokenRequest(token=token))["dropped"] is True
          and api.session_state(api.TokenRequest(token=token))["ok"] is False)
    check("logging out twice is still logged out",
          api.logout(api.TokenRequest(token=token))["dropped"] is False)

    os.environ["RECON_UI_EMAIL"] = "ops@acme.in"
    os.environ["RECON_UI_PASSWORD"] = "correct horse"
    try:
        check("configured credentials switch the mode",
              sessions.mode() == "configured" and api.health()["login_mode"] == "configured")
        check("the demo pair stops working once real credentials exist",
              api.login(api.LoginRequest(email="demo@recon-agent.in",
                                        password="demo-88d"))["ok"] is False)
        configured = api.login(api.LoginRequest(email="ops@acme.in",
                                                password="correct horse"))
        check("the configured account works",
              configured["ok"] is True and configured["mode"] == "configured",
              str(configured)[:120])
    finally:
        os.environ.pop("RECON_UI_EMAIL", None)
        os.environ.pop("RECON_UI_PASSWORD", None)

    print("== Assistant: guide answers, grounded in the snapshot ==")
    from backend import assistant  # noqa: E402

    check("no model configured by default",
          assistant.configured_model() is None, str(assistant.configured_model()))
    check("every guide entry is usable",
          bool(assistant.guide_entries()) and all(
              e.get("keywords") and e.get("en") for e in assistant.guide_entries()))

    r = api.ask(api.AssistantRequest(question="What is Rule 88D?", lang="en"))
    check("rule 88D answered from the guide, source named",
          r["ok"] and r["source"] == "guide" and "88D" in r["answer"], str(r)[:160])
    check("assistant reports the guide, never claims a model",
          "model" not in r)

    r_hi = api.ask(api.AssistantRequest(question="Rule 88D kya hai", lang="hi"))
    check("Hindi question answered in Hindi",
          r_hi["source"] == "guide" and any("\u0900" <= ch <= "\u097f"
                                            for ch in r_hi["answer"]), str(r_hi)[:120])

    r_fig = api.ask(api.AssistantRequest(question="how much was recovered", lang="en"))
    check("{{placeholders}} render as real figures, not braces",
          "{{" not in r_fig["answer"] and "\u20b9" in r_fig["answer"],
          str(r_fig)[:160])
    check("the rendered figure is the engine's rescued total",
          "30,690" in r_fig["answer"], str(r_fig)[:200])

    r_none = api.ask(api.AssistantRequest(question="what is the weather", lang="en"))
    check("unknown question is admitted, not invented",
          r_none["ok"] is False and r_none["source"] == "none", str(r_none)[:120])
    check("empty question does not raise",
          api.ask(api.AssistantRequest(question="   ", lang="en"))["ok"] is False)

    print("== Assistant: a configured model that fails degrades, honestly ==")
    os.environ["RECON_ASSISTANT_MODEL"] = "amazon.nova-lite-v1:0"
    orig_client = assistant._client

    def _boom_client():
        raise RuntimeError("bedrock unreachable")

    assistant._client = None
    orig_boto = assistant._get_client
    try:
        assistant._get_client = _boom_client  # type: ignore[assignment]
        r = api.ask(api.AssistantRequest(question="What is Rule 88D?", lang="en"))
        check("model failure still answers from the guide",
              r["ok"] and r["source"] == "guide", str(r)[:160])
        check("the model error is reported, not hidden",
              "RuntimeError" in r.get("model_error", ""), str(r.get("model_error")))
        check("configured model is visible on health",
              api.health()["assistant_model"] == "amazon.nova-lite-v1:0")
    finally:
        assistant._get_client = orig_boto  # type: ignore[assignment]
        assistant._client = orig_client
        os.environ.pop("RECON_ASSISTANT_MODEL", None)

    print("== Runs: absent audit table degrades to an empty list ==")
    check("runs returns [] without a table", api.runs()["runs"] == [])

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
