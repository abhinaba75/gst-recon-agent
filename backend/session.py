"""Workspace sessions for the web app.

The browser holds an opaque token and nothing else; the engine decides whether
that token is still valid. Three ways a token is issued, and every reply says
which one was used:

* ``operator`` — the single account configured with ``RECON_UI_EMAIL`` /
  ``RECON_UI_PASSWORD``. This is the production shape for one MSME: point it at
  their operator login, or front the deployment with SSO.
* ``account`` — a password account created on this deployment (or an OAuth
  identity), verified by :mod:`backend.users`.
* ``demo`` — nothing is configured and no account matched, so the documented
  demo pair is accepted and the page says out loud that it is a demo workspace.
  A hackathon build that silently shipped a hard-coded password would be worse
  than one that admits what it is.

Tokens live in this process with an expiry. That is honest for a single-worker
deployment, and it is why the module says so instead of implying a session
store — a restart clears every session, and the SPA re-validates on load.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

from backend import users

DEMO_EMAIL = "demo@recon-agent.in"
DEMO_PASSWORD = "demo-88d"

# Sessions outlive a demo, not a day.
TTL_SECONDS = 8 * 60 * 60

_sessions: dict[str, dict[str, Any]] = {}


def credentials() -> tuple[str, str] | None:
    """The configured operator account, or None when running in demo mode."""
    email = (os.environ.get("RECON_UI_EMAIL") or "").strip()
    password = os.environ.get("RECON_UI_PASSWORD") or ""
    if email and password:
        return email, password
    return None


def mode() -> str:
    return "configured" if credentials() else "demo"


def _matches(given: str, expected: str) -> bool:
    """Constant-time comparison; a login form is exactly where that matters."""
    try:
        return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))
    except Exception:  # noqa: BLE001 — never let a comparison raise
        return False


def issue(
    user: dict[str, Any],
    source: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Mint a session for an already-verified identity.

    Used by the OAuth callback and by the account paths below, so every way in
    ends in one session record with one shape: ``user``, ``source``, ``mode``,
    ``expires_at``.
    """
    token = token or secrets.token_urlsafe(24)
    record = {
        "user": user,
        "source": source,
        "mode": mode(),
        "expires_at": time.time() + TTL_SECONDS,
    }
    _sessions[token] = record
    return {
        "ok": True,
        "mode": record["mode"],
        "source": source,
        "token": token,
        "user": user,
        "expires_in": TTL_SECONDS,
    }


def login(email: str, password: str) -> dict[str, Any]:
    """Verify one sign-in. Never raises.

    The operator account is checked first (it is the deployment's own login),
    then the account store, then the demo pair — and only when nothing is
    configured at all.
    """
    given_email = (email or "").strip()
    if not given_email or not password:
        return {"ok": False, "mode": mode(), "detail": "email and password are required"}

    configured = credentials()
    if configured and _matches(given_email, configured[0]) and _matches(password, configured[1]):
        return issue(users.ensure_operator(configured[0]), "operator")

    account = users.authenticate(given_email, password)
    if account["ok"]:
        return issue(account["user"], "account")

    # The documented demo pair stops working the moment a real account exists:
    # a deployment with users must not keep accepting a published password.
    if (
        not configured
        and users.count() == 0
        and _matches(given_email, DEMO_EMAIL)
        and _matches(password, DEMO_PASSWORD)
    ):
        return issue({"email": DEMO_EMAIL, "name": "Demo", "provider": "demo"}, "demo")

    # One message for every failure on purpose: saying which half was wrong
    # tells an attacker which half they already have.
    return {"ok": False, "mode": mode(), "detail": "credentials did not match"}


def validate(token: str) -> dict[str, Any] | None:
    """The user behind a live token, or None."""
    record = _sessions.get(token or "")
    if not record:
        return None
    if record["expires_at"] < time.time():
        _sessions.pop(token, None)
        return None
    return {
        "user": record["user"],
        "mode": record["mode"],
        "source": record.get("source", ""),
        "expires_in": int(record["expires_at"] - time.time()),
    }


def logout(token: str) -> bool:
    """Drop a session. True when something was actually dropped."""
    return _sessions.pop(token or "", None) is not None


def active_sessions() -> int:
    """Live session count — useful for tests and for an operator."""
    now = time.time()
    return sum(1 for s in _sessions.values() if s["expires_at"] >= now)


def reset_for_tests() -> None:
    """Drop every session (tests only)."""
    _sessions.clear()
