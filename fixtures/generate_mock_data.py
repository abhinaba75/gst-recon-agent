#!/usr/bin/env python3
"""Recon-Agent :: Synthetic GST fixture generator.

Emits two deterministic datasets that reproduce the four canonical
reconciliation failure modes seen in Indian MSME purchase ledgers:

  Group 1 :: Exact Match            — identical GSTIN, invoice no. and tax
  Group 2 :: Typo / Semantic Match  — "INV/24-25/081" vs "INV-081" etc.
  Group 3 :: Defaulting Supplier    — in the books, absent from GSTR-2B
  Group 4 :: Portal-Only Entry      — late-filed credit visible only in 2B

Usage:
    python fixtures/generate_mock_data.py

Writes:
    fixtures/sample_purchase_register.xlsx
    fixtures/sample_gstr2b.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

FIXTURE_DIR = Path(__file__).resolve().parent

REGISTER_XLSX = FIXTURE_DIR / "sample_purchase_register.xlsx"
GSTR2B_JSON = FIXTURE_DIR / "sample_gstr2b.json"

# Tax period 082026 -> August 2026 (fp format used by GSTN systems).
FP = "082026"
RECIPIENT_GSTIN = "29AAACD5678M1Z2"


def _round_rupees(x: float) -> float:
    """Round half-away-from-zero, the way GSTN portals do."""
    return float(int(x + 0.5)) if x >= 0 else -float(int(-x + 0.5))


def _slab(taxable: float, rate: float, *, intra: bool) -> dict[str, float]:
    """Split a taxable value into IGST or CGST+SGST components."""
    if intra:
        half = _round_rupees(taxable * rate / 200.0)
        return {"igst": 0.0, "cgst": half, "sgst": taxable * rate / 100.0 - half}
    return {"igst": _round_rupees(taxable * rate / 100.0), "cgst": 0.0, "sgst": 0.0}


def build_purchase_register() -> pd.DataFrame:
    """Internal books of the MSME — deliberate errors baked in."""
    rows: list[dict[str, object]] = []

    def add(
        invoice_no: str,
        supplier_name: str,
        supplier_gstin: str,
        invoice_date: str,
        taxable_value: float,
        rate: float,
        *,
        intra: bool,
        vendor_phone: str,
    ) -> None:
        tax = _slab(taxable_value, rate, intra=intra)
        total_tax = tax["igst"] + tax["cgst"] + tax["sgst"]
        rows.append(
            {
                "invoice_no": invoice_no,
                "supplier_name": supplier_name,
                "supplier_gstin": supplier_gstin,
                "invoice_date": invoice_date,
                "taxable_value": float(taxable_value),
                "igst": tax["igst"],
                "cgst": tax["cgst"],
                "sgst": tax["sgst"],
                "total_tax": _round_rupees(total_tax),
                "total_amount": float(taxable_value) + _round_rupees(total_tax),
                "vendor_phone": vendor_phone,
            }
        )

    # ── Group 1 :: Exact matches (6 invoices) ─────────────────────────────
    # Karnataka recipient (29): local 29-vendors are intra-state (CGST+SGST),
    # 27/36-vendors are inter-state (IGST) — POS is always the recipient state.
    add("INV/24-25/075", "Sunrise Polymers Pvt Ltd", "27AAECS4821K1ZP",
        "2026-08-02", 84_500.0, 18.0, intra=False, vendor_phone="+919822011456")
    add("TAX/2026/014", "Bharat Office Supplies", "29AAFCB9032L1ZQ",
        "2026-08-04", 32_000.0, 18.0, intra=True, vendor_phone="+919845023347")
    add("INV/24-25/078", "Deccan Chemicals LLP", "36AAGCD1156N1ZS",
        "2026-08-06", 61_200.0, 18.0, intra=False, vendor_phone="+919701133254")
    add("BILL-902", "Kaveri Packaging", "29AAHCK2278P1ZT",
        "2026-08-08", 25_400.0, 12.0, intra=True, vendor_phone="+919886244510")
    add("INV/24-25/083", "Trident Facility Services", "29AAJCT5534Q1ZU",
        "2026-08-11", 48_900.0, 18.0, intra=True, vendor_phone="+919920355628")
    add("INV/24-25/085", "Orion Electronics", "27AAKCO6645R1ZV",
        "2026-08-13", 74_300.0, 18.0, intra=False, vendor_phone="+919833366741")

    # ── Group 2 :: Typo / semantic matches (3 invoices) ───────────────────
    # Portal echoes a mangled number; taxes and GSTIN agree exactly.
    add("INV/24-25/081", "Acme Corporation Pvt Ltd", "27AABCA1234F1Z5",
        "2026-08-15", 100_000.0, 18.0, intra=False, vendor_phone="+919876543210")
    add("TAX/2026/019", "Zenith Logistics Pvt Ltd", "29AABCL5678G1Z3",
        "2026-08-18", 45_000.0, 5.0, intra=True, vendor_phone="+919930588774")
    add("BILL-907", "Nimbus Cloud Services", "27AACCN9901H1Z9",
        "2026-08-20", 58_000.0, 18.0, intra=False, vendor_phone="+919702599806")

    # ── Group 3 :: Defaulting suppliers (in books, ABSENT from 2B) ────────
    # Inter-state (27-suppliers) → IGST under Sec 5 of IGST Act.
    add("INV/24-25/088", "Vertex Industrial Supplies", "27AAECV3345J1ZN",
        "2026-08-09", 82_500.0, 18.0, intra=False, vendor_phone="+919820177890")
    add("TAX/2026/022", "Marathon Freight Movers", "27AAFCM7789K1ZP",
        "2026-08-21", 36_600.0, 5.0, intra=False, vendor_phone="+919845288925")
    add("BILL-910", "Sahyadri Hardware Mart", "27AAGCS1102L1ZQ",
        "2026-08-23", 18_840.0, 18.0, intra=False, vendor_phone="+919762399462")

    # ── Group 4 :: Portal-only entries are NOT in the books here; they live
    # only in sample_gstr2b.json (late filings of July invoices).

    return pd.DataFrame(rows)


def build_gstr2b() -> dict[str, object]:
    """GSTN auto-drafted statement — mirrors the B2B table shape."""
    def inv(
        inum: str, idt: str, val: float, pos: str, itcavl: str,
        txval: float, rt: float, iamt: float, camt: float, samt: float,
    ) -> dict[str, object]:
        return {
            "inum": inum, "idt": idt, "val": val, "pos": pos, "itcavl": itcavl,
            "items": [{"num": 1, "txval": txval, "rt": rt,
                       "iamt": iamt, "camt": camt, "samt": samt}],
        }

    def supplier(ctin: str, trdnm: str, invoices: list[dict[str, object]]) -> dict[str, object]:
        return {"ctin": ctin, "trdnm": trdnm, "inv": invoices}

    return {
        "gstin": RECIPIENT_GSTIN,
        "fp": FP,
        # pos is the Place of Supply = recipient's state (29) for B2B;
        # supplier-state 27/36 vs POS 29 ⇒ IGST, 29 vs 29 ⇒ CGST+SGST.
        "b2b": [
            # ── Group 1 :: exact echoes of the books ──────────────────────
            supplier("27AAECS4821K1ZP", "Sunrise Polymers Pvt Ltd", [
                inv("INV/24-25/075", "02-08-2026", 99_710.0, "29", "Y",
                    84_500.0, 18.0, 15_210.0, 0.0, 0.0),
            ]),
            supplier("29AAFCB9032L1ZQ", "Bharat Office Supplies", [
                inv("TAX/2026/014", "04-08-2026", 37_760.0, "29", "Y",
                    32_000.0, 18.0, 0.0, 2_880.0, 2_880.0),
            ]),
            supplier("36AAGCD1156N1ZS", "Deccan Chemicals LLP", [
                inv("INV/24-25/078", "06-08-2026", 72_216.0, "29", "Y",
                    61_200.0, 18.0, 11_016.0, 0.0, 0.0),
            ]),
            supplier("29AAHCK2278P1ZT", "Kaveri Packaging", [
                inv("BILL-902", "08-08-2026", 28_448.0, "29", "Y",
                    25_400.0, 12.0, 0.0, 1_524.0, 1_524.0),
            ]),
            supplier("29AAJCT5534Q1ZU", "Trident Facility Services", [
                inv("INV/24-25/083", "11-08-2026", 57_702.0, "29", "Y",
                    48_900.0, 18.0, 0.0, 4_401.0, 4_401.0),
            ]),
            supplier("27AAKCO6645R1ZV", "Orion Electronics", [
                inv("INV/24-25/085", "13-08-2026", 87_674.0, "29", "Y",
                    74_300.0, 18.0, 13_374.0, 0.0, 0.0),
            ]),
            # ── Group 2 :: mangled invoice numbers, identical tax ─────────
            supplier("27AABCA1234F1Z5", "Acme Corp", [
                inv("INV-081", "15-08-2026", 118_000.0, "29", "Y",
                    100_000.0, 18.0, 18_000.0, 0.0, 0.0),
            ]),
            supplier("29AABCL5678G1Z3", "Zenith Logistics", [
                inv("TAX-2026-019", "18-08-2026", 47_250.0, "29", "Y",
                    45_000.0, 5.0, 0.0, 1_125.0, 1_125.0),
            ]),
            supplier("27AACCN9901H1Z9", "Nimbus Cloud Services Pvt. Ltd.", [
                inv("INV-2026-907", "20-08-2026", 68_440.0, "29", "Y",
                    58_000.0, 18.0, 10_440.0, 0.0, 0.0),
            ]),
            # ── Group 4 :: portal-only late filings from July ─────────────
            supplier("27AAECP4412M1ZR", "Pinnacle Marketing", [
                inv("INV-0056", "12-07-2026", 66_720.0, "29", "Y",
                    56_000.0, 18.0, 0.0, 5_040.0, 5_040.0),
            ]),
            supplier("27AAFCQ8823N1ZT", "Quantum Print Solutions", [
                inv("QP/2026/031", "28-07-2026", 94_380.0, "29", "Y",
                    80_000.0, 18.0, 14_400.0, 0.0, 0.0),
            ]),
        ],
    }


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    register = build_purchase_register()
    register.to_excel(REGISTER_XLSX, index=False, sheet_name="Purchase Register")

    gstr2b = build_gstr2b()
    GSTR2B_JSON.write_text(json.dumps(gstr2b, indent=2) + "\n", encoding="utf-8")

    books_itc = register["total_tax"].sum()
    portal_itc = sum(
        item["iamt"] + item["camt"] + item["samt"]
        for sup in gstr2b["b2b"]  # type: ignore[union-attr]
        for i in sup["inv"]       # type: ignore[index]
        for item in i["items"]    # type: ignore[index]
    )
    print(f"Wrote {REGISTER_XLSX.relative_to(FIXTURE_DIR.parent)} "
          f"({len(register)} invoices, ITC Rs {books_itc:,.0f})")
    print(f"Wrote {GSTR2B_JSON.relative_to(FIXTURE_DIR.parent)} "
          f"({sum(len(s['inv']) for s in gstr2b['b2b'])} invoices, ITC Rs {portal_itc:,.0f})")
    print("Groups :: 6 exact | 3 typo/semantic | 3 defaulting | 2 portal-only")


if __name__ == "__main__":
    main()
