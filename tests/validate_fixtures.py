#!/usr/bin/env python3
"""Deterministic validation of Recon-Agent fixtures and both pipelines.

Run directly (no pytest needed):  python tests/validate_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "frontend"))

import app  # noqa: E402  (Streamlit module import — no server started)


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
