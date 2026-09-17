#!/usr/bin/env python3
"""Headless UI smoke test for frontend/app.py using streamlit.testing.AppTest.

Run directly (no pytest needed):  python tests/smoke_ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "frontend"))

from streamlit.testing.v1 import AppTest  # noqa: E402


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print("== Initial render (demo fixtures) ==")
    at = AppTest.from_file(str(ROOT / "frontend" / "app.py"), default_timeout=60)
    at.run()
    check("no exception on first render", not at.exception,
          str(at.exception)[:200] if at.exception else "")
    check("title rendered", any("Recon-Agent" in t.value for t in at.title),
          str([t.value for t in at.title]))
    check("4 KPI metrics", len(at.metric) >= 4, f"{len(at.metric)} metrics")
    if len(at.metric) >= 4:
        labels = [m.label for m in at.metric[:4]]
        check("KPI labels correct",
              labels == ["Total Invoiced ITC", "Reconciled ITC (Exact)",
                         "Rescued ITC (AI)", "ITC at High Risk"], str(labels))
        check("rescued KPI shows ₹30,690",
              any("30,690" in m.value for m in at.metric),
              str([m.value for m in at.metric]))
    check("two dataframes rendered", len(at.dataframe) >= 2, f"{len(at.dataframe)} frames")
    check("dispatch buttons present",
          any(b.key and b.key.startswith("wa-") for b in at.button),
          str([b.key for b in at.button if b.key]))

    print("== WhatsApp A2A dispatch flow ==")
    btn = next(b for b in at.button if b.key and b.key.startswith("wa-"))
    btn.click()
    at.run()
    check("no exception after dispatch click", not at.exception,
          str(at.exception)[:200] if at.exception else "")
    check("modal state set", bool(at.session_state.get("wa_modal")))
    check("comms agent logged", any("[A2A]" in line for line in at.session_state["log"]),
          "log tail: " + str(at.session_state["log"][-1:]))

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all UI checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
