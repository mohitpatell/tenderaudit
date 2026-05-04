"""Local content-addressable blob storage at ``./data/blobs/{sha256}``.

Each blob is stored under its SHA-256 hex digest. Reads return raw bytes;
writes are idempotent. The optional ``meta`` JSON sidecar records the original
filename and content type for retrieval (e.g., for the ``/files/{blob_id}``
static route).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_ROOT = "./data/blobs"


@dataclass(frozen=True)
class BlobMeta:
    blob_id: str
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size: int = 0


def _root(root: Optional[str] = None) -> Path:
    p = Path(root or os.getenv("BLOB_ROOT", DEFAULT_ROOT))
    p.mkdir(parents=True, exist_ok=True)
    return p


def put_bytes(
    data: bytes,
    *,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    root: Optional[str] = None,
) -> BlobMeta:
    """Write ``data`` to a blob keyed by its SHA-256. Idempotent."""
    digest = hashlib.sha256(data).hexdigest()
    root_p = _root(root)
    blob_path = root_p / digest
    if not blob_path.exists():
        blob_path.write_bytes(data)
    meta = BlobMeta(
        blob_id=digest,
        filename=filename,
        content_type=content_type,
        size=len(data),
    )
    meta_path = root_p / f"{digest}.meta.json"
    if not meta_path.exists() and (filename or content_type):
        meta_path.write_text(
            json.dumps(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "size": len(data),
                },
                sort_keys=True,
            )
        )
    return meta


def get_path(blob_id: str, *, root: Optional[str] = None) -> Optional[Path]:
    """Return the absolute path to the blob, or None if it does not exist."""
    p = _root(root) / blob_id
    return p if p.exists() else None


def get_bytes(blob_id: str, *, root: Optional[str] = None) -> Optional[bytes]:
    p = get_path(blob_id, root=root)
    return p.read_bytes() if p else None


def get_meta(blob_id: str, *, root: Optional[str] = None) -> Optional[BlobMeta]:
    p = _root(root) / f"{blob_id}.meta.json"
    if not p.exists():
        return BlobMeta(blob_id=blob_id) if get_path(blob_id, root=root) else None
    raw = json.loads(p.read_text())
    return BlobMeta(
        blob_id=blob_id,
        filename=raw.get("filename"),
        content_type=raw.get("content_type"),
        size=int(raw.get("size", 0)),
    )
