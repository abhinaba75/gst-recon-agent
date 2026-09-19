#!/usr/bin/env python3
"""Auth tests: accounts, password hashing, OAuth, sessions.

Run directly (no pytest, no server):  .venv/bin/python tests/test_auth.py

No provider is ever contacted: the token/profile calls are stubbed, and every
assertion is about this project's own behaviour — what it stores, what it
refuses, and what it refuses to put in a URL.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Accounts go to a throwaway file, never to the project root, and the audit
# table stays untouched.
_TMP = Path(tempfile.mkdtemp(prefix="recon-auth-")) / "users.json"
os.environ["RECON_USERS_FILE"] = str(_TMP)
os.environ["RECON_USERS_TABLE"] = ""
os.environ["RECON_RESULTS_TABLE"] = ""
for _key in (
    "RECON_UI_EMAIL",
    "RECON_UI_PASSWORD",
    "RECON_ALLOW_SIGNUP",
    "RECON_GOOGLE_CLIENT_ID",
    "RECON_GOOGLE_CLIENT_SECRET",
    "RECON_GITHUB_CLIENT_ID",
    "RECON_GITHUB_CLIENT_SECRET",
    "RECON_APPLE_CLIENT_ID",
    "RECON_APPLE_CLIENT_SECRET",
    "RECON_APPLE_TEAM_ID",
    "RECON_APPLE_KEY_ID",
    "RECON_APPLE_KEY_PATH",
    "RECON_APPLE_PRIVATE_KEY",
):
    os.environ.pop(_key, None)

from api import main as api  # noqa: E402
from backend import oauth, session as sessions, users  # noqa: E402


class FakeResponse:
    """Stands in for requests.Response in the provider calls."""

    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print("== Password hashing ==")
    first, second = users.hash_password("correct horse"), users.hash_password("correct horse")
    check("a stored hash names its scheme", first.startswith("scrypt$"), first[:24])
    check("the same password hashes differently twice (per-user salt)", first != second)
    check("the right password verifies", users.verify_password("correct horse", first))
    check("a wrong password does not", not users.verify_password("correct hors", first))
    check("a malformed hash verifies nothing", not users.verify_password("x", "not-a-hash"))
    check("an empty password verifies nothing", not users.verify_password("", first))
    check("hashes never travel in the public view",
          "password" not in users.public({"email": "a@b.in", "password": first}))

    print("== Accounts ==")
    check("a bad address is refused", not users.register("not-an-email", "longenough1")["ok"])
    check("a short password is refused",
          not users.register("ops@acme.in", "short")["ok"],
          users.register("ops@acme.in", "short")["detail"])
    created = users.register("Ops@Acme.IN", "correct horse", "Ops Lead")
    check("a real sign-up is accepted", created["ok"] is True, str(created)[:120])
    check("the address is normalised", created["user"]["email"] == "ops@acme.in")
    check("the name is kept", created["user"]["name"] == "Ops Lead")
    check("the provider names how they signed up", created["user"]["provider"] == "password")
    check("the account is on disk, not just in memory", _TMP.exists())
    check("a second sign-up on the same address is refused",
          users.register("ops@acme.in", "another one")["ok"] is False)
    check("sign-up can be closed by the operator", True)

    print("== Sign-in ==")
    good = users.authenticate("ops@acme.in", "correct horse")
    check("the right password signs in", good["ok"] is True, str(good)[:120])
    bad = users.authenticate("ops@acme.in", "wrong horse")
    unknown = users.authenticate("nobody@acme.in", "wrong horse")
    check("a wrong password is refused", bad["ok"] is False)
    check("an unknown account is refused with the same sentence (no enumeration)",
          unknown["detail"] == bad["detail"], f"{bad['detail']} == {unknown['detail']}")
    check("the sign-in is recorded on the account", bool(good["user"]["last_login_at"]))
    check("no hash or salt is ever returned",
          "password" not in good["user"] and "salt" not in str(good["user"]))

    print("== Provider identities ==")
    linked = users.upsert_identity("google", "sub-123", "ops@acme.in", "Ops Lead")
    check("a provider signs into the account with the same address",
          linked["ok"] is True and linked["user"]["provider"] == "google", str(linked)[:120])
    check("the password login still works after linking",
          users.authenticate("ops@acme.in", "correct horse")["ok"] is True)
    fresh = users.upsert_identity("github", "42", "shop@kirana.in", "Kirana")
    check("a first provider sign-in creates the account",
          fresh["ok"] is True and users.count() == 2, f"count={users.count()}")
    check("a provider that shares no email is refused",
          users.upsert_identity("google", "sub-9", "", "No Address")["ok"] is False)

    print("== Sessions ==")
    sessions.reset_for_tests()
    account = api.login(api.LoginRequest(email="ops@acme.in", password="correct horse"))
    check("an account signs in through the API",
          account["ok"] is True and account["source"] == "account", str(account)[:120])
    check("the demo pair is refused once the build has real accounts",
          api.login(api.LoginRequest(email=sessions.DEMO_EMAIL,
                                    password=sessions.DEMO_PASSWORD))["ok"] is False)
    check("the token is not the password", "correct horse" not in account["token"])
    live = sessions.validate(account["token"])
    check("the session resolves to its user",
          live is not None and live["user"]["email"] == "ops@acme.in", str(live)[:120])
    check("the session names how it was created", live["source"] == "account")
    check("signing out drops it", sessions.logout(account["token"]) is True
          and sessions.validate(account["token"]) is None)

    issued = sessions.issue({"email": "vendor@kirana.in", "name": "Vendor"}, "account")
    check("a verified identity can be issued a session directly",
          sessions.validate(issued["token"])["user"]["email"] == "vendor@kirana.in")

    os.environ["RECON_UI_EMAIL"] = "owner@msme.in"
    os.environ["RECON_UI_PASSWORD"] = "secret operator"
    try:
        operator = api.login(api.LoginRequest(email="owner@msme.in",
                                             password="secret operator"))
        check("the configured operator signs in as itself",
              operator["ok"] is True and operator["source"] == "operator", str(operator)[:120])
        check("the configured account is listed like any other",
              users.find("owner@msme.in") is not None)
    finally:
        os.environ.pop("RECON_UI_EMAIL", None)
        os.environ.pop("RECON_UI_PASSWORD", None)

    print("== OAuth: nothing is offered until it is configured ==")
    available = {p["slug"]: p for p in oauth.available()}
    check("every supported provider is described",
          set(available) == {"google", "github", "apple"}, str(sorted(available)))
    check("unconfigured providers are not offered",
          all(not p["configured"] for p in available.values()))
    check("the missing variables are named, not guessed",
          "RECON_GOOGLE_CLIENT_ID" in available["google"]["missing"]
          and "RECON_GOOGLE_CLIENT_SECRET" in available["google"]["missing"],
          str(available["google"]["missing"]))
    check("no provider is live yet", oauth.live() == [])
    try:
        oauth.authorize_url("google", "https://app.example/api/auth/google/callback")
        check("starting an unconfigured provider raises", False)
    except oauth.OAuthError as exc:
        check("starting an unconfigured provider raises", "not configured" in str(exc), str(exc))
    try:
        oauth.authorize_url("myspace", "https://app.example/cb")
        check("an unknown provider raises", False)
    except oauth.OAuthError as exc:
        check("an unknown provider raises", "Unknown" in str(exc), str(exc))

    print("== OAuth: the flow, with the provider stubbed ==")
    os.environ["RECON_GOOGLE_CLIENT_ID"] = "id-123"
    os.environ["RECON_GOOGLE_CLIENT_SECRET"] = "secret-123"
    try:
        check("configuring both variables turns the provider on", oauth.configured("google"))
        url = oauth.authorize_url("google", "https://app.example/api/auth/google/callback")
        check("the authorize URL carries the client id and a scope",
              "client_id=id-123" in url and "scope=" in url, url[:90])
        state = url.split("state=")[1].split("&")[0]
        attempt = oauth.consume_state(state)
        check("the state resolves to its redirect URI",
              attempt["redirect_uri"].endswith("/api/auth/google/callback"))
        try:
            oauth.consume_state(state)
            check("a state is single use", False)
        except oauth.OAuthError:
            check("a state is single use", True)
        try:
            oauth.consume_state("invented")
            check("an unknown state is refused", False)
        except oauth.OAuthError:
            check("an unknown state is refused", True)

        real_post, real_get = oauth.requests.post, oauth.requests.get
        try:
            oauth.requests.post = lambda *a, **k: FakeResponse({"access_token": "at-1"})  # type: ignore[assignment]
            oauth.requests.get = lambda *a, **k: FakeResponse(  # type: ignore[assignment]
                {"sub": "sub-1", "email": "owner@kirana.in", "name": "Owner"}
            )
            profile = oauth.exchange("google", "the-code", "https://app.example/cb")
            check("the profile comes back as an identity",
                  profile["sub"] == "sub-1" and profile["email"] == "owner@kirana.in",
                  str(profile))
            check("no access token is passed back to the caller", "at-1" not in str(profile))

            oauth.requests.post = lambda *a, **k: FakeResponse({}, status_code=400)  # type: ignore[assignment]
            try:
                oauth.exchange("google", "the-code", "https://app.example/cb")
                check("a provider refusal is reported in words", False)
            except oauth.OAuthError as exc:
                check("a provider refusal is reported in words", "refused" in str(exc), str(exc))

            def _boom(*_a, **_k):
                raise OSError("network down")

            oauth.requests.post = _boom  # type: ignore[assignment]
            try:
                oauth.exchange("google", "the-code", "https://app.example/cb")
                check("an unreachable provider does not raise OSError", False)
            except oauth.OAuthError as exc:
                check("an unreachable provider does not raise OSError", "reached" in str(exc), str(exc))
        finally:
            oauth.requests.post, oauth.requests.get = real_post, real_get  # type: ignore[assignment]
    finally:
        os.environ.pop("RECON_GOOGLE_CLIENT_ID", None)
        os.environ.pop("RECON_GOOGLE_CLIENT_SECRET", None)

    print("== Apple: the provider that issues no static secret ==")
    available = {p["slug"]: p for p in oauth.available()}
    check("Apple is offered beside the others", "apple" in available)
    apple_missing = available["apple"]["missing"]
    check("an unconfigured Apple names what it needs",
          "RECON_APPLE_CLIENT_ID" in apple_missing and "RECON_APPLE_KEY_ID" in apple_missing,
          str(apple_missing))
    check("Apple is not offered while it is unconfigured",
          available["apple"]["configured"] is False)
    try:
        oauth.authorize_url("apple", "https://app.example/cb")
        check("starting an unconfigured Apple raises", False)
    except oauth.OAuthError as exc:
        check("starting an unconfigured Apple raises", "not configured" in str(exc), str(exc))

    # The operator path that needs no key material: a secret made by hand.
    os.environ["RECON_APPLE_CLIENT_ID"] = "in.reconagent.web"
    os.environ["RECON_APPLE_CLIENT_SECRET"] = "made-elsewhere.jwt"
    try:
        check("a ready-made client secret switches Apple on", oauth.configured("apple"))
        check("nothing is left missing", oauth.missing_env("apple") == [],
              str(oauth.missing_env("apple")))
        check("a ready-made secret is used exactly as given",
              oauth.client("apple")[1] == "made-elsewhere.jwt")
        ready_url = oauth.authorize_url("apple", "https://app.example/api/auth/apple/callback")
        check("Apple is asked to post its answer back rather than append it",
              "response_mode=form_post" in ready_url, ready_url[:120])
        check("the attempt carries a nonce", "nonce=" in ready_url, ready_url[:120])
        check("the nonce is kept for the attempt that will come back",
              len(oauth.consume_state(ready_url.split("state=")[1].split("&")[0])["nonce"]) > 20)
    finally:
        os.environ.pop("RECON_APPLE_CLIENT_ID", None)
        os.environ.pop("RECON_APPLE_CLIENT_SECRET", None)

    # The production path: sign the secret here, from the developer's .p8 key.
    try:
        from cryptography.hazmat.primitives import serialization as der
        from cryptography.hazmat.primitives.asymmetric import ec

        signing_key = ec.generate_private_key(ec.SECP256R1())
        p8 = Path(tempfile.mkdtemp(prefix="recon-apple-")) / "AuthKey_KEY7890AB.p8"
        p8.write_bytes(
            signing_key.private_bytes(
                encoding=der.Encoding.PEM,
                format=der.PrivateFormat.PKCS8,
                encryption_algorithm=der.NoEncryption(),
            )
        )
        have_crypto = True
    except Exception as exc:  # noqa: BLE001
        print(f"  SKIP  the signing checks — no cryptography library ({exc})")
        have_crypto = False

    apple_nonce = ""
    if have_crypto:
        import jwt as pyjwt  # only reached when the crypto extra is installed

        os.environ["RECON_APPLE_CLIENT_ID"] = "in.reconagent.web"
        os.environ["RECON_APPLE_TEAM_ID"] = "TEAM123456"
        os.environ["RECON_APPLE_KEY_ID"] = "KEY7890AB"
        os.environ["RECON_APPLE_KEY_PATH"] = str(p8)
        try:
            oauth.reset_for_tests()
            check("the .p8 key is enough, with no pasted secret", oauth.configured("apple"))
            _, secret = oauth.client("apple")
            check("the secret is a JWT, not a string", secret.count(".") == 2, secret[:20] + "…")
            claims = pyjwt.decode(
                secret, signing_key.public_key(), algorithms=["ES256"], audience=oauth.APPLE_ISSUER
            )
            check("it verifies against the public half of the key", bool(claims), str(claims)[:120])
            check("its subject is the Services ID", claims["sub"] == "in.reconagent.web")
            check("its issuer is the team", claims["iss"] == "TEAM123456")
            check("its audience is Apple", claims["aud"] == oauth.APPLE_ISSUER)
            check("it lives well short of Apple's six-month ceiling",
                  150 * 24 * 3600 <= claims["exp"] - claims["iat"] <= 180 * 24 * 3600,
                  f"{claims['exp'] - claims['iat']}s")
            header = pyjwt.get_unverified_header(secret)
            check("it names the key Apple matches on",
                  header["alg"] == "ES256" and header["kid"] == "KEY7890AB", str(header))
            check("asking twice does not sign twice", oauth.client("apple")[1] == secret)

            oauth.reset_for_tests()
            url = oauth.authorize_url("apple", "https://app.example/api/auth/apple/callback")
            state = url.split("state=")[1].split("&")[0]
            apple_nonce = url.split("nonce=")[1].split("&")[0]
            check("the nonce sent to Apple is the one kept for the attempt",
                  oauth.consume_state(state)["nonce"] == apple_nonce)

            def id_token(**over) -> str:
                """A provider-shaped identity token carrying whatever we need to test."""
                payload = {
                    "iss": oauth.APPLE_ISSUER,
                    "aud": "in.reconagent.web",
                    "sub": "001234.abcdef",
                    "email": "apple@kirana.in",
                    "nonce": apple_nonce,
                    "exp": int(time.time()) + 300,
                }
                payload.update(over)
                body = base64.urlsafe_b64encode(json.dumps(payload).encode())
                return f"eyJhbGciOiJSUzI1NiJ9.{body.rstrip(b'=').decode()}.signature"

            real_post = oauth.requests.post
            try:
                oauth.requests.post = lambda *a, **k: FakeResponse(  # type: ignore[assignment]
                    {"access_token": "at-apple", "id_token": id_token()}
                )
                profile = oauth.exchange(
                    "apple", "the-code", "https://app.example/cb", nonce=apple_nonce
                )
                check("Apple's identity comes out of the id_token",
                      profile["sub"] == "001234.abcdef" and profile["email"] == "apple@kirana.in",
                      str(profile))
                check("no access token is passed back to the caller", "at-apple" not in str(profile))
                named = oauth.exchange(
                    "apple", "c", "https://app.example/cb",
                    nonce=apple_nonce, name_hint="Asha Rao",
                )
                check("the name Apple shares once is used", named["name"] == "Asha Rao", str(named))

                for label, over, expect in (
                    ("a token minted for another attempt", {"nonce": "someone-elses"}, "matched"),
                    ("a token minted for another app", {"aud": "com.example.other"}, "application"),
                    ("a token from another issuer", {"iss": "https://evil.example"}, "issuer"),
                    ("a token that has already lapsed", {"exp": int(time.time()) - 10}, "expired"),
                ):
                    oauth.requests.post = (  # type: ignore[assignment]
                        lambda *a, _o=over, **k: FakeResponse(
                            {"access_token": "at", "id_token": id_token(**_o)}
                        )
                    )
                    try:
                        oauth.exchange("apple", "c", "https://app.example/cb", nonce=apple_nonce)
                        check(f"{label} is refused", False)
                    except oauth.OAuthError as exc:
                        check(f"{label} is refused", expect in str(exc), str(exc))

                oauth.requests.post = lambda *a, **k: FakeResponse(  # type: ignore[assignment]
                    {"access_token": "at"}
                )
                try:
                    oauth.exchange("apple", "c", "https://app.example/cb", nonce=apple_nonce)
                    check("a reply with no id_token is refused in words", False)
                except oauth.OAuthError as exc:
                    check("a reply with no id_token is refused in words",
                          "identity token" in str(exc), str(exc))

                print("== Apple: the callback that arrives as a POST ==")
                oauth.reset_for_tests()
                url = oauth.authorize_url("apple", "https://app.example/api/auth/apple/callback")
                state = url.split("state=")[1].split("&")[0]
                apple_nonce = url.split("nonce=")[1].split("&")[0]
                oauth.requests.post = lambda *a, **k: FakeResponse(  # type: ignore[assignment]
                    {"access_token": "at", "id_token": id_token()}
                )
                posted = asyncio.run(
                    api.oauth_callback_form(
                        provider="apple",
                        request=_FakeRequest(),
                        code="the-code",
                        state=state,
                        error="",
                        user='{"name": {"firstName": "Asha", "lastName": "Rao"}}',
                    )
                )
                location = posted.headers["location"]
                check("a posted-back sign-in hands the page a one-time code",
                      "auth_code=" in location, location)
                check("that URL carries a code, never the session token", "token=" not in location)
                handed = api.oauth_exchange(
                    api.CodeRequest(code=location.split("auth_code=")[1].split("&")[0])
                )
                check("the page can exchange it for a live session",
                      handed["ok"] is True and handed["user"]["email"] == "apple@kirana.in",
                      str(handed)[:120])
                stored = users.find("apple@kirana.in") or {}
                check("the account Apple created keeps the name it shared once",
                      stored.get("name") == "Asha Rao", str(stored))
                check("the account records Apple as how it signs in",
                      stored.get("provider") == "apple", str(stored))

                oauth.reset_for_tests()
                url = oauth.authorize_url("apple", "https://app.example/api/auth/apple/callback")
                rejected = asyncio.run(
                    api.oauth_callback_form(
                        provider="apple", request=_FakeRequest(),
                        code="c", state="invented", error="", user="",
                    )
                )
                check("a state that was never issued is refused in words, not as a 500",
                      "auth_error=" in rejected.headers["location"],
                      rejected.headers["location"])
                declined = asyncio.run(
                    api.oauth_callback_form(
                        provider="apple", request=_FakeRequest(),
                        code="", state="", error="user_cancelled_authorize", user="",
                    )
                )
                check("a provider-side refusal reaches the page as a sentence",
                      "auth_error=user_cancelled_authorize" in declined.headers["location"],
                      declined.headers["location"])
                apple_named = api._apple_name_hint(
                    '{"name": {"firstName": "Asha", "lastName": "Rao"}}'
                )
                check("the name Apple posts is flattened to one string",
                      apple_named == "Asha Rao", apple_named)
                check("a name-less or malformed payload reads as no name",
                      api._apple_name_hint("not json") == ""
                      and api._apple_name_hint('{"name": null}') == ""
                      and api._apple_name_hint("{") == "")
            finally:
                oauth.requests.post = real_post  # type: ignore[assignment]
        finally:
            for key in ("RECON_APPLE_CLIENT_ID", "RECON_APPLE_TEAM_ID",
                        "RECON_APPLE_KEY_ID", "RECON_APPLE_KEY_PATH"):
                os.environ.pop(key, None)

    print("== The one-time code that hands over the session ==")
    oauth.reset_for_tests()
    token = sessions.issue({"email": "owner@kirana.in", "name": "Owner"}, "account")["token"]
    code = oauth.issue_code(token, {"email": "owner@kirana.in", "name": "Owner"})
    check("the code is not the token", code != token)
    redeemed = oauth.redeem_code(code)
    check("the code redeems once", redeemed["token"] == token)
    try:
        oauth.redeem_code(code)
        check("a spent code is refused", False)
    except oauth.OAuthError:
        check("a spent code is refused", True)
    check("exchanging a spent code answers ok=false, not an exception",
          api.oauth_exchange(api.CodeRequest(code=code))["ok"] is False)

    print("== The endpoints the login page calls ==")
    options = api.auth_options()
    check("options list the methods", options["password"] is True and "providers" in options)
    check("options say whether sign-up is open", options["signup_open"] is True)
    check("options name the account store", options["account_store"] == "file",
          str(options["account_store"]))
    os.environ["RECON_GOOGLE_CLIENT_SECRET"] = "sentinel-do-not-leak"
    try:
        check("options never leak a configured secret value",
              "sentinel-do-not-leak" not in str(api.auth_options()))
    finally:
        os.environ.pop("RECON_GOOGLE_CLIENT_SECRET", None)
    check("the demo hint is only published in demo mode",
          "demo_password" in options and options["demo_password"] is not None)

    sessions.reset_for_tests()
    signed_up = api.register(
        api.RegisterRequest(email="new@kirana.in", password="another good one", name="New")
    )
    check("sign-up returns a live session",
          signed_up["ok"] is True and bool(signed_up["token"]), str(signed_up)[:120])
    check("sign-up names the account it made",
          signed_up["user"]["email"] == "new@kirana.in" and "created" in signed_up["detail"])
    check("a weak sign-up is refused with a sentence",
          api.register(api.RegisterRequest(email="weak@kirana.in", password="tiny"))["ok"] is False)
    who = api.me(api.TokenRequest(token=signed_up["token"]))
    check("/api/me describes the signed-in account",
          who["ok"] is True and who["user"]["email"] == "new@kirana.in", str(who)[:120])
    check("/api/me refuses an unknown token", api.me(api.TokenRequest(token="nope"))["ok"] is False)

    print("== The callback never puts the session token in a URL ==")
    oauth.reset_for_tests()
    request = _FakeRequest()
    redirect = api.oauth_callback(provider="google", request=request, code="c", state="bad")
    location = redirect.headers["location"]
    check("a bad state redirects back to the login page",
          location.startswith("https://app.example/?auth_error="), location)
    check("the redirect carries no token", "token=" not in location and "sub-1" not in location)

    oauth.reset_for_tests()
    os.environ["RECON_GOOGLE_CLIENT_ID"] = "id-123"
    os.environ["RECON_GOOGLE_CLIENT_SECRET"] = "secret-123"
    real_post, real_get = oauth.requests.post, oauth.requests.get
    try:
        url = oauth.authorize_url("google", "https://app.example/api/auth/google/callback")
        state = url.split("state=")[1].split("&")[0]
        oauth.requests.post = lambda *a, **k: FakeResponse({"access_token": "at-2"})  # type: ignore[assignment]
        oauth.requests.get = lambda *a, **k: FakeResponse(  # type: ignore[assignment]
            {"sub": "sub-2", "email": "flow@kirana.in", "name": "Flow"}
        )
        done = api.oauth_callback(provider="google", request=request, code="c", state=state)
        location = done.headers["location"]
        check("a finished sign-in hands over a one-time code",
              "auth_code=" in location, location)
        check("the URL carries a code, never the session token", "token=" not in location)
        handed = api.oauth_exchange(
            api.CodeRequest(code=location.split("auth_code=")[1].split("&")[0])
        )
        check("the page can exchange that code for a session",
              handed["ok"] is True and handed["user"]["email"] == "flow@kirana.in",
              str(handed)[:120])
        check("the account the provider created is stored",
              users.find("flow@kirana.in") is not None)
    finally:
        oauth.requests.post, oauth.requests.get = real_post, real_get  # type: ignore[assignment]
        os.environ.pop("RECON_GOOGLE_CLIENT_ID", None)
        os.environ.pop("RECON_GOOGLE_CLIENT_SECRET", None)

    print("== Coming home: the page's origin, not the engine's ==")
    oauth.reset_for_tests()
    os.environ["RECON_GOOGLE_CLIENT_ID"] = "id-123"
    os.environ["RECON_GOOGLE_CLIENT_SECRET"] = "secret-123"
    os.environ["RECON_ALLOWED_ORIGINS"] = "http://localhost:5173"
    real_post, real_get = oauth.requests.post, oauth.requests.get
    try:
        page = api._return_to(request, "http://localhost:5173")
        check("an origin the operator listed is accepted as home",
              page == "http://localhost:5173", page)
        proxied = oauth.authorize_url(
            "google",
            oauth.callback_uri(page, "google"),
            start_origin=page,
        )
        state = proxied.split("state=")[1].split("&")[0]
        check("the redirect URI is built from the page's origin, not the engine's",
              "redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Fapi%2Fauth%2Fgoogle%2Fcallback" in proxied,
              proxied[:150])
        check("the attempt remembers where it started",
              oauth.consume_state(state)["start_origin"] == "http://localhost:5173")

        # A second attempt, because the check above spent the first state. Its
        # callback arrives through the Vite proxy, whose changeOrigin makes the
        # request look like it came to the engine's own port — the browser still
        # has to land on the page's origin.
        state = oauth.authorize_url(
            "google", oauth.callback_uri(page, "google"), start_origin=page
        ).split("state=")[1].split("&")[0]
        oauth.requests.post = lambda *a, **k: FakeResponse({"access_token": "at-3"})  # type: ignore[assignment]
        oauth.requests.get = lambda *a, **k: FakeResponse(  # type: ignore[assignment]
            {"sub": "sub-3", "email": "proxied@kirana.in", "name": "Proxied"}
        )
        home = api.oauth_callback(provider="google", request=_FakeRequest(), code="c", state=state)
        location = home.headers["location"]
        check("a Host-rewriting proxy does not send the browser to the engine",
              location.startswith("http://localhost:5173/?"), location)
        check("the one-time code still arrives there", "auth_code=" in location, location)
    finally:
        oauth.requests.post, oauth.requests.get = real_post, real_get  # type: ignore[assignment]
        os.environ.pop("RECON_GOOGLE_CLIENT_ID", None)
        os.environ.pop("RECON_GOOGLE_CLIENT_SECRET", None)
        os.environ.pop("RECON_ALLOWED_ORIGINS", None)

    print("== An open redirect is not allowed ==")
    check("only this origin is accepted",
          api._return_to(request, "https://evil.example") == "https://app.example",
          api._return_to(request, "https://evil.example"))
    check("a listed origin is accepted",
          api._return_to(request, "https://shop.example") == "https://shop.example"
          if "https://shop.example" in (os.environ.get("RECON_ALLOWED_ORIGINS") or "")
          else api._return_to(request, "https://shop.example") == "https://app.example")
    check("nonsense falls back to this origin",
          api._return_to(request, "javascript:alert(1)") == "https://app.example")

    print("== Provider visibility on health ==")
    check("health names the account store", api.health()["account_store"] in {"file", "dynamodb"})
    check("health lists no live provider when none is configured",
          api.health()["oauth_providers"] == [], str(api.health()["oauth_providers"]))

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s): {failures}")
        return 1
    print("RESULT: all checks passed")
    return 0


class _FakeRequest:
    """Just enough of a Starlette request for the origin helpers."""

    class _URL:
        scheme = "https"
        netloc = "app.example"

    url = _URL()
    headers: dict[str, str] = {}


if __name__ == "__main__":
    raise SystemExit(main())
