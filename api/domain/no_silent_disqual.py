"""Runtime guard: no silent disqualification.

Hard invariant of the TenderAudit system:

    A "NotEligible" verdict MUST be backed by at least one Evidence item.

The LLM prompt instructs the model to obey this rule, but the prompt is not
trustworthy on its own. :func:`enforce` is the runtime double-check that any
``NotEligible`` lacking evidence raises :class:`EvidenceMissingError`. An
``Eligible`` lacking evidence is downgraded to ``NeedsManualReview`` (a soft
guard — being permissive without evidence is also wrong, but less catastrophic
than a silent disqualification).

Every code path that returns a Verdict to the caller MUST run through this
function. See ``api/domain/eval_engine.py``.
"""

from __future__ import annotations

from typing import Iterable

from .schemas import Verdict


class EvidenceMissingError(Exception):
    """Raised when a ``NotEligible`` verdict has no supporting evidence."""

    def __init__(self, verdict: Verdict) -> None:
        self.verdict = verdict
        super().__init__(
            "NotEligible verdict has no supporting evidence "
            f"(criterion_id={verdict.criterion_id!r}, bidder_id={verdict.bidder_id!r}). "
            "This violates the no-silent-disqualification invariant."
        )


_NO_EVIDENCE_PREFIX = "[no evidence] "


def enforce(verdicts: Iterable[Verdict]) -> list[Verdict]:
    """Apply the no-silent-disqualification guard to a list of verdicts.

    Behavior:

    - If ``verdict.verdict == "NotEligible"`` and ``verdict.evidence == []``:
      raise :class:`EvidenceMissingError` (HARD failure — caller is buggy).
    - If ``verdict.verdict == "Eligible"`` and ``verdict.evidence == []``:
      downgrade to ``NeedsManualReview`` and prepend the explanation with
      ``"[no evidence] "``. Returns a NEW Verdict (immutability).
    - Otherwise pass through unchanged.

    The returned list preserves input order.
    """
    out: list[Verdict] = []
    for v in verdicts:
        if v.verdict == "NotEligible" and not v.evidence:
            raise EvidenceMissingError(v)
        if v.verdict == "Eligible" and not v.evidence:
            new_explanation = v.explanation
            if not new_explanation.startswith(_NO_EVIDENCE_PREFIX):
                new_explanation = _NO_EVIDENCE_PREFIX + new_explanation
            out.append(
                v.model_copy(
                    update={
                        "verdict": "NeedsManualReview",
                        "explanation": new_explanation,
                    }
                )
            )
            continue
        out.append(v)
    return out
