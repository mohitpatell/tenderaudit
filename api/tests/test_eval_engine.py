"""Evaluation engine: end-to-end with monkeypatched RAG + LLM.

Verifies:
- ``evaluate()`` produces ``len(criteria) * len(bidders)`` verdicts
- Every NotEligible carries non-empty evidence (no_silent_disqual invariant)
- An LLM "Eligible with no evidence" gets downgraded to NeedsManualReview
- An LLM "NotEligible with no evidence" raises EvidenceMissingError
"""

from __future__ import annotations

import pytest

from api.domain import eval_engine
from api.domain.no_silent_disqual import EvidenceMissingError
from api.domain.schemas import (
    BBox,
    Bidder,
    BidderDoc,
    Criterion,
    Evidence,
    EvidenceLLM,
    Tender,
    VerdictLLM,
)


def _make_tender() -> Tender:
    return Tender(
        id="T1",
        title="CRPF Tents Tender",
        issuer="CRPF",
        criteria=[
            Criterion(
                id="C1",
                name="Min annual turnover",
                type="financial",
                description="Avg annual turnover INR 50 lakhs",
                threshold_value=50.0,
                threshold_unit="INR_lakhs",
                threshold_operator=">=",
                source_clause="minimum average annual turnover of INR 50 lakhs",
                required_documents=["CA Avg Turnover Cert"],
            ),
            Criterion(
                id="C2",
                name="ISO 9001",
                type="technical",
                description="Bidder must possess ISO 9001 certification",
                threshold_operator="exists",
                source_clause="must possess ISO 9001 certification",
                required_documents=["ISO 9001 Certificate"],
            ),
        ],
    )


def _make_bidders() -> list[Bidder]:
    return [
        Bidder(
            id="B1",
            tender_id="T1",
            name="Acme Pvt Ltd",
            documents=[
                BidderDoc(id="d1", bidder_id="B1", filename="ca_turnover.pdf",
                          doc_type="ca_turnover_cert", blob_id="blob1"),
                BidderDoc(id="d2", bidder_id="B1", filename="iso.pdf",
                          doc_type="iso_cert", blob_id="blob2"),
            ],
        ),
        Bidder(
            id="B2",
            tender_id="T1",
            name="Beta Industries",
            documents=[
                BidderDoc(id="d3", bidder_id="B2", filename="ca_turnover.pdf",
                          doc_type="ca_turnover_cert", blob_id="blob3"),
            ],
        ),
    ]


def _ev(doc_id: str, quote: str, page: int = 0, score: float = 0.85) -> Evidence:
    return Evidence(
        bidder_doc_id=doc_id,
        page=page,
        bbox=BBox(page=page, x0=10, y0=10, x1=100, y1=30),
        quote=quote,
        score=score,
    )


def test_evaluate_happy_path():
    tender = _make_tender()
    bidders = _make_bidders()

    def fake_retrieve(tender_id, criterion, bidder_id, k):
        return [_ev(f"doc-{bidder_id}-{criterion.id}", f"evidence for {criterion.id}")]

    def fake_eval(criterion, bidder, evidence):
        # Emulate an LLM that returns Eligible with the top evidence quote.
        ev = evidence[0]
        return VerdictLLM(
            criterion_id=criterion.id,
            bidder_id=bidder.id,
            verdict="Eligible",
            confidence=0.9,
            explanation=f"Meets criterion. Evidence: {ev.quote}",
            evidence=[EvidenceLLM(bidder_doc_id=ev.bidder_doc_id, page=ev.page, quote=ev.quote)],
        )

    matrix = eval_engine.evaluate(
        tender, bidders, retrieve=fake_retrieve, evaluate_pair=fake_eval
    )
    assert matrix.tender_id == "T1"
    assert len(matrix.verdicts) == len(tender.criteria) * len(bidders)
    for v in matrix.verdicts:
        assert v.verdict == "Eligible"
        assert len(v.evidence) >= 1


def test_evaluate_eligible_without_evidence_is_downgraded():
    tender = _make_tender()
    bidders = _make_bidders()[:1]

    def fake_retrieve(*_args, **_kwargs):
        return []

    def fake_eval(criterion, bidder, evidence):
        return VerdictLLM(
            criterion_id=criterion.id,
            bidder_id=bidder.id,
            verdict="Eligible",
            confidence=0.95,
            explanation="LLM hallucinated eligibility without evidence.",
            evidence=[],
        )

    matrix = eval_engine.evaluate(
        tender, bidders, retrieve=fake_retrieve, evaluate_pair=fake_eval
    )
    for v in matrix.verdicts:
        assert v.verdict == "NeedsManualReview"
        assert v.explanation.startswith("[no evidence] ")


def test_evaluate_noteligible_without_evidence_raises():
    tender = _make_tender()
    bidders = _make_bidders()[:1]

    def fake_retrieve(*_args, **_kwargs):
        return []

    def fake_eval(criterion, bidder, evidence):
        return VerdictLLM(
            criterion_id=criterion.id,
            bidder_id=bidder.id,
            verdict="NotEligible",
            confidence=0.99,
            explanation="LLM tried to silently disqualify with no evidence.",
            evidence=[],
        )

    with pytest.raises(EvidenceMissingError):
        eval_engine.evaluate(
            tender, bidders, retrieve=fake_retrieve, evaluate_pair=fake_eval
        )


def test_evaluate_noteligible_with_evidence_passes_through():
    tender = _make_tender()
    bidders = _make_bidders()[:1]

    def fake_retrieve(tender_id, criterion, bidder_id, k):
        return [_ev("d1", "audited turnover INR 5 lakhs only")]

    def fake_eval(criterion, bidder, evidence):
        ev = evidence[0]
        return VerdictLLM(
            criterion_id=criterion.id,
            bidder_id=bidder.id,
            verdict="NotEligible",
            confidence=0.92,
            explanation=f"Turnover INR 5 lakhs is below threshold. Evidence: {ev.quote}",
            evidence=[EvidenceLLM(bidder_doc_id=ev.bidder_doc_id, page=ev.page, quote=ev.quote)],
        )

    matrix = eval_engine.evaluate(
        tender, bidders, retrieve=fake_retrieve, evaluate_pair=fake_eval
    )
    for v in matrix.verdicts:
        assert v.verdict == "NotEligible"
        assert len(v.evidence) >= 1
        assert v.evidence[0].bbox.x1 > 0  # bbox was post-populated from retrieved chunk
