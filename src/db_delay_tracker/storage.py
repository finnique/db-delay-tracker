"""Where raw responses get written.

Storage only moves bytes under a key. It knows nothing about XML, gzip,
stations or time: keys come from keys.raw_key, bytes come from the collector.

The interface has a single method, put. That mirrors the collector's IAM role,
which may only s3:PutObject on raw/*: code that cannot read needs no read
permission. The parser (Phase 4) will need a separate readable interface.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...


class LocalStorage:
    """Writes under a root folder, using the key as the relative path.

    Mainly a test fake and for offline runs. The layout is identical to S3,
    so `aws s3 sync <root>/raw s3://<bucket>/raw` would upload it as is.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def put(self, key: str, data: bytes) -> None:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"key {key!r} escapes the storage root")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file, then rename: a crash mid-write never leaves a
        # half-written .gz under the real key (os.replace is atomic).
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)


class S3Storage:
    """Writes objects to an S3 bucket. Needs only s3:PutObject on the key."""

    def __init__(self, bucket: str, client=None) -> None:
        if client is None:
            import boto3  # imported lazily so tests and local runs don't need it

            client = boto3.client("s3")
        self.bucket = bucket
        self._client = client

    def put(self, key: str, data: bytes) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/gzip",
        )
