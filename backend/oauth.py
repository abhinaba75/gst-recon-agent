"""OAuth 2.0 sign-in for the web app (authorization-code flow).

A provider is *enabled by configuration and nothing else*: if a deployment has
not set the client id and secret for Google, the login page does not show a
Google button. A button that cannot work is worse than no button, so
:func:`available` is what the API answers with, and the page renders from it.

Why this is hand-rolled rather than a hosted auth product: the production shape
of this app is a static SPA plus this FastAPI worker, with no Node server to run
an auth SDK in. Two provider calls and a state check are less machinery than
proxying a third-party service, and the identity it produces is the one
:mod:`backend.users` already stores.

Security notes, all of them deliberate:

* ``state`` is random, single-use and expires, which is what stops a login-CSRF
  from attaching an attacker's provider account to a victim's session.
* The token endpoint is called server-side with the client secret; the browser
  never sees it.
* The profile is read from the provider's own userinfo API over TLS with the
  access token, so no cryptographic verification of our own is involved.
* Apple returns the address only inside the ``id_token``, so that token's claims
  are read directly — see :func:`_id_token_claims` for why that is the same
  trust model rather than a shortcut — and the nonce this deployment generated
  is checked against the one that comes back.
* Apple is also the one provider that will not hand out a static client secret:
  it wants a short-lived ES256 JWT signed with a ``.p8`` key from the developer
  account. :func:`_apple_client_secret` signs one when the key is configured,
  and accepts a ready-made secret when it is not.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

import requests

#: How long an authorization attempt may sit half-finished.
STATE_TTL_SECONDS = 10 * 60

#: How long the one-time code that hands a session to the browser may live.
CODE_TTL_SECONDS = 2 * 60

#: Network ceiling for both provider calls: a slow provider must not hold a
#: worker open while a shop owner waits at the login screen.
TIMEOUT = 10

#: Apple's issuer, and the ``aud`` a client secret it will accept must name.
APPLE_ISSUER = "https://appleid.apple.com"

#: How long a client secret this deployment signs stays valid. Apple's ceiling
#: is six months; this is comfortably under it and is refreshed long before it
#: lapses.
APPLE_SECRET_TTL_SECONDS = 150 * 24 * 60 * 60

PROVIDERS: dict[str, dict[str, Any]] = {
    "google": {
        "label": "Google",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "profile_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "id_env": ("RECON_GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID"),
        "secret_env": ("RECON_GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET"),
        "docs": "https://console.cloud.google.com/apis/credentials",
    },
    "github": {
        "label": "GitHub",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "profile_url": "https://api.github.com/user",
        "email_url": "https://api.github.com/user/emails",
        "scope": "read:user user:email",
        "id_env": ("RECON_GITHUB_CLIENT_ID", "GITHUB_CLIENT_ID"),
        "secret_env": ("RECON_GITHUB_CLIENT_SECRET", "GITHUB_CLIENT_SECRET"),
        "docs": "https://github.com/settings/developers",
    },
    "apple": {
        "label": "Apple",
        "authorize_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "scope": "name email",
        "id_env": ("RECON_APPLE_CLIENT_ID",),
        "secret_env": ("RECON_APPLE_CLIENT_SECRET",),
        "docs": "https://developer.apple.com/account/resources/identifiers/list/serviceId",
        # Apple posts the authorization code back instead of appending it to the
        # query string, and identifies the account through a signed id_token.
        "response_mode": "form_post",
        "oidc": True,
        "issuer": APPLE_ISSUER,
    },
}

_lock = threading.Lock()
_states: dict[str, dict[str, Any]] = {}
_codes: dict[str, dict[str, Any]] = {}

#: Client secrets this process has signed, keyed by the Services ID they name,
#: so a page that asks for the sign-in options does not re-sign on every poll.
_apple_secrets: dict[str, dict[str, Any]] = {}


class OAuthError(RuntimeError):
    """One readable sentence for the login page, never a stack trace."""


# ── configuration ───────────────────────────────────────────────────────────


def _env(names: tuple[str, ...]) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def client(provider: str) -> tuple[str, str]:
    """(client_id, client_secret) for a provider; ("", "") when unconfigured.

    Apple's half of this is derived rather than read, which is why the secret
    may be signed here; it degrades to "" instead of raising so that a half-set
    provider is reported as missing configuration rather than taking the whole
    options endpoint down with it.
    """
    spec = PROVIDERS.get(provider)
    if not spec:
        return "", ""
    client_id = _env(spec["id_env"])
    if not client_id:
        return "", ""
    if provider == "apple":
        try:
            return client_id, _apple_client_secret(client_id)
        except OAuthError:
            return client_id, ""
    return client_id, _env(spec["secret_env"])


def configured(provider: str) -> bool:
    client_id, client_secret = client(provider)
    return bool(client_id and client_secret)


def _read_private_key() -> str:
    """Apple's ``.p8`` signing key: inline in the environment, or a path to it."""
    inline = (os.environ.get("RECON_APPLE_PRIVATE_KEY") or "").strip()
    if inline:
        # A PEM pasted into a hosting UI usually arrives with escaped newlines.
        return inline.replace("\\n", "\n")
    path = (os.environ.get("RECON_APPLE_KEY_PATH") or "").strip()
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — an unreadable key is a missing key
        return ""


def _apple_client_secret(client_id: str) -> str:
    """Apple's client secret: one this deployment signs, or one already made.

    Apple is the only provider here that does not issue a static secret. It
    accepts a short-lived ES256 JWT whose ``sub`` is the Services ID, signed
    with a ``.p8`` key from the developer account. This signs one from
    ``RECON_APPLE_TEAM_ID`` / ``RECON_APPLE_KEY_ID`` / the key when they are all
    present, and uses ``RECON_APPLE_CLIENT_SECRET`` verbatim when the operator
    has generated one themselves (they last six months).
    """
    static = _env(("RECON_APPLE_CLIENT_SECRET",))
    if static:
        return static

    team_id = _env(("RECON_APPLE_TEAM_ID",))
    key_id = _env(("RECON_APPLE_KEY_ID",))
    key = _read_private_key()
    if not (team_id and key_id and key):
        return ""

    cached = _apple_secrets.get(client_id)
    if cached and cached["refreshes_at"] > time.time():
        return str(cached["secret"])

    try:
        import jwt  # imported lazily: only Apple's signing route needs it
    except Exception as exc:  # noqa: BLE001
        raise OAuthError(
            "Signing Apple's client secret needs the pyjwt library "
            "(pip install 'pyjwt[crypto]'), or set a ready-made "
            "RECON_APPLE_CLIENT_SECRET instead."
        ) from exc

    now = int(time.time())
    expires_at = now + APPLE_SECRET_TTL_SECONDS
    try:
        secret = jwt.encode(
            {
                "iss": team_id,
                "iat": now,
                "exp": expires_at,
                "aud": APPLE_ISSUER,
                "sub": client_id,
            },
            key,
            algorithm="ES256",
            headers={"kid": key_id},
        )
    except Exception as exc:  # noqa: BLE001
        raise OAuthError(
            "Apple's signing key could not be used as an ES256 key. It must be "
            "the .p8 file downloaded from the Apple developer account."
        ) from exc

    # Renew a few minutes early rather than hand Apple a secret that lapses
    # mid-sign-in.
    _apple_secrets[client_id] = {"secret": secret, "refreshes_at": expires_at - 300}
    return secret


def _apple_missing() -> list[str]:
    """What an operator still has to set before Apple sign-in can work."""
    out: list[str] = []
    if not _env(("RECON_APPLE_CLIENT_ID",)):
        out.append("RECON_APPLE_CLIENT_ID")
    if _env(("RECON_APPLE_CLIENT_SECRET",)):
        return out
    if not _env(("RECON_APPLE_TEAM_ID",)):
        out.append("RECON_APPLE_TEAM_ID")
    if not _env(("RECON_APPLE_KEY_ID",)):
        out.append("RECON_APPLE_KEY_ID")
    if not _read_private_key():
        out.append("RECON_APPLE_KEY_PATH")
    return out


def missing_env(provider: str) -> list[str]:
    """The variable names an operator still has to set — named, not guessed."""
    spec = PROVIDERS.get(provider)
    if not spec:
        return []
    if provider == "apple":
        return _apple_missing()
    out: list[str] = []
    if not _env(spec["id_env"]):
        out.append(spec["id_env"][0])
    if not _env(spec["secret_env"]):
        out.append(spec["secret_env"][0])
    return out


def unconfigured_message(provider: str) -> str:
    """One sentence naming what would switch this provider on."""
    spec = PROVIDERS.get(provider)
    label = spec["label"] if spec else provider
    names = missing_env(provider)
    message = f"{label} sign-in is not configured on this deployment."
    if names:
        message += f" Set {', '.join(names)} to enable it."
    if provider == "apple":
        message += (
            " Apple also accepts a ready-made RECON_APPLE_CLIENT_SECRET in place "
            "of the team id, key id and .p8 key."
        )
    return message


def available() -> list[dict[str, Any]]:
    """Every provider this build can offer, with its live state.

    Returned to the login page, which shows only the configured ones.
    """
    return [
        {
            "slug": slug,
            "label": spec["label"],
            "configured": configured(slug),
            "missing": missing_env(slug),
            "docs": spec["docs"],
        }
        for slug, spec in PROVIDERS.items()
    ]


def live() -> list[str]:
    """Slugs a user can actually sign in with right now."""
    return [p["slug"] for p in available() if p["configured"]]


# ── the authorization step ──────────────────────────────────────────────────


def _prune() -> None:
    """Drop expired states and codes. Called under the lock."""
    now = time.time()
    for store in (_states, _codes):
        for key in [k for k, v in store.items() if v["expires_at"] < now]:
            store.pop(key, None)


def authorize_url(
    provider: str,
    redirect_uri: str,
    *,
    start_origin: str = "",
) -> str:
    """The provider URL to send the browser to, with a fresh single-use state.

    For the OpenID Connect providers a ``nonce`` is generated here, kept with
    the state, and checked against the one inside the ``id_token`` that comes
    back — it is what stops a token minted for another attempt being replayed
    into this one.

    ``start_origin`` is the origin the page that began this is served from. It
    is remembered with the state and used to send the browser home afterwards,
    because it is the only value that survives a proxy that rewrites ``Host``:
    behind this project's own Vite proxy the engine sees 127.0.0.1:8000 while
    the page is on the preview URL. The caller must have validated it first;
    :func:`api.main._return_to` is what does that.
    """
    spec = PROVIDERS.get(provider)
    if not spec:
        raise OAuthError(f"Unknown sign-in provider: {provider}.")
    client_id, client_secret = client(provider)
    if not (client_id and client_secret):
        raise OAuthError(unconfigured_message(provider))

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24) if spec.get("oidc") else ""
    with _lock:
        _prune()
        _states[state] = {
            "provider": provider,
            "redirect_uri": redirect_uri,
            "nonce": nonce,
            "start_origin": start_origin.rstrip("/"),
            "expires_at": time.time() + STATE_TTL_SECONDS,
        }

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": spec["scope"],
        "state": state,
    }
    if nonce:
        params["nonce"] = nonce
    if spec.get("response_mode"):
        # Apple posts the code back rather than appending it to the query —
        # required as soon as the request asks for the email scope.
        params["response_mode"] = spec["response_mode"]
    if provider == "google":
        # Without this Google returns no refresh token and re-asks for consent.
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    query = "&".join(f"{k}={requests.utils.quote(str(v), safe='')}" for k, v in params.items())
    return f"{spec['authorize_url']}?{query}"


def consume_state(state: str) -> dict[str, Any]:
    """Validate and burn one state value. Raises OAuthError when it is no good."""
    with _lock:
        _prune()
        record = _states.pop(state or "", None)
    if not record:
        raise OAuthError("This sign-in attempt has expired. Please start again.")
    return record


# ── the token + profile step ────────────────────────────────────────────────


def _post_token(spec: dict[str, Any], data: dict[str, str]) -> dict[str, Any]:
    try:
        resp = requests.post(
            spec["token_url"],
            data=data,
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — network, DNS, TLS: one message
        raise OAuthError(
            f"{spec['label']} could not be reached ({type(exc).__name__}). "
            "Check this deployment's network access and try again."
        ) from exc
    if resp.status_code >= 400:
        raise OAuthError(f"{spec['label']} refused the sign-in ({resp.status_code}).")
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        raise OAuthError(f"{spec['label']} answered in a format this build cannot read.") from exc


def _get_profile(spec: dict[str, Any], access_token: str, url: str) -> Any:
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "recon-agent",
            },
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        raise OAuthError(
            f"{spec['label']} could not be reached ({type(exc).__name__})."
        ) from exc
    if resp.status_code >= 400:
        raise OAuthError(f"{spec['label']} would not share the account profile.")
    return resp.json()


def _id_token_claims(id_token: str, label: str) -> dict[str, Any]:
    """The claims inside an ``id_token``, read without checking its signature.

    These claims are not a token a client handed us: they arrived from the
    provider's *token endpoint*, over TLS, in answer to a server-to-server
    request this process authenticated with its client secret. That is the same
    trust as reading a userinfo reply from the same endpoint, and there is no
    caller-supplied token in the path to forge.

    What that costs is the signature check, so every claim this build acts on is
    checked against a value the deployment itself chose instead: ``aud`` against
    its own client id, ``iss`` against the provider's issuer, ``nonce`` against
    the one generated when the attempt began, and ``exp`` against the clock.
    Apple returns the address only inside this token, which is why the read
    exists at all.
    """
    parts = (id_token or "").split(".")
    if len(parts) < 2:
        raise OAuthError(f"{label} did not return a readable identity token.")
    payload = parts[1]
    try:
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(decoded.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise OAuthError(
            f"{label} returned an identity token this build cannot read."
        ) from exc
    if not isinstance(claims, dict):
        raise OAuthError(f"{label} returned an identity token this build cannot read.")
    return claims


def exchange(
    provider: str,
    code: str,
    redirect_uri: str,
    *,
    nonce: str = "",
    name_hint: str = "",
) -> dict[str, Any]:
    """Swap an authorization code for a verified identity. Never returns a token.

    The reply is exactly what :func:`backend.users.upsert_identity` needs:
    ``{"provider", "sub", "email", "name"}``.

    ``nonce`` is the value :func:`authorize_url` generated for this attempt, and
    ``name_hint`` is what the provider sent alongside the code — Apple shares a
    person's name once, on first consent, and never again.
    """
    spec = PROVIDERS.get(provider)
    if not spec:
        raise OAuthError(f"Unknown sign-in provider: {provider}.")
    client_id, client_secret = client(provider)
    if not (client_id and client_secret):
        raise OAuthError(unconfigured_message(provider))
    if not code:
        raise OAuthError("The provider did not return an authorization code.")

    token = _post_token(
        spec,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    access_token = token.get("access_token")
    if not access_token:
        raise OAuthError(
            token.get("error_description")
            or f"{spec['label']} did not issue an access token for this sign-in."
        )

    if spec.get("oidc"):
        # The address is inside the id_token; there is no userinfo call to make.
        claims = _id_token_claims(token.get("id_token") or "", spec["label"])
        issuer = spec.get("issuer")
        if issuer and claims.get("iss") != issuer:
            raise OAuthError(f"{spec['label']} answered for a different issuer.")
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if client_id not in audiences:
            raise OAuthError(f"{spec['label']} answered for a different application.")
        if nonce and claims.get("nonce") != nonce:
            raise OAuthError(
                "This sign-in could not be matched to the attempt that started "
                "it. Please start again."
            )
        try:
            expired = int(claims.get("exp") or 0) < int(time.time())
        except (TypeError, ValueError):
            expired = True
        if expired:
            raise OAuthError(
                f"{spec['label']}'s sign-in token had already expired. Please start again."
            )
        email = str(claims.get("email") or "")
        subject = str(claims.get("sub") or "")
        name = str(claims.get("name") or "") or (name_hint or "").strip()
    else:
        profile = _get_profile(spec, access_token, spec["profile_url"])
        if not isinstance(profile, dict):
            raise OAuthError(f"{spec['label']} answered with an unexpected profile.")

        email = profile.get("email") or ""
        name = profile.get("name") or profile.get("login") or ""
        subject = str(profile.get("sub") or profile.get("id") or "")

        # GitHub hides the address unless it is public, so ask for the primary one.
        if provider == "github" and not email and spec.get("email_url"):
            emails = _get_profile(spec, access_token, spec["email_url"])
            if isinstance(emails, list):
                primary = next(
                    (e for e in emails if isinstance(e, dict) and e.get("primary")),
                    None,
                )
                chosen = primary or next((e for e in emails if isinstance(e, dict)), None)
                email = (chosen or {}).get("email", "")

    if not subject:
        raise OAuthError(f"{spec['label']} did not identify the account.")

    return {
        "provider": provider,
        "label": spec["label"],
        "sub": subject,
        "email": email,
        "name": name,
    }


# ── handing the session to the browser ──────────────────────────────────────


def issue_code(token: str, user: dict[str, Any]) -> str:
    """A one-time code that the page swaps for its session token.

    The session token itself never travels in a URL: it would land in browser
    history, in a referrer header, and in the access log of whatever serves the
    redirect. A code that dies on first use is the cheap way not to do that.
    """
    code = secrets.token_urlsafe(24)
    with _lock:
        _prune()
        _codes[code] = {
            "token": token,
            "user": user,
            "expires_at": time.time() + CODE_TTL_SECONDS,
        }
    return code


def redeem_code(code: str) -> dict[str, Any]:
    """Burn a one-time code and return what it held, or raise OAuthError."""
    with _lock:
        _prune()
        record = _codes.pop(code or "", None)
    if not record:
        raise OAuthError("That sign-in link has already been used or has expired.")
    return record


# ── redirect plumbing ───────────────────────────────────────────────────────


def callback_uri(base_url: str, provider: str) -> str:
    """The redirect URI to register with the provider, built from this request.

    Behind a proxy the forwarded scheme is what the operator must have
    registered, so ``X-Forwarded-Proto`` wins over what the socket says.
    """
    return f"{base_url.rstrip('/')}/api/auth/{provider}/callback"


def reset_for_tests() -> None:
    """Empty the state, code and signed-secret stores (tests only)."""
    with _lock:
        _states.clear()
        _codes.clear()
        _apple_secrets.clear()
