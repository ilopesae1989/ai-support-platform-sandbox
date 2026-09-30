"""Pure Python acceptance policy for a single, bound communication review.

No model is invoked here. A pass accepts the form and correlation of supplied
judgments; it does not prove they are semantically correct or authorize an action.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json

from src.communication.contracts import CommunicationRequest, CommunicationResult
from .contracts import (
    REQUIRED_REVIEW_CRITERIA,
    REVIEW_CRITERIA_VERSION,
    ReviewAssessment,
    ReviewReasonCode,
    ReviewRequest,
    ReviewResult,
)


def build_review_request(
    *,
    review_id: str,
    context: CommunicationRequest,
    candidate: CommunicationResult,
) -> ReviewRequest:
    """Copy and revalidate exact, previously typed inputs; never modify them."""
    if type(context) is not CommunicationRequest:
        raise TypeError("context must be exactly CommunicationRequest.")
    if type(candidate) is not CommunicationResult:
        raise TypeError("candidate must be exactly CommunicationResult.")
    return ReviewRequest(
        schema_version="1.0",
        review_id=review_id,
        criteria_version=REVIEW_CRITERIA_VERSION,
        context=context,
        candidate=candidate,
    )


def _validated_request(request: ReviewRequest) -> ReviewRequest:
    if type(request) is not ReviewRequest:
        raise TypeError("request must be exactly ReviewRequest.")
    # model_construct/model_copy do not replace validation at a boundary.
    return ReviewRequest.model_validate(request)


def _request_digest(request: ReviewRequest) -> str:
    encoded = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def review_request_sha256(request: ReviewRequest) -> str:
    """Hash validated content without trimming or Unicode normalization.

    This is the domain's versioned JSON encoding, not a claim of RFC 8785
    canonicalization, authenticity, or authorization.
    """
    return _request_digest(_validated_request(request))


def _permitted_evidence_refs(request: ReviewRequest) -> frozenset[str]:
    """Build finite references from the actual, non-null scalar input leaves.

    No path traversal, attribute resolution, URL access or generic JSON pointer
    execution takes place. Container nodes and padded/negative indices cannot
    match this allowlist. A false boolean is still a valid supplied fact.
    """
    refs: set[str] = set()
    for field, value in request.context.model_dump(mode="json").items():
        if type(value) is bool or (type(value) is str and value.strip()):
            refs.add("/context/" + field)
    refs.update(("/candidate/headline", "/candidate/summary"))
    refs.update("/candidate/details/" + str(i) for i in range(len(request.candidate.details)))
    return frozenset(refs)


def _inconclusive(*reasons: ReviewReasonCode) -> ReviewAssessment:
    return ReviewAssessment(verdict="inconclusive", reason_codes=reasons)


def assess_review(
    *,
    request: ReviewRequest,
    result: ReviewResult | None,
) -> ReviewAssessment:
    """Validate, bind, check coverage/evidence, then aggregate quality findings.

    Invalid typed inputs raise instead of becoming a pass. Missing results,
    mismatches, incomplete coverage and unresolvable references are inconclusive.
    Only complete admissible reports are aggregated: fail takes precedence over
    inconclusive, which takes precedence over pass. No input is mutated.
    """
    reviewed = _validated_request(request)
    if result is None:
        return _inconclusive("missing_result")
    if type(result) is not ReviewResult:
        raise TypeError("result must be exactly ReviewResult or None.")
    checked = ReviewResult.model_validate(result)

    reasons: list[ReviewReasonCode] = []
    if checked.review_id != reviewed.review_id:
        reasons.append("review_id_mismatch")
    if checked.request_sha256 != _request_digest(reviewed):
        reasons.append("request_sha256_mismatch")
    if checked.criteria_version != reviewed.criteria_version:
        reasons.append("criteria_version_mismatch")
    if reasons:
        return _inconclusive(*reasons)

    if Counter(f.criterion for f in checked.findings) != Counter(REQUIRED_REVIEW_CRITERIA):
        return _inconclusive("criteria_coverage_mismatch")

    permitted = _permitted_evidence_refs(reviewed)
    if any(ref not in permitted for f in checked.findings for ref in f.evidence_refs):
        reasons.append("evidence_reference_invalid")
    if any(not f.evidence_refs and f.outcome != "inconclusive" for f in checked.findings):
        reasons.append("evidence_missing")
    if reasons:
        return _inconclusive(*reasons)

    outcomes = {finding.outcome for finding in checked.findings}
    if "fail" in outcomes:
        reasons.append("criterion_failed")
    if "inconclusive" in outcomes:
        reasons.append("criterion_inconclusive")
    if "fail" in outcomes:
        return ReviewAssessment(verdict="fail", reason_codes=tuple(reasons))
    if "inconclusive" in outcomes:
        return _inconclusive(*reasons)
    return ReviewAssessment(verdict="pass", reason_codes=())
