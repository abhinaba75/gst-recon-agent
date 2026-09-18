"""GSTR-2B JSON parser — accepts the real GSTN download schema.

The GSTN portal's "Download JSON" for GSTR-2B wraps the B2B table in a
versioned envelope whose shape varies by API version and statement period.
Real downloads differ from the tidy fixture in three ways this parser
absorbs:

1. The invoice list may sit under ``b2b`` **or** under versioned envelopes
   (``b2b_4`` / ``b2b_5``), each holding period groups (``OPPATTR``-style)
   with the actual ``b2b`` supplier tables nested inside.
2. Numerics can arrive as strings, with blanks, or as ``NaN`` — junk in, zero
   out, never an exception in the reconcile path.
3. Invoice-level ``val`` may be absent; the fallback sums taxable value plus
   taxes so ``val`` is always a present, sane number.

Output is the exact dict shape ``frontend/app.py::_parse_portal`` already
consumes, so the app delegates to this module and nothing else changes.
"""

from __future__ import annotations

from typing import Any

# Envelope keys the portal has used for B2B tables, in priority order.
_B2B_KEYS = ("b2b", "b2b_4", "b2b_5", "b2ba")
# Tax components aggregated per invoice from the item lines.
_TAX_KEYS = ("txval", "iamt", "camt", "samt")


def _num(value: Any, default: float = 0.0) -> float:
    """Coerce a GSTN numeric (str / float / None / 'NaN' / '') to float."""
    if value is None:
        return default
    try:
        f = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return default
    return default if f != f else f  # NaN check without math import


def _suppliers(payload: dict) -> list[dict]:
    """Supplier tables from the flat or versioned envelope, in order."""
    for key in _B2B_KEYS:
        block = payload.get(key)
        if isinstance(block, list) and block:
            # Versioned envelopes nest period groups holding the real tables.
            if all(isinstance(g, dict) and "b2b" in g for g in block):
                return [s for g in block for s in (g.get("b2b") or [])]
            return block
    return []


def parse_gstr2b(payload: dict) -> list[dict[str, Any]]:
    """Parse a GSTR-2B payload into flat, app-ready invoice dicts.

    Each dict carries: ctin, trdnm, inum, idt, val, itcavl, txval, igst, cgst,
    sgst — the exact fields ``_parse_portal`` maps onto its PortalRow.
    """
    rows: list[dict[str, Any]] = []
    for sup in _suppliers(payload):
        ctin = str(sup.get("ctin", "") or "")
        trdnm = str(sup.get("trdnm", "") or "")
        for inv in sup.get("inv", []) or []:
            items = inv.get("items") or [{}]
            agg = {k: round(sum(_num(i.get(k)) for i in items), 2) for k in _TAX_KEYS}
            val = _num(inv.get("val"), -1.0)
            if val < 0:  # absent or junk → rebuild from the components
                val = round(agg["txval"] + agg["iamt"] + agg["camt"] + agg["samt"], 2)
            rows.append({
                "ctin": ctin,
                "trdnm": trdnm,
                "inum": str(inv.get("inum", "") or ""),
                "idt": str(inv.get("idt", "") or ""),
                "val": val,
                "itcavl": str(inv.get("itcavl", "N") or "N"),
                "txval": agg["txval"],
                "igst": agg["iamt"],
                "cgst": agg["camt"],
                "sgst": agg["samt"],
            })
    return rows
