#!/usr/bin/env python3
"""Deterministic validation of Recon-Agent fixtures and both pipelines.

Run directly (no pytest needed):  python tests/validate_fixtures.py

Persistence is stubbed for the whole suite: runs are counted and their
``degraded`` flag asserted, but nothing ever reaches the deployed DynamoDB.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "frontend"))

import app  # noqa: E402  (Streamlit module import — no server started)

# Tests must never write to the deployed DynamoDB audit trail. The stub below
# also counts persist_run calls so the degraded-persistence contract can be
# asserted without touching real AWS.
os.environ["RECON_RESULTS_TABLE"] = ""
_persist_calls: list[bool] = []


def _stub_persist_run(books, portal, matches, degraded=False):
    _persist_calls.append(degraded)
    return None


app._persist_run = _stub_persist_run


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print("== Fixture schema ==")
    books = pd.read_excel(app.REGISTER_XLSX)
    payload = json.loads(app.GSTR2B_JSON.read_text(encoding="utf-8"))
    expected_cols = [
        "invoice_no", "supplier_name", "supplier_gstin", "invoice_date",
        "taxable_value", "igst", "cgst", "sgst", "total_tax", "total_amount",
        "vendor_phone",
    ]
    check("register columns", list(books.columns) == expected_cols, str(list(books.columns)))
    check("register rows == 12", len(books) == 12, f"{len(books)}")
    check("payload keys", all(k in payload for k in ("gstin", "fp", "b2b")))
    portal = app._parse_portal(payload)
    check("portal invoices == 11", len(portal) == 11, f"{len(portal)}")
    check("fp is 082026", payload["fp"] == "082026", payload["fp"])

    print("== Excel VLOOKUP pipeline (premature write-off) ==")
    excel = app.run_excel_vlookup(books, portal)
    unmatched = [m for m in excel if m.status == "unmatched"]
    check("vlookup exact matches == 6", sum(m.status == "exact" for m in excel) == 6)
    check("vlookup #N/A count == 6", len(unmatched) == 6, f"{len(unmatched)}")
    check("vlookup write-off == 50,761", sum(m.tax for m in unmatched) == 50_761,
          f"₹{sum(m.tax for m in unmatched):,.0f}")

    print("== Recon-Agent pipeline (semantic rescue) ==")
    matches = app.run_recon_pipeline(books, portal)
    ai = [m for m in matches if m.status == "ai"]
    check("ai rescued == 3", len(ai) == 3, str([m.register_no for m in ai]))
    check("ai rescued ITC == 30,690", sum(m.tax for m in ai) == 30_690,
          f"₹{sum(m.tax for m in ai):,.0f}")
    missing = [m for m in matches if m.status == "missing"]
    check("defaulting suppliers == 3", len(missing) == 3)
    check("risk ITC == 20,071", sum(m.tax for m in missing) == 20_071,
          f"₹{sum(m.tax for m in missing):,.0f}")
    check("portal-only == 2", sum(m.status == "portal_only" for m in matches) == 2)
    check("every defaulting supplier has GSTIN 27-prefixed",
          all(m.supplier_gstin.startswith("27") for m in missing))

    print("== Conservation (each portal row claimed at most once) ==")
    claimed = [m.portal_no for m in matches if m.status in ("exact", "ai")]
    check("no portal invoice double-claimed", len(set(claimed)) == len(claimed),
          str(claimed))

    # Two books lines sharing GSTIN + tax (duplicate entry / split billing)
    # must resolve to a single 2B claim — the loser stays 'missing'.
    dup = pd.concat([books, books.iloc[[0]]], ignore_index=True)  # Sunrise, 2B: INV/24-25/075
    dup_matches = app.run_recon_pipeline(dup, portal)
    dup_claims = [m for m in dup_matches
                  if m.status in ("exact", "ai") and m.portal_no == "INV/24-25/075"]
    check("duplicate books line cannot double-claim one 2B entry",
          len(dup_claims) == 1, f"{len(dup_claims)} claims on INV/24-25/075")
    dup_remainder = [m for m in dup_matches
                     if m.register_no == "INV/24-25/075" and m.status == "missing"]
    check("surplus duplicate line stays missing", len(dup_remainder) == 1,
          str([m.status for m in dup_remainder]))

    print("== Corroboration fails closed ==")
    blank = books.copy()
    blank.loc[6, "supplier_gstin"] = ""  # Acme row, group 2
    blank_matches = app.run_recon_pipeline(blank, portal)
    acme_row = next(m for m in blank_matches if "081" in m.register_no)
    check("books row without GSTIN is never corroborated",
          acme_row.status == "missing", acme_row.status)
    blank_portal = copy.deepcopy(payload)
    for sup in blank_portal["b2b"]:
        if sup["ctin"] == "27AABCA1234F1Z5":
            sup["ctin"] = ""  # 2B row missing the ctin — blank == blank is not identity
    bp_matches = app.run_recon_pipeline(books, app._parse_portal(blank_portal))
    bp_acme = next(m for m in bp_matches if "081" in m.register_no)
    check("two blank GSTINs never corroborate (fail-closed)",
          bp_acme.status == "missing", bp_acme.status)

    print("== Bedrock degradation (unreachable → fallback, never crashes) ==")
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("network unreachable")

    orig_matcher = app._bedrock_semantic_matcher
    app._bedrock_semantic_matcher = _boom
    try:
        degraded = app.run_recon_pipeline(books, portal, use_bedrock=True)
    finally:
        app._bedrock_semantic_matcher = orig_matcher
    check("matcher consulted exactly once", calls["n"] == 1, f"{calls['n']} calls")
    check("degraded run == fallback classification",
          sum(m.status == "ai" for m in degraded) == 3
          and sum(m.tax for m in degraded if m.status == "ai") == 30_690)

    print("== Degraded runs are never cached (a rerun retries Bedrock) ==")
    app._bedrock_semantic_matcher = _boom
    try:
        again = app.run_recon_pipeline(books, portal, use_bedrock=True)
    finally:
        app._bedrock_semantic_matcher = orig_matcher
    check("degraded result not cached — matcher consulted again",
          calls["n"] == 2, f"{calls['n']} calls after rerun")
    check("retry returns consistent fallback classification",
          [m.register_no for m in again] == [m.register_no for m in degraded])

    print("== Degraded runs are persisted, flagged, not authoritative ==")
    # The two immediately preceding runs were the degraded pair.
    check("degraded runs persisted, each flagged",
          len(_persist_calls) >= 2 and _persist_calls[-2:] == [True, True],
          str(_persist_calls))
    b_healthy = books.copy()
    b_healthy.loc[0, "vendor_phone"] = "+919999999999"  # fresh digest, same taxonomy
    app.run_recon_pipeline(b_healthy, portal)  # healthy local run
    check("healthy run persisted unflagged",
          _persist_calls[-1] is False, str(_persist_calls))

    print("== Cache digest is portal-sensitive (corrected 2B is not stale) ==")
    # Same invoice numbers, corrected amounts: the cached classification must
    # not survive — tax/risk figures would be wrong until the session died.
    payload2 = copy.deepcopy(payload)
    for sup in payload2["b2b"]:
        for inv in sup["inv"]:
            if inv["inum"] == "INV-081":
                for it in inv["items"]:
                    it["iamt"] += 5000.0
    corrected = app.run_recon_pipeline(books, app._parse_portal(payload2))
    acme2 = next(m for m in corrected if "081" in m.register_no)
    check("corrected GSTR-2B reclassified (Acme no longer corroborates)",
          acme2.status == "missing", acme2.status)
    check("original cached classification untouched",
          next(m for m in matches if "081" in m.register_no).status == "ai")

    print("== Cascade semantic pass (router over stubbed Converse) ==")
    # Books copy: original Sunrise row loses its GSTIN; the duplicate keeps a
    # valid one and is a LITERAL match, so Tier 1 claims INV/24-25/075 and the
    # semantic tier only ever sees corroborated, unclaimed candidates.
    b2 = books.copy()
    b2.loc[0, "supplier_gstin"] = ""
    dup2 = pd.concat([b2, books.iloc[[0]]], ignore_index=True)

    from backend.tools import smart_router as sr
    asked: list[str] = []
    model_calls = {"n": 0}
    orig_conv = sr.call_bedrock_converse

    def _match_all(model_id, prompt):
        model_calls["n"] += 1
        asked.append(prompt)
        return "MATCH"

    sr.call_bedrock_converse = _match_all
    try:
        bm = app._bedrock_semantic_matcher(dup2, portal)
    finally:
        sr.call_bedrock_converse = orig_conv
    bm_ai = [m for m in bm if m.status == "ai"]
    check("exactly 3 corroborated candidates rescued", len(bm_ai) == 3,
          str([(m.register_no, m.portal_no) for m in bm_ai]))
    if len(bm_ai) == 3:
        check("each claim maps to its own portal row",
              {m.portal_no for m in bm_ai} == {"INV-081", "TAX-2026-019", "INV-2026-907"},
              str({m.portal_no for m in bm_ai}))
        check("blank-GSTIN Sunrise stays missing (fail-closed)",
              any(m.status == "missing" and "075" in m.register_no for m in bm))
    check("conservation: INV/24-25/075 claimed exactly once",
          sum(1 for m in bm if m.status in ("exact", "ai")
              and m.portal_no == "INV/24-25/075") == 1)
    check("blank-GSTIN row never reaches any model prompt",
          all("075" not in p for p in asked), f"{model_calls['n']} model calls")
    check("cost cascade: only the abbreviation vendor needed a paid engine",
          model_calls["n"] == 1
          and {m.engine for m in bm_ai} == {"RapidFuzz", "Nova Micro"},
          str({(m.engine, m.register_no) for m in bm_ai}))
    check("engine attribution only on semantic claims",
          all(not m.engine for m in bm if m.status != "ai"))

    print("== WhatsApp template guards ==")
    empty = app.Match("X", "—", "", "27AA", 100.0, "missing")
    check("wa_preview survives empty supplier name",
          "Supplier" in app.wa_preview(empty, "August 2026"))

    print("== Group 2 identity (tax corroborated, GSTIN verified) ==")
    acme = next(m for m in ai if "081" in m.register_no)
    check("Acme portal invoice is INV-081", acme.portal_no == "INV-081", acme.portal_no)
    check("Acme AI confidence high", acme.ai_conf >= 80, f"{acme.ai_conf}%")
    zen = next(m for m in ai if "019" in m.register_no)
    check("Zenith tax corroborated (2250)", zen.tax == 2_250.0, f"₹{zen.tax:,.0f}")
    check("all AI confidences ≤ 100", all(0 <= m.ai_conf <= 100 for m in ai),
          str([m.ai_conf for m in ai]))

    print("== WhatsApp template ==")
    preview = app.wa_preview(missing[0], "August 2026")
    for token in ("Rule 88D", "GSTR-1", "August 2026", "₹"):
        check(f"template contains {token!r}", token in preview)

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
