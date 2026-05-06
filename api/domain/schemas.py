"""Pydantic schemas for TenderAudit.

The full ``Verdict`` carries Evidence with bbox; for OpenAI Structured Outputs
we use the slimmer ``VerdictLLM`` and ``EvidenceLLM`` (no bbox), and post-
populate Evidence.bbox from the retrieved chunk's source span at the call site.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class BBox(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


class Criterion(BaseModel):
    id: str
    name: str
    type: Literal["financial", "technical", "compliance", "documentation"]
    description: str
    threshold_value: Optional[float] = None
    threshold_unit: Optional[str] = None
    threshold_operator: Literal[">=", "<=", "==", "exists", "not_blacklisted"] = "exists"
    source_clause: str
    source_bbox: Optional[BBox] = None
    required_documents: list[str] = Field(default_factory=list)
    is_mandatory: bool = True
    approved: bool = False


class Tender(BaseModel):
    id: str
    title: str
    issuer: str
    nit_number: Optional[str] = None
    estimated_value: Optional[float] = None
    criteria: list[Criterion] = Field(default_factory=list)


class BidderDoc(BaseModel):
    id: str
    bidder_id: str
    filename: str
    doc_type: Optional[str] = None
    blob_id: str


class Bidder(BaseModel):
    id: str
    tender_id: str
    name: str
    documents: list[BidderDoc] = Field(default_factory=list)


class Evidence(BaseModel):
    bidder_doc_id: str
    page: int
    bbox: BBox
    quote: str
    score: float


class Verdict(BaseModel):
    criterion_id: str
    bidder_id: str
    verdict: Literal["Eligible", "NotEligible", "NeedsManualReview"]
    confidence: float
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)


class EvaluationMatrix(BaseModel):
    tender_id: str
    bidders: list[Bidder]
    criteria: list[Criterion]
    verdicts: list[Verdict]


# ---------------------------------------------------------------------------
# Slim LLM-output variants (no bbox; bbox is post-populated from RAG hits).
# ---------------------------------------------------------------------------


class EvidenceLLM(BaseModel):
    bidder_doc_id: str
    page: int
    quote: str


class VerdictLLM(BaseModel):
    criterion_id: str
    bidder_id: str
    verdict: Literal["Eligible", "NotEligible", "NeedsManualReview"]
    confidence: float
    explanation: str
    evidence: list[EvidenceLLM] = Field(default_factory=list)


class CriterionExtractionResult(BaseModel):
    """Wrapper used as the OpenAI response_format for criterion extraction."""

    criteria: list[Criterion]
    nit_number: Optional[str] = None
    title: Optional[str] = None
    issuer: Optional[str] = None
    estimated_value: Optional[float] = None
