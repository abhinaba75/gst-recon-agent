"""User accounts and multi-provider identities for the web app.

The login page offers three kinds of sign-in, and this module is what makes
them real rather than decorative:

* a password account created on this deployment (register + sign in),
* the operator account configured with ``RECON_UI_EMAIL`` / ``RECON_UI_PASSWORD``,
* an identity handed over by an OAuth provider (see :mod:`backend.oauth`).

Two storage backends, chosen by configuration, and both of them degrade the
same way — a storage outage returns a readable sentence, never a stack trace:

* ``RECON_USERS_TABLE`` — the DynamoDB table from
  ``infrastructure/recon-agent-core.yaml``. This is the production shape.
* otherwise a JSON file (``RECON_USERS_FILE``, default ``.recon-users.json``
  in the project root). Single-worker demo storage, and the file is gitignored
  because it holds password hashes.

Passwords are hashed with ``hashlib.scrypt`` (stdlib, memory-hard) using a
per-user random salt, and compared with :func:`secrets.compare_digest`. Nothing
here ever returns a hash to a caller: :func:`public` is the only way a user
record leaves this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: Eight characters is the floor, not a suggestion: this account can dispatch
#: real WhatsApp notices to real vendors.
MIN_PASSWORD = 8

#: scrypt cost. n=2**14 with r=8 is about 16 MB and a few milliseconds per
#: hash — expensive enough to matter for an attacker, cheap enough for a login.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

_lock = threading.Lock()
_dynamo = None

_REGION_KEYS = ("RECON_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION")


# ── configuration ───────────────────────────────────────────────────────────


def table_name() -> str | None:
    """The DynamoDB table for accounts, or None to use the local file."""
    return os.environ.get("RECON_USERS_TABLE") or None


def file_path() -> Path:
    """Where accounts live when no table is configured."""
    configured = os.environ.get("RECON_USERS_FILE")
    return Path(configured) if configured else ROOT / ".recon-users.json"


def store_kind() -> str:
    """``dynamodb`` or ``file`` — stated so the UI can be honest about it."""
    return "dynamodb" if table_name() else "file"


def accounts_enabled() -> bool:
    """Registration is open unless the operator disables it explicitly."""
    return (os.environ.get("RECON_ALLOW_SIGNUP") or "1").strip() not in {"0", "false", "no"}


# ── password hashing ────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """``scrypt$n$r$p$salt$hash`` — parameters travel with the hash so a future
    cost change can verify old passwords instead of invalidating them."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check against a stored hash. False on any malformed input."""
    if not password or not encoded:
        return False
    try:
        scheme, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
    except Exception:  # noqa: BLE001 — a broken hash must read as "no match"
        return False
    try:
        return secrets.compare_digest(candidate.hex(), digest_hex)
    except Exception:  # noqa: BLE001
        return False


# ── records ─────────────────────────────────────────────────────────────────


def normalise_email(email: str) -> str | None:
    """Lower-cased address, or None when it is not an address at all."""
    clean = (email or "").strip().lower()
    return clean if _EMAIL_RE.match(clean) else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _display_name(email: str) -> str:
    local = email.split("@", 1)[0]
    return local.replace(".", " ").replace("_", " ").title() or "Operator"


def public(record: dict[str, Any]) -> dict[str, Any]:
    """The record as the browser may see it: never a hash, never a salt."""
    return {
        "email": record.get("email", ""),
        "name": record.get("name") or _display_name(record.get("email", "")),
        "provider": record.get("provider", "password"),
        "created_at": record.get("created_at", ""),
        "last_login_at": record.get("last_login_at", ""),
    }


def _dynamo_client() -> Any:
    global _dynamo
    if _dynamo is None:
        import boto3  # imported lazily: boto3 is only needed when configured

        region = next(
            (os.environ[k] for k in _REGION_KEYS if os.environ.get(k)), "us-east-1"
        )
        _dynamo = boto3.client("dynamodb", region_name=region)
    return _dynamo


def _load_file() -> dict[str, dict[str, Any]]:
    path = file_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — a corrupt store must not take login down
        return {}


def _save_file(users: dict[str, dict[str, Any]]) -> bool:
    path = file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(users, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:  # noqa: BLE001
        return False


def _get(email: str) -> dict[str, Any] | None:
    """One record by address, from whichever store is configured."""
    name = table_name()
    if not name:
        return _load_file().get(email)
    try:
        resp = _dynamo_client().get_item(
            TableName=name,
            Key={"pk": {"S": f"user#{email}"}, "sk": {"S": "profile"}},
        )
        item = resp.get("Item")
        return json.loads(item["profile"]["S"]) if item and "profile" in item else None
    except Exception:  # noqa: BLE001
        return None


def _put(record: dict[str, Any]) -> bool:
    """Write one record, keeping the store consistent either way."""
    email = record["email"]
    name = table_name()
    if not name:
        with _lock:
            users = _load_file()
            users[email] = record
            return _save_file(users)
    try:
        _dynamo_client().put_item(
            TableName=name,
            Item={
                "pk": {"S": f"user#{email}"},
                "sk": {"S": "profile"},
                "email": {"S": email},
                "provider": {"S": record.get("provider", "password")},
                "profile": {"S": json.dumps(record, separators=(",", ":"))},
            },
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def count() -> int:
    """How many accounts exist. Used by tests and by the operator view."""
    name = table_name()
    if not name:
        return len(_load_file())
    try:
        resp = _dynamo_client().scan(TableName=name, Select="COUNT")
        return int(resp.get("Count", 0))
    except Exception:  # noqa: BLE001
        return 0


# ── the operations the API calls ────────────────────────────────────────────


def register(email: str, password: str, name: str = "") -> dict[str, Any]:
    """Create a password account. Never raises.

    Returns ``{"ok": True, "user": {...}}`` or ``{"ok": False, "detail": ...}``
    with one sentence naming what to fix, in the language of a shop owner.
    """
    if not accounts_enabled():
        return {
            "ok": False,
            "detail": "This deployment does not accept new accounts.",
        }
    address = normalise_email(email)
    if not address:
        return {"ok": False, "detail": "That does not look like an email address."}
    if len(password or "") < MIN_PASSWORD:
        return {
            "ok": False,
            "detail": f"Use at least {MIN_PASSWORD} characters for the password.",
        }
    if _get(address):
        return {
            "ok": False,
            "detail": "An account already exists for that email. Sign in instead.",
        }

    now = _now_iso()
    record = {
        "email": address,
        "name": (name or "").strip() or _display_name(address),
        "provider": "password",
        "password": hash_password(password),
        "identities": {},
        "created_at": now,
        "last_login_at": now,
    }
    if not _put(record):
        return {
            "ok": False,
            "detail": "The account could not be stored just now. Please try again.",
        }
    return {"ok": True, "user": public(record)}


def authenticate(email: str, password: str) -> dict[str, Any]:
    """Verify one password sign-in. Never raises, never says which half failed."""
    address = normalise_email(email)
    generic = {"ok": False, "detail": "Those credentials did not match."}
    if not address or not password:
        return generic

    record = _get(address)
    if not record or not record.get("password"):
        # Still spend the time: a fast "no such user" is a user-enumeration oracle.
        verify_password(password, hash_password("timing-equaliser"))
        return generic
    if not verify_password(password, record["password"]):
        return generic

    record["last_login_at"] = _now_iso()
    record["provider"] = "password"
    _put(record)
    return {"ok": True, "user": public(record)}


def upsert_identity(
    provider: str,
    subject: str,
    email: str,
    name: str = "",
) -> dict[str, Any]:
    """Find or create the account behind an OAuth identity. Never raises.

    Signing in with Google for the first time creates the account; signing in
    again — or linking from a password account with the same address — reuses
    it, so one person does not end up with two workspaces.
    """
    address = normalise_email(email)
    if not address:
        return {
            "ok": False,
            "detail": (
                f"The {provider} account did not share an email address, "
                "which this deployment needs to identify you."
            ),
        }

    now = _now_iso()
    record = _get(address) or {
        "email": address,
        "name": "",
        "provider": provider,
        "identities": {},
        "created_at": now,
        "last_login_at": now,
    }

    identities = dict(record.get("identities") or {})
    identities[provider] = {"sub": subject, "linked_at": now}
    record["identities"] = identities
    record["provider"] = provider
    record["name"] = record.get("name") or (name or "").strip() or _display_name(address)
    record["last_login_at"] = now

    if not _put(record):
        return {
            "ok": False,
            "detail": "The account could not be updated just now. Please try again.",
        }
    return {"ok": True, "user": public(record)}


def find(email: str) -> dict[str, Any] | None:
    """Public view of an account, or None — for the operator and the API."""
    record = _get((email or "").strip().lower())
    return public(record) if record else None


def ensure_operator(email: str, name: str = "") -> dict[str, Any]:
    """Record the env-configured operator account on first sign-in.

    ``RECON_UI_EMAIL`` / ``RECON_UI_PASSWORD`` remain the source of truth for
    that account (they are compared in constant time by
    :mod:`backend.session`); this only gives it a row so it appears in the
    account list like any other user.
    """
    address = normalise_email(email)
    if not address:
        return {"email": email, "name": name or _display_name(email), "provider": "operator"}
    record = _get(address)
    if record:
        record["last_login_at"] = _now_iso()
        record["provider"] = "operator"
        _put(record)
        return public(record)
    record = {
        "email": address,
        "name": name or _display_name(address),
        "provider": "operator",
        "identities": {},
        "created_at": _now_iso(),
        "last_login_at": _now_iso(),
    }
    _put(record)
    return public(record)


def reset_for_tests(path: str) -> None:
    """Point the file store somewhere disposable and empty it (tests only)."""
    os.environ["RECON_USERS_FILE"] = path
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    time.sleep(0)  # keep the signature honest about doing work
