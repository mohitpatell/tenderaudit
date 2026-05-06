"""Tender upload + criteria edit routes."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from ...core import audit, pdf_loader, persistence, storage
from .. import criterion_extractor
from ..schemas import Criterion, Tender

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenders", tags=["tenders"])


def _state(req: Request) -> Any:
    return req.app.state


@router.post("/upload")
async def upload_tender(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = None,
    issuer: str | None = None,
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    blob = storage.put_bytes(
        raw, filename=file.filename, content_type=file.content_type or "application/pdf"
    )

    # Write to a temp file for PyMuPDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        document = pdf_loader.load_pdf(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    tender_id = uuid.uuid4().hex[:12]
    tender = criterion_extractor.extract(
        document,
        title=title or (file.filename or "Untitled tender"),
        issuer=issuer or "Unknown",
        tender_id=tender_id,
    )

    state = _state(request)
    state.tenders[tender.id] = tender
    state.tender_blob[tender.id] = blob.blob_id
    persistence.save_tender(state.audit_conn, tender, blob_id=blob.blob_id)

    audit.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.upload",
        entity_type="tender",
        entity_id=tender.id,
        payload={"blob_id": blob.blob_id, "criteria_count": len(tender.criteria)},
    )
    return {"tender": tender.model_dump(), "blob_id": blob.blob_id}


@router.get("")
async def list_tenders(request: Request) -> list[dict]:
    """List all tenders currently in memory with summary counts."""
    state = _state(request)
    out: list[dict] = []
    for tid, tender in state.tenders.items():
        criteria = getattr(tender, "criteria", []) or []
        bidders = state.bidders.get(tid) or {}
        matrix = state.matrices.get(tid)
        verdicts = []
        if matrix is not None:
            verdicts = getattr(matrix, "verdicts", []) or []
        not_eligible = sum(
            1 for v in verdicts if getattr(v, "verdict", None) == "NotEligible"
        )
        manual = sum(
            1 for v in verdicts if getattr(v, "verdict", None) == "NeedsManualReview"
        )
        out.append(
            {
                "id": tid,
                "title": getattr(tender, "title", None),
                "issuer": getattr(tender, "issuer", None),
                "nit_number": getattr(tender, "nit_number", None),
                "criteria_count": len(criteria),
                "bidder_count": len(bidders),
                "verdict_count": len(verdicts),
                "not_eligible_count": not_eligible,
                "manual_review_count": manual,
            }
        )
    return out


@router.get("/{tender_id}")
async def get_tender(request: Request, tender_id: str) -> dict:
    state = _state(request)
    tender = state.tenders.get(tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    return tender.model_dump()


@router.get("/{tender_id}/bidders")
async def list_bidders(request: Request, tender_id: str) -> list[dict]:
    """Return per-bidder summaries for a given tender."""
    state = _state(request)
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="tender not found")
    bidders = state.bidders.get(tender_id) or {}
    return [
        {
            "id": bid_id,
            "tender_id": tender_id,
            "name": getattr(b, "name", None),
            "doc_count": len(getattr(b, "documents", []) or []),
        }
        for bid_id, b in bidders.items()
    ]


@router.patch("/{tender_id}/criteria")
async def patch_criteria(
    request: Request, tender_id: str, criteria: list[dict]
) -> dict:
    state = _state(request)
    tender: Tender | None = state.tenders.get(tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    new_criteria = [Criterion(**c) for c in criteria]
    updated = tender.model_copy(update={"criteria": new_criteria})
    state.tenders[tender_id] = updated
    persistence.save_tender(state.audit_conn, updated)
    audit.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.criteria.edit",
        entity_type="tender",
        entity_id=tender_id,
        payload={"new_count": len(new_criteria)},
    )
    return updated.model_dump()


@router.post("/{tender_id}/criteria/approve")
async def approve_criteria(
    request: Request, tender_id: str, body: dict
) -> dict:
    """Mark the given criterion ids as approved on this tender."""
    state = _state(request)
    tender: Tender | None = state.tenders.get(tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    raw_ids = body.get("criteria_ids", []) if isinstance(body, dict) else []
    if not isinstance(raw_ids, list):
        raise HTTPException(status_code=400, detail="criteria_ids must be a list")
    ids = {str(x) for x in raw_ids}
    if not ids:
        raise HTTPException(status_code=400, detail="criteria_ids is empty")
    updated_criteria = [
        c.model_copy(update={"approved": True}) if c.id in ids else c
        for c in tender.criteria
    ]
    updated = tender.model_copy(update={"criteria": updated_criteria})
    state.tenders[tender_id] = updated
    persistence.save_tender(state.audit_conn, updated)
    audit.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.criteria.approve",
        entity_type="tender",
        entity_id=tender_id,
        payload={"approved_ids": sorted(ids)},
    )
    return updated.model_dump()
