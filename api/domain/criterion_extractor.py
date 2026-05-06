"""Extract eligibility criteria from a tender PDF using the LLM.

Two paths:

- ``extract_from_document(document)``: feeds the eligibility-section span text
  to the LLM with the criterion_extract.txt prompt and returns a populated
  Tender (criteria + bbox provenance).
- ``extract_stub(document)``: deterministic placeholder used when no
  ``OPENAI_API_KEY`` is configured. Yields a single stub Criterion per
  document so the upload route can still return a valid Tender JSON.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from ..core import provenance, sections
from ..core.llm_client import LLMClient
from ..core.pdf_loader import Document
from .schemas import BBox, Criterion, CriterionExtractionResult, Tender

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "criterion_extract.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _eligibility_text(document: Document) -> str:
    """Return concatenated text of eligibility-section spans (or the full doc).

    If no eligibility section is detected, the full document text is returned;
    callers should rely on the prompt's instructions to find the relevant
    clauses.
    """
    spans = list(document.all_spans)
    if not spans:
        return ""
    grouped = sections.classify(document)
    elig_idxs: list[int] = []
    for label, idxs in grouped:
        if label in ("eligibility", "compliance", "documentation"):
            elig_idxs.extend(idxs)
    chosen = elig_idxs or list(range(len(spans)))
    return " ".join(spans[i].text for i in chosen)


def _attach_bboxes(document: Document, criteria: list[Criterion]) -> list[Criterion]:
    out: list[Criterion] = []
    for c in criteria:
        bbox = c.source_bbox or provenance.quote_to_bbox(document, c.source_clause)
        out.append(c.model_copy(update={"source_bbox": bbox}))
    return out


def extract_from_document(
    document: Document,
    *,
    title: str,
    issuer: str = "Unknown",
    tender_id: Optional[str] = None,
    client: Optional[LLMClient] = None,
) -> Tender:
    """Run the LLM extractor over the document's eligibility section."""
    text = _eligibility_text(document)
    llm = client or LLMClient()
    result = llm.parse(
        system=_load_prompt(),
        user=text,
        response_format=CriterionExtractionResult,
    )
    criteria = _attach_bboxes(document, result.criteria)
    return Tender(
        id=tender_id or uuid.uuid4().hex[:12],
        title=result.title or title,
        issuer=result.issuer or issuer,
        nit_number=result.nit_number,
        estimated_value=result.estimated_value,
        criteria=criteria,
    )


def extract_stub(
    document: Document,
    *,
    title: str,
    issuer: str = "Unknown",
    tender_id: Optional[str] = None,
) -> Tender:
    """Deterministic placeholder used when no LLM key is configured.

    Emits a single ``C1`` criterion citing the first 200 chars of the document
    so the upload route still returns valid Tender JSON for the demo.
    """
    text = (document.full_text or "")[:200] or "Eligibility section not detected."
    bbox = sections.fallback_section_bbox(document)
    source_bbox = (
        BBox(page=bbox[0], x0=bbox[1], y0=bbox[2], x1=bbox[3], y1=bbox[4])
        if bbox
        else None
    )
    crit = Criterion(
        id="C1",
        name="Stub eligibility criterion",
        type="documentation",
        description="Auto-generated stub (no OPENAI_API_KEY configured).",
        threshold_operator="exists",
        source_clause=text,
        source_bbox=source_bbox,
        required_documents=[],
        is_mandatory=True,
    )
    return Tender(
        id=tender_id or uuid.uuid4().hex[:12],
        title=title,
        issuer=issuer,
        nit_number=None,
        estimated_value=None,
        criteria=[crit],
    )


def extract(
    document: Document,
    *,
    title: str,
    issuer: str = "Unknown",
    tender_id: Optional[str] = None,
    client: Optional[LLMClient] = None,
) -> Tender:
    """Top-level convenience: LLM if a key is set, otherwise stub."""
    if not os.getenv("OPENAI_API_KEY"):
        return extract_stub(document, title=title, issuer=issuer, tender_id=tender_id)
    try:
        return extract_from_document(
            document, title=title, issuer=issuer, tender_id=tender_id, client=client
        )
    except Exception as e:
        # Falling back to the stub keeps the upload route responsive, but the
        # failure must not be silent: a stub tender looks indistinguishable
        # from a successful 1-criterion extraction in the UI, which previously
        # made LLM/SDK regressions invisible. log.exception captures the
        # stack trace for diagnosis.
        log.exception(
            "criterion extraction failed for tender '%s' (%s); "
            "falling back to stub", title, type(e).__name__,
        )
        return extract_stub(document, title=title, issuer=issuer, tender_id=tender_id)
