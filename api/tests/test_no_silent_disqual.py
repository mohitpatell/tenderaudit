"""HARD invariant: no NotEligible verdict without supporting evidence.

These tests pin the runtime guard. They MUST pass.
"""

from __future__ import annotations

import pytest

from api.domain.no_silent_disqual import EvidenceMissingError, enforce
from api.domain.schemas import BBox, Evidence, Verdict


def _ev(doc_id: str = "d1", quote: str = "audited turnover INR 50 lakhs") -> Evidence:
    return Evidence(
        bidder_doc_id=doc_id,
        page=0,
        bbox=BBox(page=0, x0=0, y0=0, x1=10, y1=10),
        quote=quote,
        score=0.9,
    )


def test_not_eligible_without_evidence_raises():
    """A NotEligible verdict with no evidence MUST raise EvidenceMissingError."""
    v = Verdict(
        criterion_id="C1",
        bidder_id="B1",
        verdict="NotEligible",
        confidence=0.9,
        explanation="Failed solvency check.",
        evidence=[],
    )
    with pytest.raises(EvidenceMissingError):
        enforce([v])


def test_eligible_without_evidence_is_downgraded():
    """An Eligible verdict with no evidence is silently dangerous; downgrade it."""
    v = Verdict(
        criterion_id="C2",
        bidder_id="B1",
        verdict="Eligible",
        confidence=0.95,
        explanation="Bidder meets turnover requirement.",
        evidence=[],
    )
    out = enforce([v])
    assert len(out) == 1
    assert out[0].verdict == "NeedsManualReview"
    assert out[0].explanation.startswith("[no evidence] ")
    # Original explanation preserved after the prefix:
    assert "Bidder meets turnover requirement." in out[0].explanation


def test_valid_verdicts_pass_through():
    """Verdicts that obey the invariant are returned unchanged (in order)."""
    v1 = Verdict(
        criterion_id="C1",
        bidder_id="B1",
        verdict="Eligible",
        confidence=0.92,
        explanation="Meets turnover threshold.",
        evidence=[_ev()],
    )
    v2 = Verdict(
        criterion_id="C1",
        bidder_id="B2",
        verdict="NotEligible",
        confidence=0.9,
        explanation="Turnover well below threshold per audited statement.",
        evidence=[_ev(doc_id="d2", quote="turnover INR 5 lakhs")],
    )
    v3 = Verdict(
        criterion_id="C2",
        bidder_id="B1",
        verdict="NeedsManualReview",
        confidence=0.6,
        explanation="Cert expired; needs human review.",
        evidence=[_ev(doc_id="d3")],
    )
    out = enforce([v1, v2, v3])
    assert [v.verdict for v in out] == ["Eligible", "NotEligible", "NeedsManualReview"]
    assert out[0] == v1
    assert out[1] == v2
    assert out[2] == v3


def test_double_prefix_is_idempotent():
    """Re-running enforce on a downgraded Verdict does not stack '[no evidence]'."""
    v = Verdict(
        criterion_id="C2",
        bidder_id="B1",
        verdict="Eligible",
        confidence=0.95,
        explanation="Meets req.",
        evidence=[],
    )
    once = enforce([v])
    # Re-feed the once-downgraded verdict but flip back to Eligible to retest path.
    redo = once[0].model_copy(update={"verdict": "Eligible"})
    twice = enforce([redo])
    assert twice[0].explanation.count("[no evidence]") == 1
