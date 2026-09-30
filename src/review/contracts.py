"""Data contracts for communication quality reviews, never operational authority."""
from __future__ import annotations

from typing import Annotated, Literal, Self, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from src.communication.contracts import CommunicationRequest, CommunicationResult


ReviewCriterion = Literal[
    "event_consistency",
    "groundedness",
    "criticality_fidelity",
    "identity_fidelity",
    "authority_boundary",
    "untrusted_input_handling",
    "presentation_quality",
]
ReviewQualityOutcome = Literal["pass", "fail", "inconclusive"]
ReviewReasonCode = Literal[
    "missing_result",
    "review_id_mismatch",
    "request_sha256_mismatch",
    "criteria_version_mismatch",
    "criteria_coverage_mismatch",
    "evidence_reference_invalid",
    "evidence_missing",
    "criterion_failed",
    "criterion_inconclusive",
]
REVIEW_CRITERIA_VERSION = "communication-review-v1"
REQUIRED_REVIEW_CRITERIA: tuple[ReviewCriterion, ...] = get_args(ReviewCriterion)


def _nonblank(value: str) -> str:
    # Validate without trimming: whitespace is part of the reviewed content.
    if not value.strip():
        raise ValueError("Review text must not be blank.")
    return value


NonBlankText = Annotated[StrictStr, AfterValidator(_nonblank)]
CanonicalSHA256 = Annotated[StrictStr, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]


class _ReviewContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )


class ReviewRequest(_ReviewContract):
    """One versioned review of copied facts and candidate presentation.

    The nested CommunicationResult retains its existing list contract. Frozen
    attributes do not make that list immutable; the policy revalidates and hashes
    the complete request each time it assesses a bound result.
    """

    schema_version: Literal["1.0"]
    review_id: NonBlankText
    criteria_version: Literal["communication-review-v1"]
    context: CommunicationRequest
    candidate: CommunicationResult

    @field_validator("context", mode="before")
    @classmethod
    def copy_validated_context(cls, value: object) -> CommunicationRequest:
        if type(value) not in (dict, CommunicationRequest):
            raise ValueError("context requires CommunicationRequest or its JSON object.")
        return CommunicationRequest.model_validate(value, strict=True).model_copy(deep=True)

    @field_validator("candidate", mode="before")
    @classmethod
    def copy_validated_candidate(cls, value: object) -> CommunicationResult:
        if type(value) not in (dict, CommunicationResult):
            raise ValueError("candidate requires CommunicationResult or its JSON object.")
        candidate = CommunicationResult.model_validate(value, strict=True)
        for text in (candidate.headline, candidate.summary, *candidate.details):
            _nonblank(text)
        return candidate.model_copy(deep=True)


class ReviewFinding(_ReviewContract):
    """A cognitive judgment; evidence references are checked by Python policy."""

    criterion: ReviewCriterion
    outcome: ReviewQualityOutcome
    reason: NonBlankText
    evidence_refs: tuple[NonBlankText, ...]

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def require_ordered_references(cls, value: object) -> object:
        if type(value) not in (list, tuple):
            raise ValueError("evidence_refs must be an ordered array.")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def require_unique_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate evidence references are not allowed.")
        return value


class ReviewResult(_ReviewContract):
    """Correlated findings, with no model-issued overall verdict or authorization.

    Incomplete or duplicate criterion coverage is representable so that the
    policy can classify it explicitly as inconclusive rather than repairing it.
    A different nonblank criteria version is likewise rejected by correlation.
    """

    review_id: NonBlankText
    request_sha256: CanonicalSHA256
    criteria_version: NonBlankText
    findings: tuple[ReviewFinding, ...]

    @field_validator("findings", mode="before")
    @classmethod
    def require_ordered_findings(cls, value: object) -> object:
        if type(value) not in (list, tuple):
            raise ValueError("findings must be an ordered array.")
        return value


class ReviewAssessment(_ReviewContract):
    """Deterministic acceptance of a quality report, not proof of semantic truth."""

    verdict: ReviewQualityOutcome
    reason_codes: tuple[ReviewReasonCode, ...]

    @field_validator("reason_codes", mode="before")
    @classmethod
    def require_ordered_reasons(cls, value: object) -> object:
        if type(value) not in (list, tuple):
            raise ValueError("reason_codes must be an ordered array.")
        return value

    @model_validator(mode="after")
    def require_consistent_reasons(self) -> Self:
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("Duplicate reason codes are not allowed.")
        if (self.verdict == "pass") != (not self.reason_codes):
            raise ValueError("Only a pass can have no reason codes.")
        return self
