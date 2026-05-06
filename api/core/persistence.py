"""SQLite-backed persistence for tenders, bidders, and evaluation matrices.

Reuses the same connection as ``core.audit`` (one SQLite file, separate
tables). Pydantic models are serialized to JSON in a single ``data_json``
column per row. On startup ``load_state`` rehydrates the in-memory dicts
held on ``app.state``.

Schema::

    tenders(id PK, data_json, blob_id, updated_at)
    bidders(id PK, tender_id, data_json, updated_at)
    matrices(tender_id PK, data_json, updated_at)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..domain.schemas import Bidder, EvaluationMatrix, Tender

log = logging.getLogger(__name__)


def init_db(conn: sqlite3.Connection) -> None:
    """Create persistence tables if they do not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tenders (
            id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL,
            blob_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bidders (
            id TEXT PRIMARY KEY,
            tender_id TEXT NOT NULL,
            data_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bidders_tender ON bidders(tender_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS matrices (
            tender_id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_tender(
    conn: sqlite3.Connection, tender: Tender, blob_id: Optional[str] = None
) -> None:
    """Upsert a tender row. ``blob_id`` is preserved if not supplied."""
    if blob_id is None:
        cur = conn.execute("SELECT blob_id FROM tenders WHERE id = ?", (tender.id,))
        row = cur.fetchone()
        if row is not None:
            blob_id = row[0]
    conn.execute(
        """
        INSERT INTO tenders (id, data_json, blob_id, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            data_json = excluded.data_json,
            blob_id = excluded.blob_id,
            updated_at = excluded.updated_at
        """,
        (tender.id, tender.model_dump_json(), blob_id, _now()),
    )
    conn.commit()


def save_bidder(conn: sqlite3.Connection, bidder: Bidder) -> None:
    """Upsert a bidder row."""
    conn.execute(
        """
        INSERT INTO bidders (id, tender_id, data_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            tender_id = excluded.tender_id,
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
        """,
        (bidder.id, bidder.tender_id, bidder.model_dump_json(), _now()),
    )
    conn.commit()


def save_matrix(conn: sqlite3.Connection, matrix: EvaluationMatrix) -> None:
    """Upsert an evaluation matrix row."""
    conn.execute(
        """
        INSERT INTO matrices (tender_id, data_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(tender_id) DO UPDATE SET
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
        """,
        (matrix.tender_id, matrix.model_dump_json(), _now()),
    )
    conn.commit()


def load_state(
    conn: sqlite3.Connection,
) -> tuple[dict[str, Tender], dict[str, dict[str, Bidder]], dict[str, EvaluationMatrix], dict[str, str]]:
    """Rehydrate ``(tenders, bidders, matrices, tender_blob)`` from SQLite.

    Returns the same shapes used on ``app.state`` so the caller can assign
    them directly. Rows whose JSON fails to parse are skipped with a warning.
    """
    tenders: dict[str, Tender] = {}
    bidders: dict[str, dict[str, Bidder]] = {}
    matrices: dict[str, EvaluationMatrix] = {}
    tender_blob: dict[str, str] = {}

    for tid, data_json, blob_id in conn.execute(
        "SELECT id, data_json, blob_id FROM tenders"
    ):
        try:
            tenders[tid] = Tender.model_validate_json(data_json)
            if blob_id:
                tender_blob[tid] = blob_id
        except Exception as e:  # pragma: no cover - defensive
            log.warning("failed to load tender %s: %s", tid, e)

    for bid, tid, data_json in conn.execute(
        "SELECT id, tender_id, data_json FROM bidders"
    ):
        try:
            bidder = Bidder.model_validate_json(data_json)
            bidders.setdefault(tid, {})[bid] = bidder
        except Exception as e:  # pragma: no cover
            log.warning("failed to load bidder %s: %s", bid, e)

    for tid, data_json in conn.execute(
        "SELECT tender_id, data_json FROM matrices"
    ):
        try:
            matrices[tid] = EvaluationMatrix.model_validate_json(data_json)
        except Exception as e:  # pragma: no cover
            log.warning("failed to load matrix for %s: %s", tid, e)

    log.info(
        "persistence load: %d tenders, %d bidders across %d tenders, %d matrices",
        len(tenders),
        sum(len(b) for b in bidders.values()),
        len(bidders),
        len(matrices),
    )
    return tenders, bidders, matrices, tender_blob
