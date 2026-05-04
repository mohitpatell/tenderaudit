"""Tender upload + criteria edit routes."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from ...core import audit, pdf_loader, storage
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

    audit.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.upload",
        entity_type="tender",
        entity_id=tender.id,
        payload={"blob_id": blob.blob_id, "criteria_count": len(tender.criteria)},
    )
    return {"tender": tender.model_dump(), "blob_id": blob.blob_id}


@router.get("/{tender_id}")
async def get_tender(request: Request, tender_id: str) -> dict:
    state = _state(request)
    tender = state.tenders.get(tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    return tender.model_dump()


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
    audit.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="tender.criteria.edit",
        entity_type="tender",
        entity_id=tender_id,
        payload={"new_count": len(new_criteria)},
    )
    return updated.model_dump()
