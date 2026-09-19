#!/usr/bin/env python3
"""Export the dashboard snapshot the React frontend renders.

This is the contract between the two halves of the product: the Python engine
stays the single source of truth for every figure, and the web app displays
what this script produced. Run it after changing fixtures or the engine:

    .venv/bin/python scripts/export_snapshot.py

Writes ``web/src/data/snapshot.json``. The reconciliation itself lives in
``backend/intake.py`` — the same module the API uses for an operator's own
upload, so a submitted run and the shipped sample cannot drift apart.

It never touches AWS: persistence is stubbed here, exactly as the test suites
do it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["RECON_RESULTS_TABLE"] = ""  # never write to the deployed table

from backend import intake  # noqa: E402

OUT = ROOT / "web" / "src" / "data" / "snapshot.json"


def main() -> int:
    # Import the Streamlit module through the intake helper, then make sure a
    # snapshot export can never append an audit row to a deployed table.
    app = intake._app()
    app._persist_run = lambda *a, **k: None  # belt and braces for the export run

    books = pd.read_excel(app.REGISTER_XLSX)
    payload = json.loads(app.GSTR2B_JSON.read_text(encoding="utf-8"))

    snapshot, warnings = intake.build_snapshot(books, payload)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} — "
          f"{snapshot['counts']['books']} books / {snapshot['counts']['portal']} 2B rows, "
          f"rescued ₹{snapshot['totals']['rescued']:,.0f}, "
          f"risk ₹{snapshot['totals']['risk']:,.0f}, "
          f"write-off ₹{snapshot['totals']['write_off']:,.0f}")
    for warning in warnings:
        print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
