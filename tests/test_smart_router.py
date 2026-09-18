#!/usr/bin/env python3
"""Test suite for the tiered cost router (backend/tools/smart_router.py).

Run directly (no pytest needed):  .venv/bin/python tests/test_smart_router.py

The Bedrock layers are exercised with stub clients so the suite is free,
fast and deterministic; the live-path behaviour was verified separately
against real Bedrock (see DOCUMENTATION.md §11).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.tools import smart_router as sr  # noqa: E402

PAIR = dict(
    reg_inv="INV/24-25/081",
    portal_inv="INV-081",
    reg_vendor="Acme Corporation Pvt Ltd",
    portal_vendor="Acme Corp",
    books_tax=18_000.0,
    portal_tax=18_000.0,
    books_gstin="27AABCA1234F1Z5",
    portal_gstin="27AABCA1234F1Z5",
)


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print("== Layer 0: corroboration gate (no model calls, ever) ==")
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("model must not be consulted behind the gate")

    orig = sr.call_bedrock_converse
    sr.call_bedrock_converse = _boom
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "books_tax": 18_000.0,
                                             "portal_tax": 20_000.0})
        check("tax mismatch → UNSAFE, zero model calls", v["status"] == "UNSAFE"
              and v["engine"] == "Gate" and calls["n"] == 0, str(v))
        v = sr.dual_engine_reconciliation(**{**PAIR, "books_gstin": "29AABCA1234F1Z5"})
        check("gstin mismatch → UNSAFE, zero model calls", v["status"] == "UNSAFE",
              str(v))
        v = sr.dual_engine_reconciliation(**{**PAIR, "books_gstin": ""})
        check("blank gstin → UNSAFE (fail-closed)", v["status"] == "UNSAFE", str(v))
    finally:
        sr.call_bedrock_converse = orig

    class _Stub:
        """Scripted Converse client; raises if temperature drifts off 0."""

        def __init__(self, replies):
            self.replies = list(replies)
            self.models: list[str] = []

        def converse(self, **kwargs):
            assert kwargs["inferenceConfig"]["temperature"] == 0.0, "temperature drift"
            self.models.append(kwargs["modelId"])
            return {"output": {"message": {"content":
                    [{"text": self.replies.pop(0)}]}}}

    print("== Layer 1: RapidFuzz (free) ==")
    calls = {"n": 0}

    def _forbidden(*a, **k):
        calls["n"] += 1
        raise RuntimeError("model consulted on a free-tier pair")

    orig = sr.call_bedrock_converse
    sr.call_bedrock_converse = _forbidden
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "reg_inv": "TAX/2026/019",
                                             "portal_inv": "TAX-2026-019",
                                             "reg_vendor": "Zenith Logistics Pvt Ltd",
                                             "portal_vendor": "Zenith Logistics"})
        check("Zenith separators matched free via canonical equality",
              v["engine"] == "RapidFuzz" and v["confidence"] >= 90
              and calls["n"] == 0, str(v))
        v = sr.dual_engine_reconciliation(**{**PAIR, "reg_inv": "BILL-907",
                                             "portal_inv": "INV-2026-907",
                                             "reg_vendor": "Nimbus Traders LLP",
                                             "portal_vendor": "Nimbus Traders",
                                             "books_tax": 7_481.0,
                                             "portal_tax": 7_481.0})
        check("Nimbus serial identity + vendor agreement matched free",
              v["engine"] == "RapidFuzz" and v["status"] == "MATCHED"
              and calls["n"] == 0, str(v))
        v = sr.dual_engine_reconciliation(**{**PAIR, "reg_inv": "INV/24-25/075",
                                             "portal_inv": "INV/24-25/078",
                                             "reg_vendor": "Sunrise Polymers Pvt Ltd",
                                             "portal_vendor": "Sunrise Polymers",
                                             "books_tax": 15_210.0,
                                             "portal_tax": 15_210.0})
        check("92%-similar decoy (different serials) never cleared free",
              v["status"] != "MATCHED" and calls["n"] >= 1, str(v))
    finally:
        sr.call_bedrock_converse = orig

    print("== Layer 1 vendor bar: abbreviation-only vendors escalate ==")
    # Acme's vendor pair scores 61% on token_set — below the 90 bar — so the
    # flagship typo escalates to a paid model. That is the intended economics:
    # the two full-name vendors are free, the hardest case gets real reasoning.
    stub = _Stub(["MATCH"])
    orig_client = sr._client
    sr._client = stub
    try:
        v = sr.dual_engine_reconciliation(**PAIR)
    finally:
        sr._client = orig_client
    check("Acme (61% vendor) escalates to Nova Micro, serial evidence intact",
          v["status"] == "MATCHED" and v["engine"] == "Nova Micro"
          and v["confidence"] == 85 and stub.models == [sr.NOVA_MICRO], str(v))

    print("== Layers 2-3: model tiers via stubbed clients ==")

    # Transposed serial (081 → 810): serial evidence gone, high fuzz band,
    # identical vendor → Nova Micro must decide, Claude must not be called.
    stub = _Stub(["MATCH"])
    orig_client = sr._client
    sr._client = stub
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr._client = orig_client
    check("transposed serial → Nova Micro MATCHED",
          v["status"] == "MATCHED" and v["engine"] == "Nova Micro"
          and v["confidence"] == 85, str(v))
    check("only Nova consulted, temperature pinned",
          stub.models == [sr.NOVA_MICRO], str(stub.models))

    print("== Cost ledger: usage rides on model verdicts ==")
    class _UsageStub(_Stub):
        def converse(self, **kwargs):
            out = super().converse(**kwargs)
            out["usage"] = {"inputTokens": 210, "outputTokens": 5}
            return out

    ustub = _UsageStub(["MATCH"])
    sr._client = ustub
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr._client = orig_client
    check("verdict carries Converse usage for the cost ledger",
          v.get("input_tokens") == 210 and v.get("output_tokens") == 5
          and isinstance(v.get("latency_ms"), int), str(v))

    # Same pair, Nova says MISMATCH → escalation to Claude Sonnet 4.5.
    two = _Stub(["MISMATCH", "MATCH"])
    sr._client = two
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr._client = orig_client
    check("nova mismatch → escalates to Claude Sonnet 4.5",
          v["status"] == "MATCHED" and v["engine"] == "Claude Sonnet 4.5"
          and two.models == [sr.NOVA_MICRO, sr.CLAUDE_SONNET], str(v))

    # Both models decline → UNRECONCILED (never fabricated, never looping).
    declined = _Stub(["MISMATCH", "MISMATCH"])
    sr._client = declined
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr._client = orig_client
    check("honest MISMATCH ×2 → UNRECONCILED",
          v["status"] == "UNRECONCILED" and v["confidence"] == 0, str(v))

    print("== Verdict parsing is strict (NO MATCH is not a match) ==")
    # 'NO MATCH' at Nova must NOT read as matched; it escalates to Sonnet.
    nomatch = _Stub(["NO MATCH", "MATCH"])
    sr._client = nomatch
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr._client = orig_client
    check("'NO MATCH' rejected, escalation still reaches Sonnet",
          v["status"] == "MATCHED" and v["engine"] == "Claude Sonnet 4.5"
          and nomatch.models == [sr.NOVA_MICRO, sr.CLAUDE_SONNET], str(v))

    declined2 = _Stub(["NOT A MATCH", "NO MATCH"])
    sr._client = declined2
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr._client = orig_client
    check("'NOT A MATCH' / 'NO MATCH' both degrade to UNRECONCILED",
          v["status"] == "UNRECONCILED" and v["confidence"] == 0, str(v))

    print("== Degradation ==")
    calls2 = {"n": 0}

    def _fail(*a, **k):
        calls2["n"] += 1
        raise RuntimeError("bedrock unreachable")

    sr.call_bedrock_converse = _fail
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "portal_inv": "INV/24-25/810"})
    finally:
        sr.call_bedrock_converse = orig
    check("nova down → ERROR verdict (never a fake MATCH)",
          v["status"] == "ERROR" and calls2["n"] == 1, str(v))

    print("== Layer 1 quick-pass must not invoke models ==")
    sr.call_bedrock_converse = _boom
    try:
        v = sr.dual_engine_reconciliation(**{**PAIR, "reg_inv": "TAX/2026/019",
                                             "portal_inv": "TAX-2026-019",
                                             "reg_vendor": "Zenith Logistics Pvt Ltd",
                                             "portal_vendor": "Zenith Logistics"})
        check("clean typo pair costs ₹0.00 and 0 model calls",
              v["engine"] == "RapidFuzz", str(v))
    finally:
        sr.call_bedrock_converse = orig

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
