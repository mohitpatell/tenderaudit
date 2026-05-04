"""SQLite hash-chain audit log: append + verify_chain + tamper detection."""

from __future__ import annotations

import sqlite3

from api.core import audit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    audit.init_db(conn)
    return conn


def test_append_and_verify_chain_clean():
    conn = _conn()
    audit.append(
        conn,
        actor="alice",
        action="tender.upload",
        entity_type="tender",
        entity_id="T1",
        payload={"title": "CRPF Tents NIT-2024"},
    )
    audit.append(
        conn,
        actor="alice",
        action="tender.criteria.edit",
        entity_type="tender",
        entity_id="T1",
        payload={"new_count": 7},
    )
    audit.append(
        conn,
        actor="bob",
        action="tender.evaluate",
        entity_type="tender",
        entity_id="T1",
        payload={"bidder_count": 3, "verdict_count": 21},
    )
    valid, broken_at = audit.verify_chain(conn)
    assert valid is True
    assert broken_at is None


def test_tampered_payload_breaks_chain():
    conn = _conn()
    audit.append(
        conn,
        actor="alice",
        action="tender.upload",
        entity_type="tender",
        entity_id="T1",
        payload={"x": 1},
    )
    audit.append(
        conn,
        actor="alice",
        action="tender.evaluate",
        entity_type="tender",
        entity_id="T1",
        payload={"x": 2},
    )
    # Tamper: rewrite a payload without recomputing this_hash.
    conn.execute(
        "UPDATE audit_log SET payload_json = ? WHERE id = 1",
        (audit.canonical_json({"x": 999}),),
    )
    conn.commit()

    valid, broken_at = audit.verify_chain(conn)
    assert valid is False
    assert broken_at == 1


def test_tampered_prev_hash_breaks_chain():
    conn = _conn()
    audit.append(
        conn,
        actor="alice",
        action="a1",
        entity_type="t",
        entity_id="T1",
        payload={"x": 1},
    )
    audit.append(
        conn,
        actor="alice",
        action="a2",
        entity_type="t",
        entity_id="T1",
        payload={"x": 2},
    )
    conn.execute("UPDATE audit_log SET prev_hash = ? WHERE id = 2", ("0" * 64,))
    conn.commit()
    valid, broken_at = audit.verify_chain(conn)
    assert valid is False
    assert broken_at == 2


def test_list_rows_filters_by_entity():
    conn = _conn()
    audit.append(
        conn,
        actor="alice",
        action="a",
        entity_type="t",
        entity_id="T1",
        payload={"x": 1},
    )
    audit.append(
        conn,
        actor="alice",
        action="a",
        entity_type="t",
        entity_id="T2",
        payload={"x": 2},
    )
    rows_t1 = audit.list_rows(conn, entity_id="T1")
    assert len(rows_t1) == 1
    assert rows_t1[0]["entity_id"] == "T1"
