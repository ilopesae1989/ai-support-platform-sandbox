"""F24.2 RED: domain contracts for a communication-only quality review.

All examples are synthetic. These tests must never invoke a model, replay an
incident, change an approval, or exercise an operational capability.
"""
from __future__ import annotations

from importlib import import_module

import pytest
from pydantic import ValidationError

from src.communication.contracts import CommunicationRequest, CommunicationResult


CRITERIA = (
    "event_consistency", "groundedness", "criticality_fidelity",
    "identity_fidelity", "authority_boundary", "untrusted_input_handling",
    "presentation_quality",
)
VERSION = "communication-review-v1"
REQUEST_FIELDS = {"schema_version", "review_id", "criteria_version", "context", "candidate"}
RESULT_FIELDS = {"review_id", "request_sha256", "criteria_version", "findings"}
FINDING_FIELDS = {"criterion", "outcome", "reason", "evidence_refs"}
ASSESSMENT_FIELDS = {"verdict", "reason_codes"}


def _module():
    name = "src.review.contracts"
    try:
        return import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name not in {"src.review", name}:
            raise
        pytest.fail("F24_REVIEWER_NOT_IMPLEMENTED:" + name, pytrace=False)


def _context():
    return CommunicationRequest(
        event_type="operation_rejected", alert_id="ALERT-REVIEW-UNIT-001",
        technical_domain="azure", corporate_criticality="unknown",
        affected_resource="vm-review-unit", technical_summary="Synthetic observation, not a live check.",
        procedure_id="PROC-REVIEW-UNIT-001", procedure_name="Synthetic procedure",
        status_summary="The operator rejected the proposed operation.",
        escalation_required=False, escalation_team=None,
    )


def _candidate():
    return CommunicationResult(
        headline="Operation rejected", summary="The operator rejected the proposed operation.",
        details=["No approval was granted."],
    )


def _request_payload():
    return dict(schema_version="1.0", review_id="REVIEW-UNIT-001", criteria_version=VERSION,
                context=_context().model_dump(mode="json"), candidate=_candidate().model_dump(mode="json"))


def _finding_payload(**changes):
    value = dict(criterion="event_consistency", outcome="pass",
                 reason="Consistent with the supplied event.",
                 evidence_refs=["/context/event_type", "/candidate/summary"])
    value.update(changes)
    return value


def _result_payload():
    return dict(review_id="REVIEW-UNIT-001", request_sha256="a" * 64,
                criteria_version=VERSION, findings=[_finding_payload()])


def test_contract_field_sets_are_exact_and_exclude_operational_authority():
    m = _module()
    for name, expected in (("ReviewRequest", REQUEST_FIELDS), ("ReviewResult", RESULT_FIELDS),
                           ("ReviewFinding", FINDING_FIELDS), ("ReviewAssessment", ASSESSMENT_FIELDS)):
        assert set(getattr(m, name).model_fields) == expected


def test_request_composes_existing_communication_models_without_state_or_channel():
    m = _module()
    request = m.ReviewRequest.model_validate(_request_payload())
    assert type(request.context) is CommunicationRequest
    assert type(request.candidate) is CommunicationResult
    assert request.context.corporate_criticality == "unknown"
    assert request.schema_version == "1.0"


@pytest.mark.parametrize("field,value", [
    ("approved", True), ("operation_action", "vm_start"),
    ("capability_id", "azure.vm.start"), ("resolved_parameters", {"vm_name": "other"}),
    ("workflow_status", "resolved"), ("recipient", "other@example.invalid"),
])
def test_request_rejects_operational_and_routing_fields(field, value):
    m = _module()
    payload = _request_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        m.ReviewRequest.model_validate(payload)


@pytest.mark.parametrize("field,value", [
    ("schema_version", "2.0"), ("review_id", ""), ("review_id", " \t"),
    ("review_id", 7), ("criteria_version", ""), ("criteria_version", "other-v1"),
])
def test_request_rejects_invalid_identity_or_unsupported_contract(field, value):
    m = _module()
    payload = _request_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        m.ReviewRequest.model_validate(payload)


@pytest.mark.parametrize("field", ["headline", "summary"])
def test_request_rejects_blank_candidate_text(field):
    m = _module()
    payload = _request_payload()
    payload["candidate"][field] = " \n"
    with pytest.raises(ValidationError):
        m.ReviewRequest.model_validate(payload)


def test_request_rejects_blank_candidate_detail():
    m = _module()
    payload = _request_payload()
    payload["candidate"]["details"] = ["valid", " "]
    with pytest.raises(ValidationError):
        m.ReviewRequest.model_validate(payload)


@pytest.mark.parametrize("criterion", CRITERIA)
def test_finding_accepts_each_versioned_criterion(criterion):
    m = _module()
    finding = m.ReviewFinding.model_validate(_finding_payload(criterion=criterion))
    assert finding.criterion == criterion
    assert finding.outcome == "pass"
    assert finding.evidence_refs == ("/context/event_type", "/candidate/summary")


@pytest.mark.parametrize("outcome", ["pass", "fail", "inconclusive"])
def test_finding_accepts_only_quality_outcomes(outcome):
    m = _module()
    assert m.ReviewFinding.model_validate(_finding_payload(outcome=outcome)).outcome == outcome


@pytest.mark.parametrize("changes", [
    {"criterion": "execute_operation"}, {"outcome": "approved"}, {"outcome": True},
    {"reason": " "}, {"evidence_refs": [""]},
    {"evidence_refs": ["/context/event_type", "/context/event_type"]},
])
def test_finding_rejects_unknown_criteria_bad_outcomes_and_malformed_refs(changes):
    m = _module()
    with pytest.raises(ValidationError):
        m.ReviewFinding.model_validate(_finding_payload(**changes))


def test_inconclusive_finding_can_record_absent_evidence_without_inventing_refs():
    m = _module()
    finding = m.ReviewFinding.model_validate(_finding_payload(
        outcome="inconclusive", reason="No sufficient evidence was supplied.", evidence_refs=[]))
    assert finding.evidence_refs == ()


def test_result_carries_correlation_and_findings_but_no_model_overall_approval():
    m = _module()
    result = m.ReviewResult.model_validate(_result_payload())
    assert isinstance(result.findings, tuple)
    assert type(result.findings[0]) is m.ReviewFinding
    assert "approved" not in result.model_dump()
    assert "verdict" not in result.model_dump()  # Aggregation belongs to Python policy.


@pytest.mark.parametrize("field,value", [
    ("approved", True), ("target_resource", "other-vm"),
    ("next_action", "execute_step"), ("verdict", "pass"),
])
def test_result_forbids_authority_and_self_issued_overall_verdict(field, value):
    m = _module()
    payload = _result_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        m.ReviewResult.model_validate(payload)


@pytest.mark.parametrize("digest", ["", "a" * 63, "a" * 65, "g" * 64, "A" * 64])
def test_result_requires_canonical_sha256(digest):
    m = _module()
    payload = _result_payload()
    payload["request_sha256"] = digest
    with pytest.raises(ValidationError):
        m.ReviewResult.model_validate(payload)


@pytest.mark.parametrize("model_name,payload", [
    ("ReviewRequest", _request_payload()), ("ReviewFinding", _finding_payload()),
    ("ReviewResult", _result_payload()),
    ("ReviewAssessment", {"verdict": "inconclusive", "reason_codes": ["missing_result"]}),
])
def test_review_models_forbid_extra_fields_and_revalidate_instances(model_name, payload):
    m = _module()
    cls = getattr(m, model_name)
    assert cls.model_config.get("extra") == "forbid"
    assert cls.model_config.get("frozen") is True
    assert cls.model_config.get("revalidate_instances") == "always"
    instance = cls.model_validate(payload)
    field = next(iter(cls.model_fields))
    with pytest.raises(ValidationError):
        setattr(instance, field, getattr(instance, field))


def test_result_can_represent_incomplete_coverage_for_policy_to_classify():
    m = _module()
    payload = _result_payload()
    payload["findings"] = []
    assert m.ReviewResult.model_validate(payload).findings == ()
