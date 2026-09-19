"""Assistant for the web app: questions about this product and GST credit.

Two sources, in order, and the caller is always told which one answered:

1. A Bedrock Converse call, used only when ``RECON_ASSISTANT_MODEL`` is set to
   a model id the account can invoke. Nothing is attempted otherwise: with no
   model configured a call would spend seconds failing and then answer from
   the guide anyway, which is dishonest about how long it took and wasteful.
2. The shared guide in ``web/src/data/guide.json`` — the same file the browser
   matches against when the engine is unreachable, so there is exactly one set
   of answers rather than two that drift.

Invariants: this module never raises (a broken assistant must not take the page
down), and it never presents a guide answer as a model answer.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GUIDE_PATH = ROOT / "web" / "src" / "data" / "guide.json"
SNAPSHOT_PATH = ROOT / "web" / "src" / "data" / "snapshot.json"

DEFAULT_MODEL = "amazon.nova-lite-v1:0"

NO_ANSWER: dict[str, str] = {
    "en": "I do not have that in the built-in guide. Try asking about the four "
          "figures, a supplier status, Rule 88D, or how to send a recovery notice.",
    "hi": "यह बिल्ट-इन गाइड में नहीं है। चार आँकड़ों, किसी विक्रेता की स्थिति, "
          "Rule 88D, या रिकवरी नोटिस भेजने के बारे में पूछें।",
}

_client = None


def configured_model() -> str | None:
    """The model id the operator opted into, or None."""
    return (os.environ.get("RECON_ASSISTANT_MODEL") or "").strip() or None


def _get_client():
    """Lazy bedrock-runtime client with short timeouts for an interactive path."""
    global _client
    if _client is None:
        import boto3  # deferred so the module imports without AWS deps
        from botocore.config import Config

        region = (
            os.environ.get("RECON_AWS_REGION")
            or os.environ.get("AWS_REGION")
            or "us-east-1"
        )
        _client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=3,
                read_timeout=12,
                retries={"max_attempts": 0},
            ),
        )
    return _client


def _inr(amount: Any) -> str:
    """₹ with Indian digit grouping: 1,07,971 rather than 107,971."""
    try:
        rounded = str(abs(int(round(float(amount)))))
    except (TypeError, ValueError):
        return "₹0"
    if len(rounded) <= 3:
        grouped = rounded
    else:
        head, tail = rounded[:-3], rounded[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        grouped = f"{head},{tail}"
    return f"₹{grouped}"


def _facts() -> dict[str, str]:
    """Fill placeholders from the snapshot the page itself renders."""
    try:
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — an absent snapshot must not break answers
        return {}
    totals = snap.get("totals", {})
    counts = snap.get("counts", {})
    return {
        "period": str(snap.get("period", "this period")),
        "bills": str(counts.get("books", "—")),
        "portal": str(counts.get("portal", "—")),
        "missing_count": str(counts.get("missing", "—")),
        "recovered_count": str(counts.get("rescued", "—")),
        "total": _inr(totals.get("total")),
        "rescued": _inr(totals.get("rescued")),
        "risk": _inr(totals.get("risk")),
        "write_off": _inr(totals.get("write_off")),
    }


def _render(text: str, facts: dict[str, str]) -> str:
    """Replace {{placeholders}}; an unknown placeholder stays visible rather
    than silently turning into 'None' in front of a user."""
    if not facts:
        return text
    return re.sub(r"\{\{(\w+)\}\}", lambda m: facts.get(m.group(1), m.group(0)), text)


def guide_entries() -> list[dict[str, Any]]:
    try:
        return json.loads(GUIDE_PATH.read_text(encoding="utf-8")).get("entries", [])
    except Exception:  # noqa: BLE001
        return []


def match(question: str) -> dict[str, Any] | None:
    """Best guide entry by keyword weight, or None when nothing applies.

    A question is scored by the length of the keywords it contains, so a
    specific term ("rule 88d") outranks a generic one ("notice") instead of the
    entry that merely happens to appear first in the file.
    """
    text = (question or "").lower()
    if not text.strip():
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for entry in guide_entries():
        score = sum(len(k) for k in entry.get("keywords", []) if k.lower() in text)
        if score > best_score:
            best, best_score = entry, score
    return best


def guide_answer(question: str, lang: str = "en") -> str | None:
    entry = match(question)
    if entry is None:
        return None
    text = entry.get(lang) or entry.get("en") or ""
    return _render(text, _facts()) or None


def _system_prompt(lang: str) -> str:
    """Ground the model in the same guide, and bound what it may claim."""
    facts = _facts()
    lines = [
        "You are the assistant inside Recon-Agent, a GST input-tax-credit",
        "reconciliation tool for Indian MSMEs. Answer only from the material",
        "below and from the reconciliation facts. If the material does not",
        "cover the question, say so plainly and suggest one of: the four",
        "figures, a supplier status, Rule 88D, Section 16(2)(aa), or how to",
        "send a recovery notice. Never invent a figure, a GSTIN, a supplier",
        "name or a legal deadline. You are not a lawyer or a tax adviser; say",
        "so when the question is about a filing decision. Two to four short",
        "sentences. Answer in the language with code '" + (lang or "en") + "'.",
        "",
        "Reconciliation facts for the period:",
        " ".join(f"{k}={v}" for k, v in sorted(facts.items())) or "(unavailable)",
        "",
        "Reference material:",
    ]
    for entry in guide_entries():
        body = _render(entry.get("en", ""), facts)
        lines.append(f"- {entry.get('id')}: {body}")
    return "\n".join(lines)


def _model_answer(question: str, lang: str) -> str | None:
    model = configured_model()
    if not model:
        return None
    response = _get_client().converse(
        modelId=model,
        system=[{"text": _system_prompt(lang)}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 400},
    )
    text = response["output"]["message"]["content"][0]["text"].strip()
    return text or None


def answer(question: str, lang: str = "en") -> dict[str, Any]:
    """Answer one question. Never raises; always names the source."""
    q = (question or "").strip()
    if not q:
        return {"ok": False, "source": "none", "answer": NO_ANSWER.get(lang, NO_ANSWER["en"])}

    model = configured_model()
    if model:
        try:
            text = _model_answer(q, lang)
        except Exception as exc:  # noqa: BLE001 — fall back, and say which source
            text = None
            failure = f"{type(exc).__name__}: {exc}"
        else:
            failure = None
        if text:
            return {"ok": True, "source": "model", "model": model, "answer": text}
    else:
        failure = None

    rendered = guide_answer(q, lang)
    if rendered:
        entry = match(q) or {}
        result: dict[str, Any] = {
            "ok": True,
            "source": "guide",
            "topic": entry.get("id"),
            "answer": rendered,
        }
        if failure:
            result["model_error"] = failure
        return result

    result = {"ok": False, "source": "none", "answer": NO_ANSWER.get(lang, NO_ANSWER["en"])}
    if failure:
        result["model_error"] = failure
    return result
