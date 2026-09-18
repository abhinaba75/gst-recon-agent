"""Tiered cost router — the cascade that keeps Bedrock bills in the pennies.

Layer 1  RapidFuzz        ₹0.00        exact + minor separator/punctuation typos
Layer 2  Amazon Nova Micro  $0.035 / 1M  moderate structural typos, abbreviations
Layer 3  Claude Sonnet 4.5  $3.00 / 1M   severe discrepancies needing reasoning

Invariants (DOCUMENTATION.md §11.1 — what makes this defensible):
- The corroboration gate runs FIRST and fails closed: a candidate pair whose
  tax differs by more than ₹2 or whose GSTINs disagree is returned UNSAFE
  without any model call. The models re-identify rows; they never re-price
  or re-attribute them.
- temperature is pinned to 0.0 so the models cannot get creative about money.
- Model IDs are the ACTIVE us-east-1 Bedrock IDs as of 2026-09; the legacy
  claude-3-5-sonnet/haiku IDs are end-of-life and were replaced.
- Every Bedrock failure degrades to an explicit ERROR verdict; a crashed
  layer never fabricates a MATCH.
"""

from __future__ import annotations

import os
import re
import time
from typing import TypedDict

from rapidfuzz import fuzz

# ACTIVE Bedrock model IDs (verified via list_foundation_models, us-east-1).
NOVA_MICRO: str = "amazon.nova-micro-v1:0"
CLAUDE_SONNET: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"

# Gate tolerance mirrors app.py: GSTN rounding differences are ≤ ₹2.
TAX_TOLERANCE: float = 2.0

# Layer thresholds. Layer 1 is evidence-based, not a raw cut-off: canonical
# invoice equality (separator/case typos) or trailing-serial identity backed
# by vendor-name agreement. Raw high ratios alone are NOT sufficient — two
# different invoices from the same vendor (…/075 vs …/078) score 92% similar
# yet must never match for free. The 90% vendor bar keeps the demo's
# abbreviation-only vendor ("Acme Corporation Pvt Ltd" vs "Acme Corp", 61%)
# out of Layer 1 — that pair is Layer 2's job, on real Converse calls.
L1_VENDOR_RATIO: int = 90
L2_FUZZ_RATIO: int = 60

# Confidences the dashboard renders per engine. Layer 1 derives its figure
# from measured similarity; the model layers report fixed conservative
# figures because their reply is a binary judgement, not a score.
L2_CONFIDENCE: int = 85
L3_CONFIDENCE: int = 75


class Verdict(TypedDict):
    status: str      # MATCHED | UNSAFE | UNRECONCILED | ERROR
    confidence: int  # 0-100, 0 unless matched
    engine: str      # RapidFuzz | Nova Micro | Claude Sonnet 4.5 | Gate | Exhausted
    detail: str      # audit-trail evidence


_client = None  # reused across calls; one boto3 client per process


def _get_client():
    """Lazy, process-wide bedrock-runtime client (keeps imports cheap)."""
    global _client
    if _client is None:
        import boto3  # deferred so the module imports without AWS deps

        region = (
            os.environ.get("RECON_AWS_REGION")
            or os.environ.get("AWS_REGION")
            or "us-east-1"
        )
        _client = boto3.client("bedrock-runtime", region_name=region)
    return _client


def _extract_usage(response: dict) -> dict:
    """Pull Converse token usage out of a response; {} when absent."""
    try:
        return response.get("usage", {})
    except Exception:  # noqa: BLE001 — absent usage must never break matching
        return {}


# Populated by call_bedrock_converse; read immediately after by _model_verdict.
_last_usage: dict = {}


def call_bedrock_converse(model_id: str, prompt: str) -> str:
    """Stateless, deterministic (temperature 0) Converse call; reply uppercased."""
    response = _get_client().converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 16},
    )
    global _last_usage
    _last_usage = _extract_usage(response)
    return response["output"]["message"]["content"][0]["text"].strip().upper()


def _model_verdict(model_id: str, model_name: str, prompt: str,
                   confidence: int) -> Verdict:
    """Ask one model; translate the reply into a Verdict.

    Only a bare ``MATCH`` counts as matched — ``NO MATCH``, ``NOT A MATCH``,
    ``MISMATCH`` or any verbose reply degrades to UNRECONCILED. A substring
    check would read "NO MATCH" as a match and defeat the corroboration
    gate's whole purpose in the production seam.

    The reply may carry cost attributes (input_tokens / output_tokens /
    latency_ms — emitted by the JSON matcher when the caller asks for them);
    they are copied onto the Verdict for the per-run cost ledger.

    Cascade contract on failure: a model ERROR stops the cascade (infrastructure
    fault, not a verdict; escalating would double spend and latency on an
    outage path and hammer the premium tier during throttling). The caller
    surfaces ERROR; a rerun retries it.
    """
    started = time.perf_counter()
    try:
        reply = call_bedrock_converse(model_id, prompt)
    except Exception as exc:  # noqa: BLE001 — degradation, never a fake MATCH
        return Verdict(status="ERROR", confidence=0, engine=model_name,
                       detail=f"{type(exc).__name__}: {exc}")
    matched = re.fullmatch(r"MATCH", reply) is not None
    usage = _last_usage or {}
    v = Verdict(
        status="MATCHED" if matched else "UNRECONCILED",
        confidence=confidence if matched else 0,
        engine=model_name,
        detail=f"model replied {reply!r}",
    )
    if usage:
        v["input_tokens"] = int(usage.get("inputTokens", 0))
        v["output_tokens"] = int(usage.get("outputTokens", 0))
        v["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return v


def dual_engine_reconciliation(
    *,
    reg_inv: str,
    portal_inv: str,
    reg_vendor: str,
    portal_vendor: str,
    books_tax: float,
    portal_tax: float,
    books_gstin: str,
    portal_gstin: str,
) -> Verdict:
    """Classify one candidate pair through the cost cascade.

    The tax/GSTIN gate is the caller's contract: candidates that fail it are
    unsafe regardless of how similar the strings look — a model is never
    asked to reconcile two different amounts of money.
    """
    gate_ok = (
        abs(round(float(books_tax), 2) - round(float(portal_tax), 2)) <= TAX_TOLERANCE
        and _norm(books_gstin) == _norm(portal_gstin)
        and bool(_norm(books_gstin))
    )
    if not gate_ok:
        return Verdict(
            status="UNSAFE", confidence=0, engine="Gate",
            detail=f"tax {books_tax} vs {portal_tax}; "
                   f"gstin {books_gstin!r} vs {portal_gstin!r}",
        )

    inv_ratio = int(fuzz.token_sort_ratio(reg_inv.upper(), portal_inv.upper()))
    vendor_ratio = int(fuzz.token_set_ratio(reg_vendor.upper(), portal_vendor.upper()))

    # ── Layer 1: RapidFuzz, ₹0.00, microseconds ────────────────────────────
    # Evidence rules, verified against the demo fixtures: a raw ≥90 invoice
    # ratio would also clear two DIFFERENT same-vendor invoices (…/075 vs
    # …/078, 92% similar) for free — trailing-serial identity would not.
    if _canon_inv(reg_inv) == _canon_inv(portal_inv):
        return Verdict(
            status="MATCHED", confidence=max(inv_ratio, 90), engine="RapidFuzz",
            detail="canonical invoice equality (separator/case typos only)",
        )
    if _serial(reg_inv) and _serial(reg_inv) == _serial(portal_inv) \
            and vendor_ratio >= L1_VENDOR_RATIO:
        return Verdict(
            status="MATCHED", confidence=min(60 + int(vendor_ratio * 0.35), 99),
            engine="RapidFuzz",
            detail=f"trailing serial {_serial(reg_inv)} identical on both ledgers, "
                   f"vendor agreement {vendor_ratio}% (GSTIN + tax gated)",
        )

    prompt = (
        f"Are these two invoices the exact same transaction? "
        f"Internal Ledger: Invoice '{reg_inv}' from vendor '{reg_vendor}'. "
        f"Portal Ledger: Invoice '{portal_inv}' from vendor '{portal_vendor}'. "
        f"Reply strictly with 'MATCH' or 'MISMATCH'."
    )

    # ── Layer 2: Nova Micro, $0.035 / 1M, milliseconds ─────────────────────
    if inv_ratio >= L2_FUZZ_RATIO or vendor_ratio >= L2_FUZZ_RATIO:
        verdict = _model_verdict(NOVA_MICRO, "Nova Micro", prompt, L2_CONFIDENCE)
        if verdict["status"] != "UNRECONCILED":
            return verdict

    # ── Layer 3: Claude Sonnet 4.5, $3 / 1M, deep reasoning ────────────────
    return _model_verdict(CLAUDE_SONNET, "Claude Sonnet 4.5", prompt, L3_CONFIDENCE)


# Published per-1M-input-token prices (us-east-1, 2026-09) for the demo's
# cost narration; Converse input here is ~200 tokens, so each model call is
# a rounding error — the story is the ratio, not the rupee.
ENGINE_COST: dict[str, float] = {
    "RapidFuzz": 0.0,
    "Nova Micro": 0.035,
    "Claude Sonnet 4.5": 3.0,
    "Local matcher": 0.0,
}


def _norm(s: str) -> str:
    """GSTIN comparison form: uppercase, alphanumeric only."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _canon_inv(s: str) -> str:
    """Invoice-number comparison form: strips separator/case noise.

    'INV/24-25/081' → 'INV2425081'; 'INV-081' → 'INV081' (intentionally NOT
    equal — the financial-year fragment differs, so the serial rule below
    decides those).
    """
    return _norm(s)


def _serial(s: str) -> str:
    """Trailing numeral group — the human-meaningful part of an invoice no."""
    found = re.findall(r"\d+", s or "")
    return found[-1] if found else ""
