#!/usr/bin/env python3
"""Clerk sign-in tests: verification, refusal reasons, and the exchange.

Run directly (no pytest, no server):  .venv/bin/python tests/test_clerk.py

No network call reaches Clerk. The JWKS endpoint and the Backend API are
stubbed, and the session tokens are signed here with a real RSA key, so every
check is about this project's own behaviour: what it accepts, what it refuses,
and what it refuses to leak.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="recon-clerk-")) / "users.json"
os.environ["RECON_USERS_FILE"] = str(_TMP)
os.environ["RECON_USERS_TABLE"] = ""
os.environ["RECON_RESULTS_TABLE"] = ""
for _key in (
    "RECON_CLERK_ISSUER",
    "RECON_CLERK_SECRET_KEY",
    "RECON_CLERK_PUBLISHABLE_KEY",
    "RECON_CLERK_ALLOWED_ORIGINS",
    "RECON_ALLOWED_ORIGINS",
    "RECON_UI_EMAIL",
    "RECON_UI_PASSWORD",
):
    os.environ.pop(_key, None)

from api import main as api  # noqa: E402
from backend import clerk, session as sessions, users  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


# A real RSA key: the signature check below has to mean something.
from cryptography.hazmat.primitives import serialization as ser  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402
from cryptography.hazmat.primitives import hashes  # noqa: E402

_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _public_jwk() -> dict:
    """The public key as a JWK, the shape Clerk's JWKS document uses."""
    numbers = _PRIVATE.public_key().public_numbers()
    n_bytes = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": "test-key-1",
        "n": _b64u(n_bytes),
        "e": _b64u(numbers.e.to_bytes(3, "big")),
    }


def _sign(claims: dict, *, kid: str = "test-key-1", alg: str = "RS256") -> str:
    """Sign claims the way Clerk's signer does: header.payload.signature."""
    header = {"alg": alg, "typ": "JWT", "kid": kid}
    signing_input = (
        _b64u(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64u(json.dumps(claims, separators=(",", ":")).encode())
    )
    if alg != "RS256":
        # Only RS256 can be signed with the RSA key; anything else is returned
        # unsigned-but-well-formed, which is exactly what the refusal test needs.
        return signing_input + ".not-a-real-signature"
    digest = signing_input.encode()
    signature = _PRIVATE.sign(digest, padding.PKCS1v15(), hashes.SHA256())
    return signing_input + "." + _b64u(signature)


def _token(kid: str = "test-key-1", **over) -> str:
    claims = {
        "iss": "https://clerk.recon.example",
        "sub": "user_2abc",
        "azp": "http://localhost:5173",
        "exp": int(time.time()) + 120,
        "iat": int(time.time()),
        "nbf": int(time.time()) - 10,
    }
    claims.update(over)
    return _sign(claims, kid=kid)


def _install_clerk_env() -> None:
    os.environ["RECON_CLERK_ISSUER"] = "https://clerk.recon.example"
    os.environ["RECON_CLERK_SECRET_KEY"] = "sk_test_sentinel_do_not_leak"
    os.environ["RECON_CLERK_PUBLISHABLE_KEY"] = "pk_test_pub-is-public"
    os.environ["RECON_CLERK_ALLOWED_ORIGINS"] = "http://localhost:5173"


def _stub_jwks() -> None:
    clerk.requests.get = (  # type: ignore[assignment]
        lambda url, **k: (
            FakeResponse({"keys": [_public_jwk()]})
            if url.endswith("/.well-known/jwks.json")
            else _stub_profile_reply(url)
        )
    )


_PROFILE = {
    "id": "user_2abc",
    "first_name": "Asha",
    "last_name": "Rao",
    "username": None,
    "primary_email_address_id": "idn_1",
    "email_addresses": [{"id": "idn_1", "email_address": "asha@kirana.in"}],
}


def _stub_profile_reply(url: str) -> FakeResponse:
    if url.startswith("https://api.clerk.com/v1/users/"):
        return FakeResponse(_PROFILE)
    raise AssertionError(f"unexpected Clerk URL in test: {url}")


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print("== Configuration honesty ==")
    check("nothing is configured by default", not clerk.configured())
    check("the missing variables are named",
          clerk.missing_env() == ["RECON_CLERK_ISSUER", "RECON_CLERK_SECRET_KEY"],
          str(clerk.missing_env()))
    check("a non-https issuer is not quietly accepted", clerk.issuer() == "")
    status = clerk.status()
    check("the unconfigured status offers no key and no origins",
          status["publishable_key"] == "" and status["allowed_origins"] == [])
    os.environ["RECON_CLERK_ISSUER"] = "http://localhost:9999"
    check("an http issuer is refused", not clerk.configured())
    os.environ["RECON_CLERK_ISSUER"] = "https://clerk.recon.example"
    os.environ["RECON_CLERK_SECRET_KEY"] = "sk_test_sentinel_do_not_leak"
    try:
        check("issuer plus secret key is configured", clerk.configured())
    finally:
        os.environ.pop("RECON_CLERK_SECRET_KEY", None)
        os.environ.pop("RECON_CLERK_ISSUER", None)

    print("== Verification, with Clerk's endpoints stubbed ==")
    _install_clerk_env()
    clerk.reset_for_tests()
    real_get = clerk.requests.get
    try:
        clerk.requests.get = (  # type: ignore[assignment]
            lambda url, **k: (
                FakeResponse({"keys": [_public_jwk()]})
                if url.endswith("/.well-known/jwks.json")
                else FakeResponse(_PROFILE)
                if url.startswith("https://api.clerk.com/v1/users/")
                else (_ for _ in ()).throw(AssertionError(url))
            )
        )

        good = clerk.verify(_token())
        check("a well-formed session token verifies", good["sub"] == "user_2abc", str(good))
        identity = clerk.identity(_token())
        check("the identity is the shape every other provider produces",
              identity["provider"] == "clerk" and identity["sub"] == "user_2abc"
              and identity["email"] == "asha@kirana.in" and identity["name"] == "Asha Rao",
              str(identity))
        check("the secret key never reaches a reply", "sk_test_sentinel" not in str(identity))

        for label, over, expect in (
            ("a token from another Clerk project", {"iss": "https://clerk.evil.example"}, "different Clerk"),
            ("a lapsed token", {"exp": int(time.time()) - 300}, "expired"),
            ("a token for another website", {"azp": "https://evil.example"}, "different website"),
            ("an azp pretending to be ours on a lookalike domain",
             {"azp": "http://localhost:5173.evil.example"}, "different website"),
        ):
            try:
                clerk.verify(_token(**over))
                check(f"{label} is refused", False)
            except clerk.ClerkError as exc:
                check(f"{label} is refused", expect in str(exc), str(exc))

        check("an azp on our own origin with a path is still ours",
              clerk.verify(_token(azp="http://localhost:5173/app"))["sub"] == "user_2abc")

        import jwt as pyjwt

        def _expect_refusal(token: str, word: str) -> bool:
            try:
                clerk.verify(token)
                return False
            except clerk.ClerkError as exc:
                return word in str(exc)

        def _sign_alg(alg: str) -> str:
            claims = {"iss": clerk.issuer(), "sub": "user_x", "azp": "http://localhost:5173",
                      "exp": int(time.time()) + 120}
            try:
                return pyjwt.encode(claims, "symmetric-secret", algorithm=alg,
                                    headers={"kid": "test-key-1"})
            except Exception:
                return _token()

        check("an unknown signing key is refused in words",
              _expect_refusal(_token(kid="someone-elses-key"), "recognise"))
        check("a token signed in a way we do not accept is refused",
              _expect_refusal(_sign_alg("HS256"), "signed in a way"))
        check("a token with no subject is refused", _expect_refusal(_token(sub=""), "identify"))
        check("an unreadable token is refused in words",
              _expect_refusal("not-a-jwt", "could not be read"))
        check("an empty token is refused", _expect_refusal("", "did not return"))

        def _jwks_outage_refusal() -> str:
            def _boom(url, **k):
                raise OSError("network down")

            clerk.requests.get = _boom  # type: ignore[assignment]
            clerk.reset_for_tests()
            try:
                clerk.verify(_token())
                return ""
            except clerk.ClerkError as exc:
                return str(exc)
            finally:
                clerk.requests.get = (  # type: ignore[assignment]
                    lambda url, **k: FakeResponse({"keys": [_public_jwk()]})
                    if url.endswith("/.well-known/jwks.json")
                    else FakeResponse(_PROFILE)
                )

        check("a JWKS outage refuses in words, never with a stack trace",
              _jwks_outage_refusal().startswith("Clerk could not be reached"))

        print("== The Backend API profile ==")
        real_backend = clerk.requests.get
        try:
            clerk.requests.get = (  # type: ignore[assignment]
                lambda url, **k: (
                    FakeResponse({"keys": [_public_jwk()]})
                    if url.endswith("/.well-known/jwks.json")
                    else FakeResponse({}, status_code=404)
                )
            )
            degraded = clerk.identity(_token())
            check("a Clerk profile outage falls back to the token's own email claim",
                  degraded["email"] == "", str(degraded))
            check("the account store still refuses to open without an address",
                  api.clerk_exchange(api.ClerkTokenRequest(token=_token()))["ok"] is False)
        finally:
            clerk.requests.get = real_backend  # type: ignore[assignment]

        print("== The exchange endpoint ==")
        exchanged = api.clerk_exchange(api.ClerkTokenRequest(token=_token()))
        check("a verified Clerk token opens a session",
              exchanged["ok"] is True and exchanged["source"] == "account", str(exchanged)[:140])
        check("the account it created is stored and named",
              (users.find("asha@kirana.in") or {}).get("name") == "Asha Rao",
              str(users.find("asha@kirana.in")))
        check("the session token is this deployment's, not Clerk's",
              "user_2abc" not in exchanged["token"])
        live = sessions.validate(exchanged["token"])
        check("the session resolves to the Clerk account",
              live is not None and live["user"]["email"] == "asha@kirana.in")
        check("a junk token is refused with a sentence",
              api.clerk_exchange(api.ClerkTokenRequest(token="nope"))["ok"] is False)

        linked = api.clerk_exchange(api.ClerkTokenRequest(token=_token(sub="user_2abc")))
        check("a second Clerk sign-in reuses the same account", linked["ok"] is True)
        check("the account count did not grow", users.count() == 1)

        password_first = users.register("both@kirana.in", "a good password")
        both = users.upsert_identity("clerk", "user_both", "both@kirana.in", "Both")
        check("a Clerk identity links onto an existing password account",
              both["ok"] is True and password_first["ok"] is True
              and users.authenticate("both@kirana.in", "a good password")["ok"] is True)
        check("the password path still works after linking", users.count() == 2)

        print("== What the options endpoint says ==")
        options = api.auth_options()
        check("options carry the Clerk status block", isinstance(options.get("clerk"), dict))
        check("the publishable key is safe to publish",
              options["clerk"]["publishable_key"] == "pk_test_pub-is-public")
        check("the secret key is never echoed",
              "sk_test_sentinel_do_not_leak" not in str(options))
        check("health reports whether Clerk is live", api.health()["clerk"] is True)
        check("the exchange endpoint is on the app",
              any(getattr(r, "path", "") == "/api/auth/clerk" for r in api.app.routes))
    finally:
        clerk.requests.get = real_get  # type: ignore[assignment]
        for key in ("RECON_CLERK_ISSUER", "RECON_CLERK_SECRET_KEY",
                    "RECON_CLERK_PUBLISHABLE_KEY", "RECON_CLERK_ALLOWED_ORIGINS"):
            os.environ.pop(key, None)

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
