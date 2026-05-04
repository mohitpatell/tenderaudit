"""Evaluate / sign / audit-list / audit-verify routes."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ...core import audit as audit_mod
from ...core import storage
from .. import eval_engine, sign_pdf

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["audit"])


def _state(req: Request) -> Any:
    return req.app.state


@router.post("/tenders/{tender_id}/evaluate")
async def evaluate_tender(request: Request, tender_id: str) -> dict:
    state = _state(request)
    tender = state.tenders.get(tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    bidders = list(state.bidders.get(tender_id, {}).values())
    if not bidders:
        raise HTTPException(status_code=400, detail="no bidders uploaded")

    matrix = eval_engine.evaluate(tender, bidders)
    state.matrices[tender_id] = matrix
    audit_mod.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.evaluate",
        entity_type="tender",
        entity_id=tender_id,
        payload={
            "bidder_count": len(bidders),
            "criteria_count": len(tender.criteria),
            "verdict_count": len(matrix.verdicts),
        },
    )
    return matrix.model_dump()


@router.get("/tenders/{tender_id}/matrix")
async def get_matrix(request: Request, tender_id: str) -> dict:
    state = _state(request)
    matrix = state.matrices.get(tender_id)
    if matrix is None:
        raise HTTPException(status_code=404, detail="no evaluation yet")
    return matrix.model_dump()


@router.post("/tenders/{tender_id}/sign")
async def sign_tender(request: Request, tender_id: str) -> dict:
    state = _state(request)
    matrix = state.matrices.get(tender_id)
    if matrix is None:
        raise HTTPException(status_code=404, detail="no evaluation yet")

    out_dir = Path(os.getenv("BLOB_ROOT", "./data/blobs")).parent / "signed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"{tender_id}-{uuid.uuid4().hex[:6]}.pdf")
    result = sign_pdf.sign_evaluation(
        matrix,
        out_path,
        chain_root=str(Path(os.getenv("AUDIT_DB", "./data/audit.db"))),
    )

    pdf_bytes = Path(out_path).read_bytes()
    blob = storage.put_bytes(
        pdf_bytes,
        filename=f"audit-{tender_id}.pdf",
        content_type="application/pdf",
    )
    audit_mod.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.sign",
        entity_type="tender",
        entity_id=tender_id,
        payload={"blob_id": blob.blob_id, "signed": result["signed"]},
    )
    return {"blob_id": blob.blob_id, **result}


@router.get("/audit")
async def list_audit(request: Request, limit: int = 50) -> dict:
    state = _state(request)
    rows = audit_mod.list_rows(state.audit_conn, limit=limit)
    return {"rows": rows}


@router.get("/audit/verify")
async def verify_audit(request: Request) -> dict:
    state = _state(request)
    valid, broken_at = audit_mod.verify_chain(state.audit_conn)
    return {"valid": valid, "broken_at": broken_at}
