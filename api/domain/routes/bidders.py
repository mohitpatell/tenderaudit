"""Bidder bundle upload + drill-down routes."""

from __future__ import annotations

import io
import logging
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ...core import audit, pdf_loader, persistence, storage
from ..schemas import BBox, Bidder, BidderDoc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["bidders"])


def _state(req: Request) -> Any:
    return req.app.state


def _classify_doc_type(filename: str) -> str:
    """Cheap filename-based classification. Real systems would do this via LLM."""
    f = (filename or "").lower()
    if "turnover" in f or "ca_cert" in f or "ca-cert" in f:
        return "ca_turnover_cert"
    if "balance" in f or "audited" in f:
        return "balance_sheet"
    if "iso" in f:
        return "iso_cert"
    if "oem" in f:
        return "oem_letter"
    if "experience" in f or "work_order" in f or "completion" in f:
        return "experience_cert"
    if "blacklist" in f:
        return "blacklist_undertaking"
    if "gst" in f:
        return "gst_cert"
    if "epf" in f:
        return "epfo_cert"
    if "msme" in f:
        return "msme_cert"
    if "integrity" in f:
        return "integrity_pact"
    return "other"


@router.post("/tenders/{tender_id}/bidders/upload")
async def upload_bidder(
    request: Request,
    tender_id: str,
    file: UploadFile = File(...),
    bidder_name: str = Form(...),
) -> dict:
    state = _state(request)
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="tender not found")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    bidder_id = uuid.uuid4().hex[:12]
    docs: list[BidderDoc] = []
    pages_by_doc_id: dict[str, list[tuple[int, str, BBox]]] = {}

    if file.filename and file.filename.lower().endswith(".zip"):
        items = _extract_zip(raw)
    else:
        items = [(file.filename or "bidder.pdf", raw)]

    for member_name, pdf_bytes in items:
        if not pdf_bytes:
            continue
        blob = storage.put_bytes(
            pdf_bytes, filename=member_name, content_type="application/pdf"
        )
        doc_id = uuid.uuid4().hex[:12]
        doc_type = _classify_doc_type(member_name)
        bd = BidderDoc(
            id=doc_id,
            bidder_id=bidder_id,
            filename=member_name,
            doc_type=doc_type,
            blob_id=blob.blob_id,
        )
        docs.append(bd)
        try:
            pages = _load_pages_for_indexing(pdf_bytes)
            pages_by_doc_id[doc_id] = pages
        except Exception as e:  # pragma: no cover - defensive
            log.warning("page load failed for %s: %s", member_name, e)
            pages_by_doc_id[doc_id] = []

    bidder = Bidder(id=bidder_id, tender_id=tender_id, name=bidder_name, documents=docs)
    state.bidders.setdefault(tender_id, {})[bidder_id] = bidder
    persistence.save_bidder(state.audit_conn, bidder)

    # Index into RAG. Indexing failures are NOT silently swallowed: without an
    # index, every verdict for this bidder will fall back to NeedsManualReview
    # ("no evidence retrieved"), which is indistinguishable from a real
    # uncertainty signal in the matrix.
    try:
        from .. import rag

        indexed = rag.index_bidder_docs(tender_id, bidder, pages_by_doc_id)
        if indexed == 0:
            log.error(
                "RAG indexing produced 0 chunks for bidder %s (%s) -- "
                "check embedder compatibility and PDF text extraction",
                bidder_id, bidder_name,
            )
        else:
            log.info(
                "RAG indexed %d chunks for bidder %s (%s)",
                indexed, bidder_id, bidder_name,
            )
    except Exception as e:  # pragma: no cover
        log.exception(
            "RAG indexing failed for bidder %s (%s): %s",
            bidder_id, bidder_name, e,
        )

    audit.append(
        state.audit_conn,
        actor=os.getenv("ACTOR", "system"),
        action="bidder.upload",
        entity_type="bidder",
        entity_id=bidder_id,
        payload={"tender_id": tender_id, "doc_count": len(docs)},
    )
    return {"bidder": bidder.model_dump()}


def _extract_zip(raw: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                if not name.lower().endswith(".pdf"):
                    continue
                out.append((name, zf.read(name)))
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail=f"invalid zip: {e}")
    return out


def _load_pages_for_indexing(pdf_bytes: bytes) -> list[tuple[int, str, BBox]]:
    """Return ``(page_no, page_text, page_bbox)`` per page."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        doc = pdf_loader.load_pdf(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    out: list[tuple[int, str, BBox]] = []
    for page in doc.pages:
        if not page.spans:
            continue
        text = " ".join(s.text for s in page.spans)
        x0 = min(s.bbox[0] for s in page.spans)
        y0 = min(s.bbox[1] for s in page.spans)
        x1 = max(s.bbox[2] for s in page.spans)
        y1 = max(s.bbox[3] for s in page.spans)
        out.append(
            (page.page_no, text, BBox(page=page.page_no, x0=x0, y0=y0, x1=x1, y1=y1))
        )
    return out


@router.get("/bidders/{bidder_id}/criterion/{cid}")
async def drill_down(request: Request, bidder_id: str, cid: str) -> dict:
    state = _state(request)
    matrix = None
    bidder = None
    tender_id = None
    for tid, bidders in state.bidders.items():
        if bidder_id in bidders:
            bidder = bidders[bidder_id]
            tender_id = tid
            matrix = state.matrices.get(tid)
            break
    if bidder is None or tender_id is None:
        raise HTTPException(status_code=404, detail="bidder not found")
    if matrix is None:
        raise HTTPException(status_code=404, detail="no evaluation yet for this tender")

    verdict = next(
        (v for v in matrix.verdicts if v.bidder_id == bidder_id and v.criterion_id == cid),
        None,
    )
    if verdict is None:
        raise HTTPException(status_code=404, detail="verdict not found")
    blob_ids = {d.id: d.blob_id for d in bidder.documents}
    return {
        "bidder_id": bidder_id,
        "criterion_id": cid,
        "verdict": verdict.model_dump(),
        "doc_blob_ids": blob_ids,
    }
