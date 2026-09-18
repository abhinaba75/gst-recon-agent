"""Backend orchestrator — the single seam between dashboard and agent layer.

Today this delegates classification to the tiered cost router and exposes
the helpers the frontend pipeline needs. When the Strands Agents SDK /
Lambda orchestrator lands, it implements this module's functions against
DynamoDB-persisted period data; the Match-shaped contract (§11) does not
change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # keep module importable without AWS deps at import time
    from backend.tools.smart_router import Verdict


def classify_candidate(
    *,
    reg_inv: str,
    portal_inv: str,
    reg_vendor: str,
    portal_vendor: str,
    books_tax: float,
    portal_tax: float,
    books_gstin: str,
    portal_gstin: str,
) -> "Verdict":
    """Tiered classification of one corroborated-or-not candidate pair.

    Thin lazy wrapper so importing the orchestrator never constructs a
    boto3 client (important for Streamlit cold starts and tests).
    """
    from backend.tools.smart_router import dual_engine_reconciliation

    return dual_engine_reconciliation(
        reg_inv=reg_inv,
        portal_inv=portal_inv,
        reg_vendor=reg_vendor,
        portal_vendor=portal_vendor,
        books_tax=books_tax,
        portal_tax=portal_tax,
        books_gstin=books_gstin,
        portal_gstin=portal_gstin,
    )
