"""Reconcile an operator's own documents and return the dashboard snapshot.

Two callers, one implementation:

* ``api/main.py`` — ``POST /api/intake`` reads the uploaded purchase register
  and GSTR-2B file and answers with a snapshot the SPA can render directly;
* ``scripts/export_snapshot.py`` — the same snapshot, built from the fixtures
  that ship with the repository.

The snapshot shape is the contract with the React frontend, so it is built in
exactly one place. Both callers get the real engine: the deterministic pass,
then the semantic pass, then the same spreadsheet failure reconstruction the
demo shows.

Nothing here talks to a browser, and nothing here invents a figure: a file the
engine cannot read comes back as a sentence the sender can act on.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
if str(FRONTEND) not in sys.path:
    sys.path.insert(0, str(FRONTEND))

#: Columns the reconciliation needs. A register missing one of these cannot be
#: matched — and a half-read register would silently under-claim credit, which
#: is worse than refusing it.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "invoice_no",
    "supplier_name",
    "supplier_gstin",
    "taxable_value",
    "total_tax",
)

#: Read if present. Contact details come from here, and without them the
#: supplier can still be flagged — just not messaged.
OPTIONAL_COLUMNS: tuple[str, ...] = ("igst", "cgst", "sgst", "total_amount",
                                     "vendor_phone", "vendor_email",
                                     "invoice_date")


class IntakeError(Exception):
    """A problem with the submitted document, phrased for the person who sent it."""


def _app():
    """The Streamlit module, imported for its engine functions only.

    Importing ``app`` starts no server and renders nothing; the Streamlit
    console and this module share one implementation of every rule.
    """
    import app  # noqa: PLC0415 — deliberately deferred; it is a heavy import

    return app


def read_register(data: bytes, filename: str = "") -> pd.DataFrame:
    """Read a purchase register from raw bytes (xlsx, xls or csv)."""
    name = (filename or "").lower()
    frame: pd.DataFrame | None = None

    # A real xlsx is a zip and a legacy xls is an OLE2 file; anything else that
    # is text is treated as CSV. The extension is a hint, not the decision.
    is_excel = data[:4] == b"PK\x03\x04" or data[:4] == b"\xd0\xcf\x11\xe0"
    if not is_excel:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                frame = pd.read_csv(io.BytesIO(data), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
            except Exception as exc:  # noqa: BLE001 — reported as a plain sentence
                raise IntakeError(
                    "That CSV could not be read. Check that the first row carries the "
                    "column headings and that every row has the same number of commas."
                ) from exc
    if frame is None:
        try:
            frame = pd.read_excel(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise IntakeError(
                "That file could not be read as a spreadsheet. Save the purchase "
                "register as .xlsx or .csv and submit it again."
            ) from exc

    if frame.empty:
        raise IntakeError(
            "The purchase register has no data rows under its headings, so there is "
            "nothing to reconcile. Check that you submitted the register itself and "
            "not a summary sheet."
        )

    # Column headings arrive with stray spaces and any casing; the register an
    # accountant exports is rarely tidy, and tidying it is our job.
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise IntakeError(
            "The purchase register is missing these columns: "
            + ", ".join(missing)
            + ". It needs at least: "
            + ", ".join(REQUIRED_COLUMNS)
            + "."
        )

    for column in ("total_tax", "taxable_value"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["total_tax", "taxable_value"])
    if frame.empty:
        raise IntakeError("No row in the purchase register has a readable tax amount.")
    return frame


def read_portal(data: bytes, filename: str = "") -> dict[str, Any]:
    """Read a GSTR-2B download (JSON) from raw bytes."""
    try:
        payload = json.loads(data.decode("utf-8-sig", errors="strict"))
    except UnicodeDecodeError as exc:
        raise IntakeError(
            "The GSTR-2B file is not text. Download it again from the GST portal "
            "as JSON — the portal can also hand you a PDF, which this page cannot read."
        ) from exc
    except json.JSONDecodeError as exc:
        raise IntakeError(
            "The GSTR-2B file is not valid JSON, so it is probably not the portal "
            "download. On gst.gov.in, take Returns → GSTR-2B → Download as JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise IntakeError("The GSTR-2B file does not contain an object at its root.")

    # The portal wraps the B2B table under b2b, or a versioned key such as
    # b2b_4 / b2b_5 depending on the download year. The backend parser knows
    # all of them; this is only a first, friendlier refusal.
    looks_like_2b = any(
        key == "b2b" or key.startswith("b2b_") for key in payload
    )
    if not looks_like_2b:
        raise IntakeError(
            "This JSON has no b2b section, so it is not a GSTR-2B statement. "
            "On gst.gov.in, take Returns → GSTR-2B → Download as JSON."
        )
    return payload


def period_of(payload: dict[str, Any], fallback: str) -> str:
    """`fp` is MMYYYY; the page shows a period a shop owner can read."""
    raw = str(payload.get("fp") or "")
    if len(raw) == 6 and raw.isdigit():
        months = ("January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December")
        month = int(raw[:2])
        if 1 <= month <= 12:
            return f"{months[month - 1]} {raw[2:]}"
    return fallback


def build_snapshot(books: pd.DataFrame, payload: dict[str, Any],
                   period: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """The snapshot the React page renders, plus any non-fatal warnings."""
    app = _app()
    portal = app._parse_portal(payload)
    if not portal:
        raise IntakeError(
            "The GSTR-2B file has a b2b section but no invoices in it. Check that "
            "you downloaded the right period."
        )

    period = period or period_of(payload, app.DEMO_PERIOD)
    excel = app.run_excel_vlookup(books, portal)
    # The deterministic pass, then the semantic pass — the same two the console
    # runs. `run_recon_pipeline(use_bedrock=False)` is exactly these two calls
    # plus Streamlit's per-session cache; a request is not a session, so the
    # cache is skipped here and the audit write is made explicitly instead.
    matches = app._fallback_semantic_matcher(books, portal)
    app._persist_run(books, portal, matches, degraded=False)

    warnings: list[str] = []
    without_contact = [
        m for m in matches
        if m.status == "missing" and not _contact(books, m.register_no)
    ]
    if without_contact:
        warnings.append(
            f"{len(without_contact)} defaulting supplier(s) have no phone or email "
            "in the register, so no recovery notice can be sent to them."
        )

    def contact(invoice_no: str) -> tuple[str, str]:
        return _contact(books, invoice_no) or ("", "")

    rows = []
    for m in matches:
        phone, email = contact(m.register_no)
        rows.append({
            "register_no": m.register_no,
            "portal_no": m.portal_no,
            "supplier_name": m.supplier_name,
            "supplier_gstin": m.supplier_gstin,
            "tax": round(float(m.tax), 2),
            "status": m.status,
            "ai_conf": int(m.ai_conf),
            "similarity": round(float(m.similarity), 3),
            "reason": m.reason,
            "engine": m.engine,
            "phone": phone,
            "email": email,
            "message": app.wa_preview(m, period) if m.register_no != "—" else "",
        })

    total = float(books["total_tax"].sum())
    exact = sum(m.tax for m in matches if m.status == "exact")
    rescued = sum(m.tax for m in matches if m.status == "ai")
    risk = sum(m.tax for m in matches if m.status == "missing")
    unmatched = [m for m in excel if m.status == "unmatched"]
    write_off = sum(m.tax for m in unmatched)

    costs = app._engine_costs()
    ai_rows = [m for m in matches if m.status == "ai" and m.engine]
    engines: dict[str, int] = {}
    for m in ai_rows:
        engines[m.engine] = engines.get(m.engine, 0) + 1
    tokens_in = sum(m.input_tokens for m in ai_rows)
    tokens_out = sum(m.output_tokens for m in ai_rows)
    usd = sum(
        costs.get(m.engine, 0.0) * (m.input_tokens + m.output_tokens) / 1_000_000
        for m in ai_rows
    )

    from datetime import datetime, timezone  # noqa: PLC0415

    snapshot = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period": period,
        "fp": payload.get("fp", ""),
        "recipient_gstin": payload.get("gstin", ""),
        "totals": {
            "total": round(total, 2),
            "exact": round(exact, 2),
            "rescued": round(rescued, 2),
            "risk": round(risk, 2),
            "write_off": round(write_off, 2),
        },
        "counts": {
            "books": len(books),
            "portal": len(portal),
            "excel_unmatched": len(unmatched),
            "rescued": sum(1 for m in matches if m.status == "ai"),
            "missing": sum(1 for m in matches if m.status == "missing"),
            "portal_only": sum(1 for m in matches if m.status == "portal_only"),
        },
        "excel_unmatched": [
            {
                "register_no": m.register_no,
                "supplier_name": m.supplier_name,
                "tax": round(float(m.tax), 2),
                "portal_no": m.portal_no,
            }
            for m in unmatched
        ],
        "matches": rows,
        "cost": {
            "engines": engines,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "usd": round(usd, 6),
        },
    }
    return snapshot, warnings


def _contact(books: pd.DataFrame, invoice_no: str) -> tuple[str, str] | None:
    """Vendor phone + email from the register, for the dispatch dialog."""
    if "invoice_no" not in books.columns:
        return None
    row = books.loc[books["invoice_no"] == invoice_no]
    if row.empty:
        return None
    phone = str(row.iloc[0].get("vendor_phone") or "")
    email = str(row.iloc[0].get("vendor_email") or "")
    return ("" if phone == "nan" else phone, "" if email == "nan" else email)


def snapshot_from_files(register_data: bytes, portal_data: bytes,
                        register_name: str = "", portal_name: str = "") -> tuple[dict[str, Any], list[str]]:
    """Read both documents and reconcile them."""
    books = read_register(register_data, register_name)
    payload = read_portal(portal_data, portal_name)
    return build_snapshot(books, payload)
