"""S3 archive for every document the reconciliation agent ingested.

The ``recon-agent-uploads-demo-<account>`` bucket (deployed via
``infrastructure/recon-agent-core.yaml``) is private, versioned and
AES256-encrypted; the app's least-privilege identity may only Put/Get/List
inside it. Archiving uploads gives the audit story a second leg: the DynamoDB
run rows record the *result* of a reconciliation, the S3 objects record the
*exact input bytes* the agent saw — download them and reproduce the run.

Layout (one object per source document):

    uploads/<period>/<sha256[:16]>/<filename>

Keys are content-addressed, so re-uploading the identical file is a no-op
(overwrite with the same bytes); a corrected file gets a new key and both
versions stay archived. Versioning is enabled on the bucket as a backstop.

Every function degrades gracefully: with no bucket configured or no network,
callers get ``None`` / ``False`` and the UI narration says so.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # only for type hints; boto3 is imported lazily
    import boto3

_REGION_KEYS = ("RECON_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION")

_s3 = None  # reused across calls; one boto3 client per process


def bucket_name() -> str | None:
    """Configured uploads bucket, or None when archiving is not configured."""
    name = os.environ.get("RECON_UPLOADS_BUCKET")
    return name or None


def _client() -> Any:
    """Process-wide S3 client (keeps imports cheap, reuses the pool)."""
    global _s3
    if _s3 is None:
        import boto3

        region = next((os.environ[k] for k in _REGION_KEYS if os.environ.get(k)),
                      "us-east-1")
        _s3 = boto3.client("s3", region_name=region)
    return _s3


def _period_prefix(period: str) -> str:
    """Period label for the key prefix; falls back to the current UTC month."""
    return (period or datetime.now(timezone.utc).strftime("%Y-%m")).replace(" ", "-")


def archive_upload(data: bytes, filename: str, period: str = "") -> str | None:
    """Put one uploaded document in the archive. Returns the S3 key or None.

    The key embeds the content hash, so identical re-uploads land on the same
    object and a corrected file is archived alongside (not over) the original.
    """
    bucket = bucket_name()
    if not bucket:
        return None
    digest = hashlib.sha256(data).hexdigest()[:16]
    key = f"uploads/{_period_prefix(period)}/{digest}/{filename}"
    try:
        _client().put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ServerSideEncryption="AES256",
        )
    except Exception:  # noqa: BLE001 — archiving degrades, the demo must not
        return None
    return key


def list_archive(prefix: str = "uploads/", limit: int = 10) -> list[dict[str, str]]:
    """Newest archived documents, newest first; [] when unavailable."""
    bucket = bucket_name()
    if not bucket:
        return []
    try:
        resp = _client().list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
    except Exception:  # noqa: BLE001
        return []
    items = [
        {
            "key": o["Key"],
            "at": o["LastModified"].strftime("%Y-%m-%d %H:%M"),
            "bytes": str(o["Size"]),
        }
        for o in resp.get("Contents", [])
        if not o["Key"].endswith("/")
    ]
    items.sort(key=lambda o: o["at"], reverse=True)
    return items[: max(limit, 0)]
