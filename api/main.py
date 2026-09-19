"""FastAPI surface for the React frontend.

The browser never talks to Twilio, Meta or DynamoDB directly — this process
does, reusing the same modules the Streamlit console uses, so there is exactly
one implementation of every rule (E.164 normalisation, provider ladder, audit
trail, mode labelling).

Run:  .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.subagents import comms_agent  # noqa: E402
from backend.db import results as db  # noqa: E402
from backend import assistant  # noqa: E402
from backend import clerk as clerk_auth  # noqa: E402
from backend import intake as intake_engine  # noqa: E402
from backend import oauth  # noqa: E402
from backend import session as sessions  # noqa: E402
from backend import users  # noqa: E402

SNAPSHOT = ROOT / "web" / "src" / "data" / "snapshot.json"

#: The demo documents, used when an operator submits the form with no files —
#: the one-click path for a visitor who has no GST data of their own.
SAMPLE_REGISTER = ROOT / "fixtures" / "sample_purchase_register.xlsx"
SAMPLE_PORTAL = ROOT / "fixtures" / "sample_gstr2b.json"

#: A register for a mid-sized MSME is a few hundred kilobytes. This ceiling is
#: generous and still refuses an upload that would exhaust the worker.
MAX_UPLOAD_BYTES = 24 * 1024 * 1024

app = FastAPI(
    title="Recon-Agent API",
    version="0.1.0",
    description="GST ITC reconciliation engine: snapshot, audit trail, dispatch, assistant.",
)

# The SPA is served from the Vite dev server/proxy in every deployment shape we
# support, so this is a convenience for direct-port development rather than a
# requirement. Credentials are never sent as cookies, so no credentials flag.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    """One sign-in attempt from the login page."""

    email: str
    password: str


class TokenRequest(BaseModel):
    """An opaque session token, as the browser holds it."""

    token: str


class RegisterRequest(BaseModel):
    """One sign-up: a name, an address and a password."""

    email: str
    password: str
    name: str = ""


class CodeRequest(BaseModel):
    """The one-time code an OAuth callback hands to the page."""

    code: str


class ClerkTokenRequest(BaseModel):
    """A Clerk session token, as the hosted card's callback carries it."""

    token: str


class AssistantRequest(BaseModel):
    """One question to the in-app assistant."""

    question: str
    lang: str = "en"


class DispatchRequest(BaseModel):
    """One recovery notice dispatch, as the dialog sends it."""

    model_config = ConfigDict(populate_by_name=True)

    period: str
    invoice_no: str = Field(alias="invoiceNo")
    supplier: str
    message: str
    phone: str | None = None
    email: str | None = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Liveness plus the live provider the comms agent would actually use."""
    return {
        "ok": True,
        "provider": comms_agent.mode(),
        "audit_table": db.table_name(),
        "snapshot_present": SNAPSHOT.exists(),
        "assistant_model": assistant.configured_model(),
        "login_mode": sessions.mode(),
        "account_store": users.store_kind(),
        "signup_open": users.accounts_enabled(),
        "oauth_providers": oauth.live(),
        "clerk": clerk_auth.configured(),
    }


def _origin_of(request: Request) -> str:
    """The origin this request arrived on, proxy headers honoured."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    host = host or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def _return_to(request: Request, candidate: str) -> str:
    """Where the browser may be sent after sign-in.

    An OAuth callback is a redirect, so an attacker-supplied destination would
    be an open redirect. Only this deployment's own origin, or one the operator
    listed in ``RECON_ALLOWED_ORIGINS``, is accepted; anything else falls back
    to the origin the sign-in started from.

    A page served by a proxy that rewrites ``Host`` — this project's own Vite
    dev server sets ``changeOrigin`` — is a legitimate origin that the request
    cannot prove, which is what ``RECON_ALLOWED_ORIGINS`` is for: a local demo
    sets it to the address the page is actually on.
    """
    fallback = _origin_of(request)
    allowed = {
        origin.strip().rstrip("/")
        for origin in (os.environ.get("RECON_ALLOWED_ORIGINS") or "").split(",")
        if origin.strip()
    }
    allowed.add(fallback)
    clean = (candidate or "").strip().rstrip("/")
    if not clean.startswith(("http://", "https://")) or len(clean) > 200:
        return fallback
    return clean if clean in allowed else fallback


@app.get("/api/auth/options")
def auth_options() -> dict[str, Any]:
    """Every sign-in method this deployment can actually offer.

    The login page renders from this reply, so it never shows a provider that
    would fail — and when a provider is unconfigured it names the environment
    variables that would switch it on, for the operator reading the page.
    """
    return {
        "ok": True,
        "login_mode": sessions.mode(),
        "password": True,
        "signup_open": users.accounts_enabled(),
        "account_store": users.store_kind(),
        "accounts": users.count(),
        "demo": sessions.mode() == "demo",
        "demo_email": sessions.DEMO_EMAIL if sessions.mode() == "demo" else None,
        "demo_password": sessions.DEMO_PASSWORD if sessions.mode() == "demo" else None,
        "providers": oauth.available(),
        # The hosted sign-in. `publishable_key` is designed for the browser;
        # the secret key is never echoed, not even as a length.
        "clerk": clerk_auth.status(),
    }


@app.post("/api/auth/register")
def register(request: RegisterRequest) -> dict[str, Any]:
    """Create a password account and sign it in.

    A refusal is one sentence naming what to fix — never which half of an
    existing credential was wrong, and never a stack trace.
    """
    created = users.register(request.email, request.password, request.name)
    if not created["ok"]:
        return {"ok": False, "detail": created["detail"]}
    session = sessions.issue(created["user"], "account")
    return {**session, "detail": f"Account created for {created['user']['email']}."}


@app.get("/api/auth/{provider}/start")
def oauth_start(provider: str, request: Request, return_to: str = "") -> Any:
    """Send the browser to the provider's consent screen."""
    destination = _return_to(request, return_to)
    try:
        url = oauth.authorize_url(
            provider,
            oauth.callback_uri(destination, provider),
            start_origin=destination,
        )
    except oauth.OAuthError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "detail": str(exc), "provider": provider},
        )
    return RedirectResponse(url, status_code=302)


def _apple_name_hint(raw: str) -> str:
    """Flatten the name Apple shares beside the code into one string.

    Apple sends ``{"name": {"firstName": ..., "lastName": ...}}`` once, on first
    consent, and never sends it again. Anything else — absent, malformed, not a
    mapping — reads as "no name", which the account store then fills in from
    the address.
    """
    try:
        parsed = json.loads(raw or "")
    except Exception:  # noqa: BLE001 — a provider fields is never worth a 500
        return ""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("name"), dict):
        return ""
    parts = [str(parsed["name"].get(k) or "").strip() for k in ("firstName", "lastName")]
    return " ".join(part for part in parts if part)


def _finish_sign_in(
    provider: str,
    request: Request,
    code: str,
    state: str,
    error: str,
    name_hint: str = "",
) -> Any:
    """Finish a provider sign-in and hand the page a one-time code.

    The session token itself never travels through the browser's URL bar: it
    would land in history, in a referrer header and in an access log. The page
    swaps the code for the token with one POST, once.

    Both callback methods below end here, so a provider that posts its answer
    back and one that appends it to the query cannot drift apart.
    """
    # Back to the app's root: it is the one path a static host always serves.
    # The origin the sign-in started from is preferred over this request's own,
    # because a proxy that rewrites Host makes this one the engine's address
    # rather than the page's. It was validated against the allow-list before the
    # state was issued, so it is trusted here.
    back = _return_to(request, "")
    try:
        attempt: dict[str, Any] | None = oauth.consume_state(state)
    except oauth.OAuthError:
        attempt = None
    if attempt and attempt.get("start_origin"):
        back = str(attempt["start_origin"])
    back += "/"

    if error:
        # The provider's own word for why it came back empty-handed, shown as-is.
        return RedirectResponse(f"{back}?auth_error={quote(error)}", status_code=302)
    if attempt is None:
        return RedirectResponse(
            f"{back}?auth_error={quote('This sign-in attempt has expired. Please start again.')}",
            status_code=302,
        )
    try:
        profile = oauth.exchange(
            provider,
            code,
            attempt["redirect_uri"],
            nonce=attempt.get("nonce", ""),
            name_hint=name_hint,
        )
    except oauth.OAuthError as exc:
        return RedirectResponse(f"{back}?auth_error={quote(str(exc))}", status_code=302)

    linked = users.upsert_identity(
        profile["provider"], profile["sub"], profile["email"], profile["name"]
    )
    if not linked["ok"]:
        return RedirectResponse(
            f"{back}?auth_error={quote(linked['detail'])}", status_code=302
        )

    session = sessions.issue(linked["user"], "account")
    login_code = oauth.issue_code(session["token"], session["user"])
    return RedirectResponse(
        f"{back}?auth_code={login_code}&provider={profile['provider']}",
        status_code=302,
    )


@app.get("/api/auth/{provider}/callback", name="oauth_callback")
def oauth_callback(
    provider: str,
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
) -> Any:
    """Finish a sign-in for a provider that appends the code to the redirect."""
    return _finish_sign_in(provider, request, code, state, error)


@app.post("/api/auth/{provider}/callback", name="oauth_callback_form")
async def oauth_callback_form(
    provider: str,
    request: Request,
    code: str = Form(""),
    state: str = Form(""),
    error: str = Form(""),
    user: str = Form(""),
) -> Any:
    """Finish a sign-in for a provider that posts its answer back.

    Apple needs ``response_mode=form_post`` as soon as the request asks for the
    email scope, so this is not another spelling of the GET above — it is the
    only way an Apple sign-in can arrive.
    """
    return _finish_sign_in(
        provider, request, code, state, error, _apple_name_hint(user)
    )


@app.post("/api/auth/exchange")
def oauth_exchange(request: CodeRequest) -> dict[str, Any]:
    """Swap the callback's one-time code for the session the page will hold."""
    try:
        record = oauth.redeem_code(request.code)
    except oauth.OAuthError as exc:
        return {"ok": False, "detail": str(exc)}
    found = sessions.validate(record["token"])
    if not found:
        return {"ok": False, "detail": "That session has already ended."}
    return {
        "ok": True,
        "mode": found["mode"],
        "source": found["source"],
        "token": record["token"],
        "user": record["user"],
        "expires_in": found["expires_in"],
    }


@app.post("/api/auth/clerk")
def clerk_exchange(request: ClerkTokenRequest) -> dict[str, Any]:
    """Swap a verified Clerk session for one of this deployment's sessions.

    The browser hands over the token Clerk's hosted card produced; this checks
    it against Clerk's own signing keys, the issuer and the allowed origins,
    then reads the profile from Clerk's Backend API. What lands in the account
    store is the same record every other sign-in creates — a Clerk account and
    a password account with the same address are one workspace, exactly as
    with Google and GitHub.
    """
    try:
        profile = clerk_auth.identity(request.token)
    except clerk_auth.ClerkError as exc:
        return {"ok": False, "detail": str(exc)}
    if not profile.get("email"):
        return {
            "ok": False,
            "detail": (
                "The sign-in did not share an email address, which this "
                "deployment needs to identify you."
            ),
        }
    linked = users.upsert_identity(
        profile["provider"], profile["sub"], profile["email"], profile["name"]
    )
    if not linked["ok"]:
        return {"ok": False, "detail": linked["detail"]}
    return sessions.issue(linked["user"], "account")


@app.post("/api/me")
def me(request: TokenRequest) -> dict[str, Any]:
    """The account behind a live token: who, how they signed in, where from."""
    found = sessions.validate(request.token)
    if not found:
        return {"ok": False}
    email = found["user"].get("email", "")
    return {
        "ok": True,
        "user": users.find(email) or found["user"],
        "mode": found["mode"],
        "source": found["source"],
        "account_store": users.store_kind(),
    }


@app.post("/api/login")
def login(request: LoginRequest) -> dict[str, Any]:
    """Verify credentials server-side and hand back an opaque session token.

    In demo mode (no RECON_UI_EMAIL / RECON_UI_PASSWORD configured) the
    documented demo pair is accepted and the reply says ``mode="demo"``, so
    the page can state that plainly rather than implying real accounts exist.
    """
    return sessions.login(request.email, request.password)


@app.post("/api/session")
def session_state(request: TokenRequest) -> dict[str, Any]:
    """Is this token still live? Returns the user it belongs to."""
    found = sessions.validate(request.token)
    if not found:
        return {"ok": False}
    return {"ok": True, **found}


@app.post("/api/logout")
def logout(request: TokenRequest) -> dict[str, Any]:
    """Drop a session. Idempotent: signing out twice is still signed out."""
    return {"ok": True, "dropped": sessions.logout(request.token)}


@app.post("/api/assistant")
def ask(request: AssistantRequest) -> dict[str, Any]:
    """Answer one question about the app or the reconciliation.

    Two sources, and the reply always names the one that answered: a Bedrock
    model when the operator has configured one, otherwise the built-in guide.
    The assistant never claims a delivery, a figure or a deadline it cannot
    support, and a failure degrades to the guide rather than to an error page.
    """
    return assistant.answer(request.question, request.lang)


@app.get("/api/snapshot")
def snapshot() -> dict[str, Any]:
    """The engine snapshot the page renders.

    These figures come from ``scripts/export_snapshot.py``, which runs the real
    reconciliation. Re-run it after changing fixtures or engine behaviour; the
    API only serves what the engine produced.
    """
    if not SNAPSHOT.exists():
        return {"error": "snapshot not exported", "hint": "python scripts/export_snapshot.py"}
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@app.post("/api/intake")
async def intake_submit(
    register: UploadFile | None = File(default=None),
    portal: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    """Reconcile submitted documents and answer with a snapshot.

    Submitting with no files runs the bundled sample documents, which is how a
    visitor with no GST data sees the product work. The files are read in
    memory: nothing is written to disk, so the page can promise that.

    A document the engine cannot read comes back as ``ok=false`` with one
    sentence naming what to fix — never as a stack trace, and never as a
    partially-read register that would under-claim the operator's credit.
    """
    try:
        if register is None and portal is None:
            snapshot, warnings = intake_engine.snapshot_from_files(
                SAMPLE_REGISTER.read_bytes(),
                SAMPLE_PORTAL.read_bytes(),
                register_name="sample_purchase_register.xlsx",
                portal_name="sample_gstr2b.json",
            )
            return {
                "ok": True,
                "demo": True,
                "snapshot": snapshot,
                "warnings": warnings,
                "detail": "Reconciled the sample purchase register against the sample GSTR-2B.",
            }

        if register is None or portal is None:
            return {
                "ok": False,
                "detail": (
                    "Both documents are needed: the purchase register (Excel or CSV) "
                    "and the GSTR-2B file (JSON) for the same period."
                ),
            }

        register_bytes = await register.read()
        portal_bytes = await portal.read()
        for upload, size in ((register, len(register_bytes)), (portal, len(portal_bytes))):
            if size > MAX_UPLOAD_BYTES:
                return {
                    "ok": False,
                    "detail": f"{upload.filename} is larger than 24 MB, which this page will not accept.",
                }

        snapshot, warnings = intake_engine.snapshot_from_files(
            register_bytes,
            portal_bytes,
            register_name=register.filename or "",
            portal_name=portal.filename or "",
        )
        return {
            "ok": True,
            "demo": False,
            "snapshot": snapshot,
            "warnings": warnings,
            "detail": (
                f"Reconciled {snapshot['counts']['books']} purchase bills against "
                f"{snapshot['counts']['portal']} GSTR-2B entries for {snapshot['period']}."
            ),
        }
    except intake_engine.IntakeError as exc:
        return {"ok": False, "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 — the reply must stay readable
        return {
            "ok": False,
            "detail": (
                "The reconciliation could not be completed "
                f"({type(exc).__name__}). The documents were not changed; "
                "check that both files are for the same period."
            ),
        }


@app.get("/api/runs")
def runs(period: str = "August 2026", limit: int = 8) -> dict[str, Any]:
    """Recent reconciliation runs from the DynamoDB audit trail ([] if absent)."""
    return {"runs": db.recent_runs(period, limit=limit)}


@app.post("/api/dispatch")
def dispatch(request: DispatchRequest) -> dict[str, Any]:
    """Send one recovery notice through the comms agent's provider ladder.

    The agent never raises: a provider failure comes back as ``ok=false`` with
    the reason, and the attempt is written to the audit trail either way — the
    browser must not be able to report a delivery that did not happen.
    """
    result = comms_agent.send_recovery_notice(
        period=request.period,
        invoice_no=request.invoice_no,
        supplier=request.supplier,
        phone=request.phone,
        email=request.email,
        message=request.message,
    )
    return {
        "ok": result["ok"],
        "mode": result["mode"],
        "detail": result["detail"],
        "message_id": result["message_id"],
    }
