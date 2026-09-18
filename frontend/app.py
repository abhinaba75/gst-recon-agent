"""Recon-Agent :: Autonomous GST ITC Reconciliation frontend.

Streamlit compliance console for the WeMakeDevs AWS First Commit Hackathon.
Runs fully self-contained on the bundled fallback engine so judges can click
through the demo while the AWS Bedrock / Strands backend is still spinning up.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final

import boto3
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "fixtures"
REGISTER_XLSX = FIXTURE_DIR / "sample_purchase_register.xlsx"
GSTR2B_JSON = FIXTURE_DIR / "sample_gstr2b.json"

# The backend package lives one level up; make it importable when Streamlit
# runs this file from the project root (or anywhere else).
import sys  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Legal hooks surfaced in the UI (CGST Act / Rules / GSTN notices).
SEC_16_2AA: Final = "Section 16(2)(aa) — ITC only if visible in GSTR-2B"
RULE_88D: Final = "Rule 88D / DRC-01C — auto discrepancy intimation"
SEC_50_3: Final = "Section 50(3) — 18%–24% p.a. punitive interest"
# Demo tax period (fp 082026 → August 2026). The live backend supplies the
# real period; until then every panel reads this constant.
DEMO_PERIOD: Final = "August 2026"

# Status stamps — the rubber stamps of an Indian compliance file.
STAMPS: Final = {
    "exact": "MATCHED · DETERMINISTIC",
    "ai": "MATCHED · AI {:.0f}%",
    "missing": "DEFAULTING SUPPLIER",
    "portal_only": "PORTAL-ONLY · LATE FILING",
    "unmatched": "UNRESOLVED",
}

# Stamp chip palette per status: (background wash, stamp colour).
STAMP_STYLE: Final = {
    "exact": ("rgba(48, 164, 108, 0.08)", "#30A46C"),
    "ai": ("rgba(216, 185, 78, 0.10)", "#D8B94E"),
    "missing": ("rgba(229, 72, 77, 0.10)", "#E5484D"),
    "portal_only": ("rgba(122, 147, 196, 0.12)", "#7A93C4"),
    "unmatched": ("rgba(229, 72, 77, 0.16)", "#F26D6D"),
}


def stamp(status: str, ai_conf: float = 0.0) -> str:
    """A rubber-stamp chip: double-ring border, letterspaced caps, mono face."""
    bg, fg = STAMP_STYLE[status]
    text = STAMPS["ai"].format(ai_conf) if status == "ai" else STAMPS[status]
    return (
        f"<span style='font-family:\"IBM Plex Mono\",monospace;font-size:0.68rem;"
        f"letter-spacing:0.14em;color:{fg};background:{bg};"
        f"border:3px double {fg};border-radius:3px;padding:2px 8px;"
        f"white-space:nowrap'>{text}</span>"
    )


# ══════════════════════════════════════════════════════════════════════════
#  Dataclasses
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class PortalRow:
    ctin: str
    trdnm: str
    inum: str
    idt: str
    val: float
    itcavl: str
    txval: float
    igst: float
    cgst: float
    sgst: float

    @property
    def tax(self) -> float:
        return round(self.igst + self.cgst + self.sgst, 2)


@dataclass
class Match:
    register_no: str
    portal_no: str
    supplier_name: str
    supplier_gstin: str
    tax: float
    status: str          # exact | ai | missing | portal_only | unmatched
    ai_conf: float = 0.0
    similarity: float = 0.0
    reason: str = ""

    @property
    def label(self) -> str:
        if self.status == "ai":
            return STAMPS["ai"].format(self.ai_conf)
        return STAMPS[self.status]


# ══════════════════════════════════════════════════════════════════════════
#  Reconciliation engines — shared deterministic tier, then a semantic tier
#  that runs on AWS Bedrock (boto3 Converse) or falls back to a local matcher
# ══════════════════════════════════════════════════════════════════════════
def _canonical(s: str) -> str:
    """Lowercase, de-accent, keep [a-z0-9] only — defeats separator typos."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "").lower())


def _similarity(a: str, b: str) -> float:
    return round(SequenceMatcher(None, _canonical(a), _canonical(b)).ratio(), 3)


BEDROCK_MODEL_ID: Final = os.environ.get(
    "RECON_BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0"
)


def _bedrock_client():
    region = os.environ.get("RECON_AWS_REGION") or os.environ.get("AWS_REGION") or "ap-south-1"
    return boto3.client("bedrock-runtime", region_name=region)


def _parse_verdict(text: str) -> dict | None:
    """Extract the one JSON object from a model reply; None if unparseable."""
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def _corroborate(books: pd.DataFrame, b: int, p: PortalRow) -> bool:
    """Tax within ₹2 AND GSTIN equality. Fail-closed, enforced in Python —
    the model can re-identify rows but never re-price or re-attribute them."""
    bt = round(float(books.at[b, "total_tax"]), 2)
    if abs(bt - p.tax) > 2.0:
        return False
    return _canonical(str(books.at[b, "supplier_gstin"])) == _canonical(p.ctin)


def _build_match(books: pd.DataFrame, b: int, p: PortalRow,
                 status: str, conf: float, reason: str) -> Match:
    return Match(
        register_no=str(books.at[b, "invoice_no"]),
        portal_no=p.inum,
        supplier_name=str(books.at[b, "supplier_name"]),
        supplier_gstin=str(books.at[b, "supplier_gstin"]),
        tax=round(float(books.at[b, "total_tax"]), 2),
        status=status,
        ai_conf=round(conf * 100),
        similarity=_similarity(str(books.at[b, "supplier_name"]), p.trdnm),
        reason=reason,
    )


def _reconcile_deterministic(
    books: pd.DataFrame, portal: list[PortalRow]
) -> tuple[list[Match], set[int], set[str]]:
    """Tier 1 — literal invoice-number equality with full corroboration.

    Every claimed portal row is removed from all later candidate sets, so a
    duplicate books line can never double-claim one GSTR-2B entry.
    """
    matches: list[Match] = []
    used: set[int] = set()
    used_portal: set[str] = set()
    for b, key in ((i, str(v).strip().upper()) for i, v in books["invoice_no"].items()):
        for p in portal:
            if p.inum in used_portal:
                continue
            if p.inum.strip().upper() == key and _corroborate(books, b, p):
                matches.append(_build_match(books, b, p, "exact", 1.0,
                                            "GSTIN + invoice + tax identical"))
                used.add(b)
                used_portal.add(p.inum)
                break
    return matches, used, used_portal


def _classify_remainder(books: pd.DataFrame, portal: list[PortalRow],
                        matches: list[Match], used: set[int],
                        used_portal: set[str]) -> None:
    """Unmatched books rows → defaulting suppliers; unclaimed portal rows → late filings."""
    for b in range(len(books)):
        if b in used:
            continue
        matches.append(
            Match(
                register_no=str(books.at[b, "invoice_no"]),
                portal_no="—",
                supplier_name=str(books.at[b, "supplier_name"]),
                supplier_gstin=str(books.at[b, "supplier_gstin"]),
                tax=round(float(books.at[b, "total_tax"]), 2),
                status="missing",
                reason="Supplier has not filed GSTR-1 for the period",
            )
        )
    for p in portal:
        if p.inum in used_portal:
            continue
        matches.append(
            Match(
                register_no="—",
                portal_no=p.inum,
                supplier_name=p.trdnm,
                supplier_gstin=p.ctin,
                tax=p.tax,
                status="portal_only",
                reason="Late cross-period filing — eligible ITC carried forward",
            )
        )


def _bedrock_semantic_matcher(
    books: pd.DataFrame, portal: list[PortalRow], min_conf: float = 0.75
) -> list[Match]:
    """Tier 2 on AWS Bedrock (Converse API), standing in for the planned MCP tool.

    Python gates every candidate through tax+GSTIN corroboration first; the
    model only decides whether a corroborated candidate is the *same document*
    (invoice-number formats, trailing serials, trade-name abbreviations). Its
    JSON verdict is parsed, hallucination-checked against the candidate list,
    and clamped. One-to-one conservation is enforced here, not trusted to the
    model.
    """
    matches, used, used_portal = _reconcile_deterministic(books, portal)
    log_run(f"[AGENT] Tier-1 deterministic pass: {len(matches)} exact matches")

    client = _bedrock_client()
    system = (
        "You are the Fuzzy Matcher inside Recon-Agent, an Indian GST ITC "
        "reconciliation agent. Buyer and supplier identity are already "
        "verified (GSTIN equal, tax equal to the rupee). Decide whether a "
        "books invoice and a portal (GSTR-2B) invoice are the same commercial "
        "document, judging only invoice-number formats (separators, prefixes, "
        "financial-year fragments), trailing serial numbers, trade-name "
        "abbreviations and dates. Be conservative: differing serial numbers or "
        "unrelated names mean NO_MATCH. Reply with ONLY one JSON object: "
        '{"match": "<portal inum or null>", "confidence": <0-100>, '
        '"reason": "<= 12 words"}'
    )

    rescued = 0
    for b in range(len(books)):
        if b in used:
            continue
        candidates = [p for p in portal
                      if p.inum not in used_portal and _corroborate(books, b, p)]
        if not candidates:
            continue
        row = {
            "books_invoice": {
                "invoice_no": str(books.at[b, "invoice_no"]),
                "supplier_name": str(books.at[b, "supplier_name"]),
                "invoice_date": str(books.at[b, "invoice_date"]),
                "tax": round(float(books.at[b, "total_tax"]), 2),
            },
            "portal_candidates": [
                {"inum": p.inum, "trade_name": p.trdnm, "date": p.idt, "tax": p.tax}
                for p in candidates
            ],
        }
        resp = client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": json.dumps(row)}]}],
            inferenceConfig={"temperature": 0.0, "maxTokens": 200},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        verdict = _parse_verdict(text)
        if verdict is None:
            log_run(f"[AGENT] Bedrock returned an unparseable verdict for "
                    f"'{books.at[b, 'invoice_no']}' — left unmatched")
            continue
        chosen = next((p for p in candidates if p.inum == verdict.get("match")), None)
        if chosen is None:
            log_run(f"[AGENT] Bedrock → '{books.at[b, 'invoice_no']}': NO_MATCH")
            continue
        conf = max(0.0, min(float(verdict.get("confidence", 0)), 100.0)) / 100.0
        if conf < min_conf:
            log_run(f"[AGENT] Bedrock → '{books.at[b, 'invoice_no']}': below "
                    f"threshold ({conf:.0%})")
            continue
        matches.append(_build_match(
            books, b, chosen, "ai", conf,
            f"Bedrock semantic ID · tax+GSTIN corroborated · {verdict.get('reason', '')}",
        ))
        used.add(b)
        used_portal.add(chosen.inum)
        rescued += 1
        log_run(f"[AGENT] Bedrock → '{books.at[b, 'invoice_no']}' ⇄ "
                f"'{chosen.inum}' ({conf:.0%})")

    _classify_remainder(books, portal, matches, used, used_portal)
    log_run(f"[AGENT] Bedrock semantic pass completed ({rescued} rescued)")
    return matches


def _fallback_semantic_matcher(
    books: pd.DataFrame, portal: list[PortalRow], min_conf: float = 0.75
) -> list[Match]:
    """Offline stand-in with the same contract as the Bedrock matcher.

    Same deterministic tier, same corroboration gate, same conservation rules;
    the semantic tier scores name similarity plus trailing-serial identity so
    the demo behaves identically with zero cloud dependency.
    """
    matches, used, used_portal = _reconcile_deterministic(books, portal)
    log_run(f"[AGENT] Tier-1 deterministic pass: {len(matches)} exact matches")

    for b in range(len(books)):
        if b in used:
            continue
        bname = str(books.at[b, "supplier_name"])
        best: tuple[float, PortalRow] | None = None
        for p in portal:
            if p.inum in used_portal or not _corroborate(books, b, p):
                continue
            sim = max(_similarity(bname, p.trdnm), _similarity(bname, p.trdnm.replace(".", "")))
            b_serial = re.findall(r"\d+", str(books.at[b, "invoice_no"]))[-1:]
            p_serial = re.findall(r"\d+", p.inum)[-1:]
            serial = 1.0 if b_serial and b_serial == p_serial else 0.0
            # Bounded composite: name similarity + trailing-serial identity +
            # the already-gated GSTIN/tax corroboration. Max = 1.0.
            score = min(0.40 * sim + 0.35 * serial + 0.25, 1.0)
            if best is None or score > best[0]:
                best = (score, p)
        if best and best[0] >= min_conf:
            p = best[1]
            matches.append(_build_match(
                books, b, p, "ai", best[0],
                f"Tax corroborated · GSTIN verified · numeral overlap on '{p.inum}'",
            ))
            used.add(b)
            used_portal.add(p.inum)

    _classify_remainder(books, portal, matches, used, used_portal)
    log_run(f"[AGENT] Fallback pass completed ({len(matches)} results)")
    return matches


# ══════════════════════════════════════════════════════════════════════════
#  Data loading
# ══════════════════════════════════════════════════════════════════════════
def _parse_portal(payload: dict) -> list[PortalRow]:
    rows: list[PortalRow] = []
    for sup in payload.get("b2b", []):
        for inv in sup.get("inv", []):
            items = inv.get("items", [{}])
            agg = {k: round(sum(i.get(k, 0.0) for i in items), 2)
                   for k in ("txval", "iamt", "camt", "samt")}
            rows.append(
                PortalRow(
                    ctin=str(sup.get("ctin", "")),
                    trdnm=str(sup.get("trdnm", "")),
                    inum=str(inv.get("inum", "")),
                    idt=str(inv.get("idt", "")),
                    val=float(inv.get("val", 0.0)),
                    itcavl=str(inv.get("itcavl", "N")),
                    txval=agg["txval"],
                    igst=agg["iamt"],
                    cgst=agg["camt"],
                    sgst=agg["samt"],
                )
            )
    return rows


def load_data(
    books: pd.DataFrame | None = None, payload: dict | None = None
) -> tuple[pd.DataFrame, list[PortalRow]] | tuple[None, None]:
    """Load fixtures (demo button, bundled data, or explicit uploads)."""
    if books is None or payload is None:
        if st.session_state.get("uploads"):
            books, payload = st.session_state["uploads"]
        else:
            try:
                books = pd.read_excel(REGISTER_XLSX)
                payload = json.loads(GSTR2B_JSON.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError):
                return None, None
    return books, _parse_portal(payload)


# ══════════════════════════════════════════════════════════════════════════
#  Reconciliation pipelines
# ══════════════════════════════════════════════════════════════════════════
def run_excel_vlookup(books: pd.DataFrame, portal: list[PortalRow]) -> list[Match]:
    """What a CA's spreadsheet actually does: strict =VLOOKUP on invoice_no."""
    log_run("[EXCEL] =VLOOKUP(A2, 'GSTR-2B'!A:F, 2, FALSE) …")
    # Real spreadsheets do a literal cell comparison — no canonicalisation.
    lookup = {p.inum.strip().upper(): p for p in portal}
    out: list[Match] = []
    for _, r in books.iterrows():
        p = lookup.get(str(r["invoice_no"]).strip().upper())
        if p is None:
            out.append(
                Match(str(r["invoice_no"]), "—", str(r["supplier_name"]),
                      str(r["supplier_gstin"]), round(float(r["total_tax"]), 2),
                      "unmatched", 0.0, 0.0, "Literal string mismatch → #N/A")
            )
        elif abs(round(float(r["total_tax"]), 2) - p.tax) > 2.0:
            out.append(
                Match(str(r["invoice_no"]), p.inum, str(r["supplier_name"]),
                      str(r["supplier_gstin"]), round(float(r["total_tax"]), 2),
                      "unmatched", 0.0, 0.0, "Tax amount differs from 2B → flagged")
            )
        else:
            out.append(
                Match(str(r["invoice_no"]), p.inum, str(r["supplier_name"]),
                      str(r["supplier_gstin"]), round(float(r["total_tax"]), 2),
                      "exact", 0.0, 0.0, "Literal string match")
            )
    log_run(f"[EXCEL] {sum(m.status == 'exact' for m in out)} matched, "
            f"{sum(m.status == 'unmatched' for m in out)} cells return #N/A")
    return out


def _persist_run(books: pd.DataFrame, portal: list[PortalRow],
                 matches: list[Match]) -> None:
    """Store a cache-miss run in DynamoDB; narration only, never fatal."""
    try:
        from backend.db import results as db
        run_id = db.persist_run(
            DEMO_PERIOD, len(books), len(portal), matches,
            {"total": float(books["total_tax"].sum()),
             "exact": sum(m.tax for m in matches if m.status == "exact"),
             "ai": sum(m.tax for m in matches if m.status == "ai"),
             "risk": sum(m.tax for m in matches if m.status == "missing")},
        )
    except Exception as exc:  # noqa: BLE001 — persistence must not break the demo
        log_run(f"[DB] Persistence unavailable ({type(exc).__name__}) — run not stored")
        return
    if run_id:
        log_run(f"[DB] Run {run_id} persisted to DynamoDB audit trail")
    else:
        log_run("[DB] Persistence not configured or unreachable — run not stored")


def run_recon_pipeline(
    books: pd.DataFrame, portal: list[PortalRow], use_bedrock: bool = False
) -> list[Match]:
    """Deterministic pass, then a semantic pass on Bedrock or the local fallback.

    Results are cached per dataset+engine in session state, so Streamlit
    reruns (any widget interaction) never re-invoke Bedrock or re-bill it.
    Fresh runs (cache misses) are persisted to the DynamoDB audit trail once.
    """
    digest = hashlib.sha256(
        (books.to_csv(index=True)
         + "\x1e".join(p.inum for p in portal)
         + f"|{use_bedrock}|{BEDROCK_MODEL_ID}").encode()
    ).hexdigest()
    cache = st.session_state.setdefault("recon_cache", {})
    if digest in cache:
        log_run("[AGENT] Pipeline cache hit — Bedrock not re-invoked")
        return cache[digest]

    log_run(f"[AGENT] Ingesting {len(books)} books rows vs {len(portal)} GSTR-2B rows")
    if use_bedrock:
        log_run(f"[AGENT] Invoking Bedrock Converse · {BEDROCK_MODEL_ID.rsplit('.', 1)[-1]}")
        try:
            matches = _bedrock_semantic_matcher(books, portal)
        except Exception as exc:  # noqa: BLE001 — the demo must never crash on stage
            log_run(f"[AGENT] Bedrock unreachable ({type(exc).__name__}) → local fallback")
            st.warning("AWS Bedrock unreachable — continuing on the local semantic matcher.")
            matches = _fallback_semantic_matcher(books, portal)
    else:
        matches = _fallback_semantic_matcher(books, portal)
    _persist_run(books, portal, matches)
    cache[digest] = matches
    return matches


# ══════════════════════════════════════════════════════════════════════════
#  Agent activity log
# ══════════════════════════════════════════════════════════════════════════
_LOG_CAP: Final = 150


def log(msg: str) -> None:
    """Event log — survives reruns (demo loads, uploads, dispatches)."""
    entry = f"{datetime.now().strftime('%H:%M:%S')}  {msg}"
    lines = st.session_state.setdefault("log", [])
    lines.append(entry)
    del lines[:-_LOG_CAP]


def log_run(msg: str) -> None:
    """Render-path log — narration of the current reconciliation run.

    Reset at the start of every rerun (see main), so widget interactions never
    flood the console with duplicate pipeline lines, and storage stays bounded.
    """
    st.session_state.setdefault("run_log", []).append(
        f"{datetime.now().strftime('%H:%M:%S')}  {msg}"
    )


# ══════════════════════════════════════════════════════════════════════════
#  WhatsApp A2A recovery
# ══════════════════════════════════════════════════════════════════════════
WA_TPL: Final = (
    "Dear {supplier}, Invoice {invoice_no} of ₹{amount} is missing from our "
    "GSTR-2B for {period}. Please file your GSTR-1 before the 11th to prevent "
    "credit blockage under Rule 88D."
)


def wa_preview(m: Match, period: str) -> str:
    return WA_TPL.format(
        supplier=m.supplier_name.split()[0] if m.supplier_name.split() else "Supplier",
        invoice_no=m.register_no,
        amount=inr(m.tax).lstrip("₹"),
        period=period,
    )


# ══════════════════════════════════════════════════════════════════════════
#  Rendering
# ══════════════════════════════════════════════════════════════════════════
_GROUP: Final = re.compile(r"(\d)(?=(\d\d)+\d$)")


def inr(amount: float) -> str:
    """Indian digit grouping — the way every GST invoice in the country reads:
    ₹1,07,971 (one lakh), not ₹107,971 (one hundred thousand)."""
    neg = amount < 0
    digits = f"{abs(round(amount)):,.0f}".replace(",", "")
    grouped = _GROUP.sub(r"\1,", digits)
    return f"{'-' if neg else ''}₹{grouped}"


def _tables(m: Match) -> tuple[str, str]:
    """A books entry and its portal counterpart, as two ledger rows."""
    name = html.escape(m.supplier_name)
    books = f"{html.escape(m.register_no)} — {name} — {inr(m.tax)}"
    portal = f"{html.escape(m.portal_no)} — {name} — {inr(m.tax)}"
    return books, portal


def _row(m: Match, status: str) -> str:
    """One stamped entry of the written-off / rescued stack."""
    books, portal = _tables(m)
    head = f"<code>{stamp(status, m.ai_conf)}</code> &nbsp;<code>{books}</code>"
    if status == "unmatched":
        return f"{head}<br><small style='color:#8B93A7'>{portal}</small>"
    sub = f"{m.reason} · name similarity {m.similarity:.0%}"
    return f"{head}<br><code>{portal}</code><br><small style='color:#8B93A7'>{sub}</small>"


def _stack(rows: list[str]) -> str:
    """Ledger rows separated by faint dashed rules, like a register page."""
    rule = "<hr style='border:0;border-top:1px dashed #2C3750;margin:0'>"
    return ("<div style='display:flex;flex-direction:column;row-gap:14px;"
            "overflow-wrap:anywhere'>" + rule.join(rows) + "</div>")


def render_side_by_side(excel: list[Match], ai: list[Match]) -> None:
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("### The spreadsheet, faithfully reproduced")
        st.code('=VLOOKUP(A2, \'GSTR-2B\'!A:F, 2, FALSE)', language="excel")
        fails = [m for m in excel if m.status == "unmatched"]
        st.metric("Written off as lost", inr(sum(m.tax for m in fails)),
                  delta=f"{len(fails)} invoices return #N/A", delta_color="inverse")
        st.markdown(
            "A literal cell comparison cannot see past a separator. Every miss "
            "lands in the same pile — the recoverable and the genuinely risky alike.")
        st.markdown(_stack([_row(m, "unmatched") for m in fails]),
                    unsafe_allow_html=True)

    with right:
        st.markdown("### The same rows, reconciled")
        rescued = [m for m in ai if m.status == "ai"]
        log_run(f"[AGENT] Semantic pass recovered {len(rescued)} invoices "
                f"({inr(sum(m.tax for m in rescued))})")
        st.metric("Rescued by the semantic pass", inr(sum(m.tax for m in rescued)),
                  delta=f"{len(rescued)} invoices recovered", delta_color="normal")
        st.markdown(
            "Tax corroborated to the rupee and GSTIN verified before any match is "
            "proposed. The agent re-identifies rows; it never invents money.")
        st.markdown(_stack([_row(m, "ai") for m in rescued]),
                    unsafe_allow_html=True)


def render_recovery_panel(matches: list[Match], period: str) -> None:
    st.markdown("### Supplier recovery")
    st.caption(f"Defaulting vendors, handed to the A2A comms agent — {RULE_88D}, {SEC_50_3}")
    missing = [m for m in matches if m.status == "missing"]
    if not missing:
        st.success("No defaulting suppliers this period.")
        return
    st.metric("Trapped with non-filing suppliers", inr(sum(m.tax for m in missing)),
              delta=f"{len(missing)} invoices at risk", delta_color="inverse")
    df = pd.DataFrame(
        [{"Invoice": m.register_no, "Supplier": m.supplier_name,
          "GSTIN": m.supplier_gstin, "ITC": inr(m.tax),
          "Phone": wa_number(m) or "—"} for m in missing]
    )
    st.dataframe(df, width="stretch", hide_index=True)
    for m in missing:
        phone = wa_number(m)
        c1, c2, _ = st.columns([2.1, 1.7, 0.4])
        c1.markdown(
            f"<code>{stamp('missing')}</code> &nbsp;{html.escape(m.supplier_name)} — "
            f"{html.escape(m.register_no)} — {inr(m.tax)}", unsafe_allow_html=True)
        if c2.button("Dispatch WhatsApp Recovery Notice via A2A Agent",
                     key=f"wa-{m.register_no}",
                     disabled=not phone,
                     help="Disabled: no vendor phone in register" if not phone else None):
            log(f"[A2A] Delegated to Comms Agent → {m.supplier_name} ({phone})")
            st.session_state["wa_modal"] = m
            st.rerun()


def wa_number(m: Match) -> str | None:
    books = st.session_state.get("books")
    if books is None:
        return None
    row = books.loc[books["invoice_no"] == m.register_no, "vendor_phone"]
    return str(row.iloc[0]) if not row.empty else None


def _close_wa_modal() -> None:
    st.session_state.pop("wa_modal", None)
    st.rerun()


@st.dialog("A2A Comms Agent · WhatsApp Recovery Notice")
def render_wa_modal(matches: list[Match], period: str) -> None:
    m = st.session_state.get("wa_modal")
    if not m:
        return
    from backend.subagents import comms_agent

    live = comms_agent.mode() == "twilio"
    st.markdown(f"**To** {m.supplier_name}, `{wa_number(m)}`")
    st.markdown(f"**Period** {period}")
    st.text_area("Message preview", wa_preview(m, period), height=140, key="wa-preview")
    st.caption(
        f"Template governed by Rule 88D, 30-day remedy window. "
        f"DRC-01C exposure {inr(m.tax * 0.24)} (interest @24% p.a.)"
    )
    st.caption(
        "Send mode: **Twilio WhatsApp API (live)**" if live else
        "Send mode: **simulated** — Twilio keys not configured; the attempt is "
        "still recorded in the DynamoDB audit trail."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm dispatch", type="primary", width="stretch"):
        result = comms_agent.send_recovery_notice(
            period=period, invoice_no=m.register_no, supplier=m.supplier_name,
            phone=wa_number(m), message=wa_preview(m, period),
        )
        if result["ok"]:
            if result["mode"] == "twilio":
                log(f"[A2A] WhatsApp delivered to {m.supplier_name} "
                    f"({wa_number(m)}) · sid {result['message_id']}")
                st.toast("Recovery notice delivered via Twilio WhatsApp API")
            else:
                log(f"[A2A] WhatsApp notice dispatched to {m.supplier_name} "
                    f"({wa_number(m)}) · simulated, recorded in audit trail")
                st.toast("Recovery notice recorded (simulated send)")
        else:
            log(f"[A2A] Dispatch failed for {m.register_no}: {result['detail']}")
            st.error(f"Dispatch failed: {result['detail']}")
        _close_wa_modal()
    if c2.button("Cancel", width="stretch"):
        _close_wa_modal()


def render_agent_log() -> None:
    with st.expander("Agent activity log", expanded=False):
        # One-time events + this rerun's narration, merged by timestamp.
        merged = sorted(st.session_state.get("log", [])
                        + st.session_state.get("run_log", []))
        lines = merged[-_LOG_CAP:]
        if lines:
            st.code("\n".join(lines), language=None)
        else:
            st.caption("No activity yet. Load the demo fixtures or reconcile a dataset.")


def render_dashboard(books: pd.DataFrame, portal: list[PortalRow]) -> None:
    st.session_state["books"] = books
    st.session_state.pop("run_log", None)  # narration is per-rerun
    excel = run_excel_vlookup(books, portal)
    matches = run_recon_pipeline(
        books, portal, use_bedrock=bool(st.session_state.get("use_bedrock"))
    )

    exact = sum(m.tax for m in matches if m.status == "exact")
    rescued = sum(m.tax for m in matches if m.status == "ai")
    risk = sum(m.tax for m in matches if m.status == "missing")
    total = float(books["total_tax"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Invoiced ITC", inr(total))
    c2.metric("Reconciled ITC (Exact)", inr(exact))
    c3.metric("Rescued ITC (AI)", inr(rescued),
              delta=f"+{rescued / total:.1%}" if total else "—")
    c4.metric("ITC at High Risk", inr(risk),
              delta="Rule 88D exposure", delta_color="inverse")

    st.divider()
    render_side_by_side(excel, matches)
    st.divider()
    render_recovery_panel(matches, DEMO_PERIOD)
    st.divider()
    render_full_ledger(matches)
    render_agent_log()
    render_wa_modal(matches, DEMO_PERIOD)


def render_full_ledger(matches: list[Match]) -> None:
    st.markdown("### Reconciliation ledger")
    st.caption("Every classification, with the evidence the agent used.")
    rows = [
        {
            "Books Invoice": m.register_no, "Portal Invoice": m.portal_no,
            "Supplier": m.supplier_name, "GSTIN": m.supplier_gstin,
            "ITC": inr(m.tax), "Status": m.label,
            "Confidence": f"{m.ai_conf}%", "Evidence": m.reason,
        }
        for m in matches
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
#  App shell
# ══════════════════════════════════════════════════════════════════════════
def sidebar() -> None:
    with st.sidebar:
        st.markdown("### Recon-Agent")
        st.caption("Autonomous GST ITC Reconciliation")
        st.markdown(
            "<small>Operates under Section 16(2)(aa) and Rule 88D of the CGST Act</small>",
            unsafe_allow_html=True)
        st.divider()
        st.markdown("#### Data Source")
        books_up = st.file_uploader("Purchase Register (.xlsx)", type=["xlsx"])
        json_up = st.file_uploader("GSTR-2B (.json)", type=["json"])
        if books_up and json_up and st.button("Reconcile uploaded files", type="primary"):
            books = pd.read_excel(books_up)
            payload = json.loads(json_up.read().decode("utf-8"))
            st.session_state["uploads"] = (books, payload)
            log("[AGENT] Uploaded dataset loaded")
        if st.button("Reset to demo fixtures"):
            st.session_state.pop("uploads", None)
            st.rerun()
        st.divider()
        st.markdown("#### Backend")
        use_bedrock = st.toggle("Use AWS Bedrock semantic pass", value=False,
                                help="On = Claude on Bedrock re-identifies corroborated "
                                     "rows. Falls back to the local matcher if AWS is "
                                     "unreachable.")
        if use_bedrock:
            region = (os.environ.get("RECON_AWS_REGION") or os.environ.get("AWS_REGION")
                      or "ap-south-1")
            model = BEDROCK_MODEL_ID.rsplit(".", 1)[-1]
            creds = ("credentials detected" if os.environ.get("AWS_ACCESS_KEY_ID")
                     else "no AWS credentials — will fall back")
            st.caption(f"Bedrock Converse · {model} · {region} · {creds}")
        else:
            st.caption("Local semantic matcher, zero cloud dependency")
        st.session_state["use_bedrock"] = use_bedrock
        st.divider()
        st.markdown("#### Persistence")
        try:
            from backend.db import results as db
            table = db.table_name()
        except Exception:  # noqa: BLE001
            table = None
        st.caption(f"Audit DB: `{table or 'not configured'}`")
        st.caption("Every reconciliation run and dispatch attempt is recorded")
        st.divider()
        st.caption(f"Period fp: `{st.session_state.get('fp', '082026')}`")
        st.caption("AWS First Commit Hackathon, WeMakeDevs")


def main() -> None:
    st.set_page_config(
        page_title="Recon-Agent — GST ITC Reconciliation",
        page_icon="🧾",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """<style>
        .stApp { background: #131A29; color: #E8E4D8; }
        section[data-testid="stSidebar"] { background: #0F1524; }
        div[data-testid="stMetric"] {
            background: #1B2537; border: 1px solid #2C3750;
            border-radius: 2px; padding: 14px 16px;
            font-variant-numeric: tabular-nums;
        }
        h1, h2, h3, h4 { letter-spacing: 0.01em; text-wrap: balance; }
        code { font-variant-numeric: tabular-nums; }
        </style>""", unsafe_allow_html=True)

    st.title("Recon-Agent")
    st.markdown("**Autonomous GST ITC reconciliation for Indian MSMEs**")
    st.caption(
        "Every year ₹45,000 crore of legitimately earned Input Tax Credit goes "
        "unclaimed, because a spreadsheet cannot see past a separator. Section "
        "16(2)(aa) blocks credit unless the supplier files; Recon-Agent finds it, "
        "rescues it, and chases the vendor.")
    st.divider()

    if st.button("Load demo fixtures", type="primary",
                 help="Loads the bundled synthetic purchase register and GSTR-2B"):
        st.session_state.pop("uploads", None)
        st.session_state.pop("wa_modal", None)
        log("[AGENT] Demo fixtures loaded")

    books, portal = load_data()
    sidebar()
    if books is None:
        st.error(
            "Fixtures not found. Run `python fixtures/generate_mock_data.py` first, "
            "or upload your own files in the sidebar."
        )
        st.stop()
    render_dashboard(books, portal)


if __name__ == "__main__":
    main()
