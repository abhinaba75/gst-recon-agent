"""DynamoDB persistence for reconciliation runs and the A2A audit trail.

Backed by the ``recon-agent-results-demo`` table deployed via
``infrastructure/recon-agent-core.yaml`` (pk/sk single-table design):

    pk = "run#<period>"       sk = "<utc iso>#<run id>"   one reconciliation run
    pk = "dispatch#<period>"  sk = "<utc iso>#<invoice>"  one WhatsApp recovery

Every function degrades gracefully: with no table configured or no network,
callers get ``None`` / ``False`` and the UI says so — a persistence outage
must never take the demo down.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # only for type hints; boto3 is imported lazily
    import boto3

_REGION_KEYS = ("RECON_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION")


def table_name() -> str | None:
    """Configured table name, or None when persistence is not configured."""
    name = os.environ.get("RECON_RESULTS_TABLE")
    return name or None


def _client() -> Any:
    import boto3

    region = next((os.environ[k] for k in _REGION_KEYS if os.environ.get(k)), "us-east-1")
    return boto3.client("dynamodb", region_name=region)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id(matches_hash_seed: str) -> str:
    digest = hashlib.sha256(matches_hash_seed.encode()).hexdigest()[:10]
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{digest}"


def persist_run(
    period: str,
    books_count: int,
    portal_count: int,
    matches: list[Any],
    totals: dict[str, float],
) -> str | None:
    """Store one reconciliation run with its full classification ledger.

    ``matches`` items need register_no / portal_no / supplier_name /
    supplier_gstin / tax / status / ai_conf / reason attributes (the app's
    Match dataclass qualifies). Returns the run id, or None on any failure.
    """
    name = table_name()
    if not name:
        return None
    run_id = _run_id(f"{period}|{books_count}|{portal_count}|{len(matches)}|{totals}")
    item = {
        "pk": {"S": f"run#{period}"},
        "sk": {"S": f"{_now_iso()}#{run_id}"},
        "run_id": {"S": run_id},
        "period": {"S": period},
        "books_count": {"N": str(books_count)},
        "portal_count": {"N": str(portal_count)},
        "total_itc": {"N": f"{totals.get('total', 0):.2f}"},
        "reconciled_itc": {"N": f"{totals.get('exact', 0):.2f}"},
        "rescued_itc": {"N": f"{totals.get('ai', 0):.2f}"},
        "risk_itc": {"N": f"{totals.get('risk', 0):.2f}"},
        "results": {"S": json.dumps([
            {
                "register_no": m.register_no,
                "portal_no": m.portal_no,
                "supplier": m.supplier_name,
                "gstin": m.supplier_gstin,
                "tax": round(float(m.tax), 2),
                "status": m.status,
                "ai_conf": int(m.ai_conf),
                "reason": m.reason,
            }
            for m in matches
        ], separators=(",", ":"))},
    }
    try:
        _client().put_item(TableName=name, Item=item)
    except Exception:  # noqa: BLE001 — persistence degrades, the demo must not
        return None
    return run_id


def record_dispatch(
    period: str,
    invoice_no: str,
    supplier: str,
    phone: str | None,
    mode: str,
    message: str,
    provider_message_id: str | None = None,
    error: str | None = None,
) -> bool:
    """Append one recovery notice to the A2A audit trail. True if recorded."""
    name = table_name()
    if not name:
        return False
    item: dict[str, dict[str, str]] = {
        "pk": {"S": f"dispatch#{period}"},
        "sk": {"S": f"{_now_iso()}#{invoice_no}"},
        "invoice_no": {"S": invoice_no},
        "supplier": {"S": supplier},
        "phone": {"S": phone or "unavailable"},
        "mode": {"S": mode},
        "message": {"S": message},
    }
    if provider_message_id:
        item["provider_message_id"] = {"S": provider_message_id}
    if error:
        item["error"] = {"S": error}
    try:
        _client().put_item(TableName=name, Item=item)
    except Exception:  # noqa: BLE001
        return False
    return True


def recent_runs(period: str, limit: int = 5) -> list[dict[str, str]]:
    """Most recent runs for a period, newest first; [] when unavailable."""
    name = table_name()
    if not name:
        return []
    try:
        resp = _client().query(
            TableName=name,
            KeyConditionExpression="pk = :p",
            ExpressionAttributeValues={":p": {"S": f"run#{period}"}},
            ScanIndexForward=False,
            Limit=limit,
        )
    except Exception:  # noqa: BLE001
        return []
    return [
        {
            "run_id": i.get("run_id", {}).get("S", ""),
            "rescued": i.get("rescued_itc", {}).get("N", "0"),
            "risk": i.get("risk_itc", {}).get("N", "0"),
            "at": i.get("sk", {}).get("S", "").split("#")[0],
        }
        for i in resp.get("Items", [])
    ]
