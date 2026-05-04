"""Append-only audit log with SHA-256 hash chain backed by SQLite.

Schema::

    audit_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT,
      actor TEXT,
      action TEXT,
      entity_type TEXT,
      entity_id TEXT,
      payload_json TEXT,
      prev_hash TEXT,
      this_hash TEXT
    )

``this_hash = sha256(prev_hash + canonical_json(payload)).hexdigest()``

``verify_chain()`` walks the table by ``id`` and recomputes each row's hash;
any tampering with ``payload_json`` or ``prev_hash`` causes it to return False.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

GENESIS = "0" * 64


def init_db(conn: sqlite3.Connection) -> None:
    """Create the audit_log table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            this_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()


def canonical_json(payload: Any) -> str:
    """Deterministic JSON encoding (sorted keys, no whitespace)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(prev_hash: str, payload_json: str) -> str:
    return hashlib.sha256((prev_hash + payload_json).encode("utf-8")).hexdigest()


def append(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: Any,
) -> int:
    """Append one row, return its ``id``. Hash links to previous row's hash."""
    payload_json = canonical_json(payload)
    cur = conn.execute("SELECT this_hash FROM audit_log ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row[0] if row else GENESIS
    this_hash = _hash(prev_hash, payload_json)
    ts = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO audit_log (ts, actor, action, entity_type, entity_id,
                               payload_json, prev_hash, this_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, actor, action, entity_type, entity_id, payload_json, prev_hash, this_hash),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def verify_chain(conn: sqlite3.Connection) -> tuple[bool, Optional[int]]:
    """Return ``(valid, broken_at_id)``.

    ``valid=True`` means every row hash-links correctly back to the genesis
    hash. ``broken_at_id`` is the id of the first row that fails to verify, or
    ``None`` if the chain is valid.
    """
    cur = conn.execute(
        """
        SELECT id, payload_json, prev_hash, this_hash
        FROM audit_log
        ORDER BY id ASC
        """
    )
    expected_prev = GENESIS
    for row_id, payload_json, prev_hash, this_hash in cur.fetchall():
        if prev_hash != expected_prev:
            return False, int(row_id)
        if _hash(prev_hash, payload_json) != this_hash:
            return False, int(row_id)
        expected_prev = this_hash
    return True, None


def list_rows(
    conn: sqlite3.Connection,
    *,
    entity_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return audit rows ordered by id DESC, optionally filtered by entity."""
    if entity_id:
        cur = conn.execute(
            "SELECT id, ts, actor, action, entity_type, entity_id, payload_json,"
            " prev_hash, this_hash FROM audit_log WHERE entity_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (entity_id, limit),
        )
    else:
        cur = conn.execute(
            "SELECT id, ts, actor, action, entity_type, entity_id, payload_json,"
            " prev_hash, this_hash FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
