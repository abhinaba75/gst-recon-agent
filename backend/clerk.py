"""Clerk sign-in: verify what the hosted service issues.

Clerk is the one sign-in provider whose settings live entirely in its
dashboard: accounts, social connections, password reset, email verification,
attack protection. This module is deliberately the smallest honest bridge to
it — the flow is Clerk's own hosted page, the session token is a standard
RS256 JWT, and this deployment's only job is to decide whether to believe it.

Verification, and why it is shaped this way:

* The signing keys come from Clerk's JWKS document
  (``https://<frontend-api>/.well-known/jwks.json``) and are cached for an
  hour. JWKS is served over TLS by Clerk itself, so the trust decision here is
  ``iss`` + ``azp``, not hand-pinned key material.
* The token's ``iss`` must be this deployment's own Clerk Frontend API URL,
  which comes from ``RECON_CLERK_ISSUER`` — a value the operator set, not one
  the request supplied. A token from somebody else's Clerk project cannot
  name that issuer.
* The token's ``azp`` must be an origin the deployment has listed in
  ``RECON_CLERK_ALLOWED_ORIGINS`` (default: the SPA's own origin in
  ``RECON_ALLOWED_ORIGINS``, falling back to ``http://localhost:5173``).
* ``exp`` and ``nbf`` are checked against the clock, with a little slack,
  because workers and browsers disagree about "now".

The profile is read from Clerk's Backend API with the secret key, not from an
unverified client claim: ``email``, ``name``, and Clerk's user id. The account
that lands in :mod:`backend.users` is the same shape every other sign-in
produces, so password accounts and Clerk accounts link on the address exactly
like Google and GitHub identities do.
"""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlparse

import requests

#: How long a JWKS document stays trusted before it is fetched again. Clerk
#: rotates keys by publishing a new ``kid``; the cache is short so a rotation
#: is picked up without a redeploy.
JWKS_TTL_SECONDS = 60 * 60

#: Clock slack for ``exp``/``nbf`` between this worker and Clerk's signer.
LEEWAY_SECONDS = 60

#: Network ceiling for the JWKS fetch and the Backend API call: a slow Clerk
#: must not hold a worker while an operator waits at the sign-in card.
TIMEOUT = 10

_jwks: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


class ClerkError(RuntimeError):
    """One readable sentence for the sign-in card, never a stack trace."""


# ── configuration ───────────────────────────────────────────────────────────


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def issuer() -> str:
    """This deployment's Clerk Frontend API URL, or "" when not configured."""
    raw = _env("RECON_CLERK_ISSUER").rstrip("/")
    if not raw:
        return ""
    if not raw.startswith("https://"):
        return ""
    return raw


def secret_key() -> str:
    """The Clerk secret key (``sk_test_…`` / ``sk_live_…``), or ""."""
    return _env("RECON_CLERK_SECRET_KEY")


def publishable_key() -> str:
    """The Clerk publishable key (``pk_…``), for the browser's ClerkProvider."""
    return _env("RECON_CLERK_PUBLISHABLE_KEY")


def allowed_origins() -> list[str]:
    """Origins a session token's ``azp`` may name."""
    origins: list[str] = []
    for name in ("RECON_CLERK_ALLOWED_ORIGINS", "RECON_ALLOWED_ORIGINS"):
        for origin in (_env(name)).split(","):
            clean = origin.strip().rstrip("/")
            if clean and clean not in origins:
                origins.append(clean)
    if not origins:
        origins.append("http://localhost:5173")
    return origins


def configured() -> bool:
    """True when the issuer and the secret key are both set."""
    return bool(issuer() and secret_key())


def missing_env() -> list[str]:
    """The variables an operator still has to set — named, not guessed."""
    out: list[str] = []
    if not _env("RECON_CLERK_ISSUER"):
        out.append("RECON_CLERK_ISSUER")
    if not _env("RECON_CLERK_SECRET_KEY"):
        out.append("RECON_CLERK_SECRET_KEY")
    return out


def unconfigured_message() -> str:
    """One sentence naming what would switch Clerk sign-in on."""
    names = missing_env()
    message = "Clerk sign-in is not configured on this deployment."
    if names:
        message += f" Set {', '.join(names)} to enable it."
    return message


def status() -> dict[str, Any]:
    """What the sign-in card and ``/api/auth/options`` may say about Clerk.

    The publishable key is safe to publish (Clerk designed it for the browser);
    the secret key never leaves this process, not even as a length.
    """
    return {
        "configured": configured(),
        "publishable_key": publishable_key(),
        "issuer": issuer() or None,
        "allowed_origins": allowed_origins() if configured() else [],
        "missing": missing_env(),
        "docs": "https://dashboard.clerk.com/last-active?path=api-keys",
    }


# ── the token, verified ─────────────────────────────────────────────────────


def _jwks_keys() -> list[dict[str, Any]]:
    """Clerk's public keys, cached briefly so a rotation is picked up."""
    if _jwks["keys"] and _jwks["fetched_at"] > time.time() - JWKS_TTL_SECONDS:
        return list(_jwks["keys"])  # type: ignore[arg-type]
    url = f"{issuer()}/.well-known/jwks.json"
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"Accept": "application/json"})
    except Exception as exc:  # noqa: BLE001 — network, DNS, TLS: one message
        raise ClerkError(
            "Clerk could not be reached to confirm the sign-in "
            f"({type(exc).__name__}). Check this deployment's network access."
        ) from exc
    if resp.status_code >= 400:
        raise ClerkError(f"Clerk refused to share its signing keys ({resp.status_code}).")
    try:
        keys = resp.json().get("keys") or []
    except Exception as exc:  # noqa: BLE001
        raise ClerkError("Clerk answered in a format this build cannot read.") from exc
    _jwks["keys"] = keys
    _jwks["fetched_at"] = time.time()
    return list(keys)


def _origin_of(azp: str) -> str:
    """The origin inside an ``azp``, or the azp itself when it is not a URL."""
    try:
        parsed = urlparse(azp)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:  # noqa: BLE001 — anything unreadable reads as "no match"
        pass
    return (azp or "").strip().rstrip("/")


def verify(token: str) -> dict[str, Any]:
    """Check one Clerk session token and return its verified claims.

    Raises :class:`ClerkError` with one sentence when anything is wrong. Every
    check fails closed: an unknown ``kid``, an unparseable token, a lapsed one
    and one minted for another front-end all read as refusals, in words.
    """
    import jwt  # imported lazily: only the Clerk path needs it

    if not configured():
        raise ClerkError(unconfigured_message())
    if not token:
        raise ClerkError("The sign-in did not return a session token.")

    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:  # noqa: BLE001
        raise ClerkError(
            "That session token could not be read. Please start the sign-in again."
        ) from exc
    kid = header.get("kid")
    algorithm = header.get("alg")
    if algorithm != "RS256":
        raise ClerkError(
            "That session token was signed in a way this build does not accept."
        )

    keys = _jwks_keys()
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise ClerkError(
            "That sign-in was signed with a key this deployment does not "
            "recognise. Please start the sign-in again."
        )

    try:
        from jwt import PyJWK

        verifying_key = PyJWK.from_dict(key).key
    except Exception as exc:  # noqa: BLE001 — a malformed JWKS entry is a refusal
        raise ClerkError(
            "Clerk's signing keys could not be read. Please try the sign-in "
            "again in a moment."
        ) from exc

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key=verifying_key,
            algorithms=["RS256"],
            audience=None,  # session tokens carry no aud; azp is the check
            leeway=LEEWAY_SECONDS,
            options={
                "require": ["exp", "sub", "iss"],
                "verify_aud": False,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
            },
            issuer=issuer(),
        )
    except jwt.exceptions.ExpiredSignatureError as exc:
        raise ClerkError("That session had already expired. Please sign in again.") from exc
    except jwt.exceptions.InvalidIssuerError as exc:
        raise ClerkError(
            "That sign-in belongs to a different Clerk project than this deployment."
        ) from exc
    except jwt.exceptions.ImmatureSignatureError as exc:
        raise ClerkError("That session is not valid yet. Please try again.") from exc
    except Exception as exc:  # noqa: BLE001 — every other failure is a refusal
        raise ClerkError(
            "That session token could not be verified. Please start the sign-in again."
        ) from exc

    azp = claims.get("azp") or ""
    if _origin_of(azp) not in {o.rstrip("/") for o in allowed_origins()}:
        raise ClerkError(
            "That sign-in was granted to a different website than this one."
        )
    if not claims.get("sub"):
        raise ClerkError("Clerk did not identify the account behind that session.")
    return claims


def _profile_from_backend_api(user_id: str) -> dict[str, Any] | None:
    """The Clerk user's email and name, read with the secret key."""
    try:
        resp = requests.get(
            f"https://api.clerk.com/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {secret_key()}"},
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        raise ClerkError(
            f"Clerk's profile could not be reached ({type(exc).__name__})."
        ) from exc
    if resp.status_code >= 400:
        return None
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


def identity(token: str) -> dict[str, Any]:
    """The verified sign-in as :func:`backend.users.upsert_identity` wants it.

    ``{"provider", "sub", "email", "name"}`` — the same shape the OAuth
    providers produce, so one account store serves every way in.
    """
    claims = verify(token)
    user_id = claims["sub"]
    email = ""
    name = ""

    user = _profile_from_backend_api(user_id)
    if isinstance(user, dict):
        for entry in user.get("email_addresses") or []:
            if isinstance(entry, dict) and entry.get("id") == user.get("primary_email_address_id"):
                email = str(entry.get("email_address") or "")
                break
        if not email:
            first = next(
                (
                    entry
                    for entry in (user.get("email_addresses") or [])
                    if isinstance(entry, dict) and entry.get("email_address")
                ),
                None,
            )
            email = str((first or {}).get("email_address") or "")
        first = str(user.get("first_name") or "").strip()
        last = str(user.get("last_name") or "").strip()
        name = " ".join(part for part in (first, last) if part)
        if not email and user.get("username"):
            name = name or str(user.get("username"))

    if not email:
        # Fallback only when the Backend API is unreachable: the standard claim
        # Clerk puts on session tokens. Verification already happened above;
        # this is a read, not a trust decision.
        email = str(claims.get("email") or "")

    return {
        "provider": "clerk",
        "label": "Clerk",
        "sub": user_id,
        "email": email,
        "name": name,
    }


def reset_for_tests() -> None:
    """Drop the cached JWKS (tests only)."""
    _jwks["keys"] = None
    _jwks["fetched_at"] = 0.0
