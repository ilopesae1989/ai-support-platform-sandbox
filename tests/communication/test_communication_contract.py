from __future__ import annotations

from importlib import import_module
import inspect

import pytest
from pydantic import ValidationError


EXPECTED_REQUEST_FIELDS = {
    "event_type",
    "alert_id",
    "technical_domain",
    "corporate_criticality",
    "affected_resource",
    "technical_summary",
    "procedure_id",
    "procedure_name",
    "status_summary",
    "escalation_required",
    "escalation_team",
}

EXPECTED_RESULT_FIELDS = {
    "headline",
    "summary",
    "details",
}


def _contracts():
    try:
        return import_module(
            "src.communication.contracts"
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {
            "src.communication",
            "src.communication.contracts",
        }:
            raise

        pytest.fail(
            "Communication contract is not implemented.",
            pytrace=False,
        )


def _valid_request_payload() -> dict:
    return {
        "event_type": "resolved",
        "alert_id": "ALERT-SYNTHETIC-001",
        "technical_domain": "azure",
        "corporate_criticality": "high",
        "affected_resource": "vm-synthetic",
        "technical_summary": (
            "Synthetic availability incident."
        ),
        "procedure_id": "PROC-SYNTHETIC-001",
        "procedure_name": (
            "Synthetic recovery procedure"
        ),
        "status_summary": (
            "The governed runtime reports the "
            "incident as resolved."
        ),
        "escalation_required": False,
        "escalation_team": None,
    }


def _valid_result_payload() -> dict:
    return {
        "headline": "Incident resolved",
        "summary": (
            "The incident has been resolved and "
            "post-operation validation succeeded."
        ),
        "details": [
            "Procedure validation completed.",
            "No further automatic action is required.",
        ],
    }


def test_request_accepts_safe_channel_agnostic_projection():
    contracts = _contracts()

    request = (
        contracts.CommunicationRequest.model_validate(
            _valid_request_payload()
        )
    )

    assert request.event_type == "resolved"
    assert request.alert_id == "ALERT-SYNTHETIC-001"
    assert request.escalation_required is False


def test_request_fields_are_exact_safe_projection():
    contracts = _contracts()

    assert (
        set(
            contracts
            .CommunicationRequest
            .model_fields
        )
        == EXPECTED_REQUEST_FIELDS
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("subscription_id", "subscription-01"),
        ("resource_group", "rg-synthetic"),
        ("operation_id", "operation-01"),
        ("operation_action", "vm_start"),
        ("capability_id", "azure.vm.start"),
        (
            "resolved_parameters",
            {"vm_name": "vm-synthetic"},
        ),
        ("approval_id", "approval-01"),
        ("approved", True),
        (
            "target_resource",
            "/subscriptions/example/resource",
        ),
        ("checkpoint_id", "checkpoint-01"),
        ("wait_recheck_id", "recheck-01"),
        ("service_session_id", "session-01"),
        ("technical_success", True),
        ("success", True),
        ("tenant_id", "tenant-01"),
        ("conversation_id", "conversation-01"),
        ("recipient", "operator@example.invalid"),
        ("team_id", "team-01"),
        ("channel_id", "channel-01"),
        ("service_url", "https://example.invalid"),
        ("channel", "teams"),
    ],
)
def test_request_forbids_operational_and_routing_authority(
    field_name,
    field_value,
):
    contracts = _contracts()

    payload = _valid_request_payload()
    payload[field_name] = field_value

    with pytest.raises(ValidationError):
        contracts.CommunicationRequest.model_validate(
            payload
        )


@pytest.mark.parametrize(
    "event_type",
    [
        "execute_step",
        "continue",
        "repeat",
        "approval_required",
    ],
)
def test_request_rejects_internal_or_authority_events(
    event_type,
):
    contracts = _contracts()

    payload = _valid_request_payload()
    payload["event_type"] = event_type

    with pytest.raises(ValidationError):
        contracts.CommunicationRequest.model_validate(
            payload
        )


@pytest.mark.parametrize(
    "event_type",
    [
        "incident_detected",
        "waiting_validation",
        "resolved",
        "escalation_required",
        "blocked",
        "failed",
        "operation_rejected",
    ],
)
def test_request_accepts_supported_information_events(
    event_type,
):
    contracts = _contracts()

    payload = _valid_request_payload()
    payload["event_type"] = event_type

    if event_type == "escalation_required":
        payload["escalation_required"] = True
        payload["escalation_team"] = "Cloud Operations"

    request = (
        contracts.CommunicationRequest.model_validate(
            payload
        )
    )

    assert request.event_type == event_type


def test_request_rejects_partial_procedure_identity():
    contracts = _contracts()

    payload = _valid_request_payload()
    payload["procedure_name"] = None

    with pytest.raises(ValidationError):
        contracts.CommunicationRequest.model_validate(
            payload
        )

    payload = _valid_request_payload()
    payload["procedure_id"] = None

    with pytest.raises(ValidationError):
        contracts.CommunicationRequest.model_validate(
            payload
        )


def test_request_allows_absent_procedure_identity():
    contracts = _contracts()

    payload = _valid_request_payload()
    payload["procedure_id"] = None
    payload["procedure_name"] = None

    request = (
        contracts.CommunicationRequest.model_validate(
            payload
        )
    )

    assert request.procedure_id is None
    assert request.procedure_name is None


def test_request_rejects_escalation_team_without_escalation():
    contracts = _contracts()

    payload = _valid_request_payload()
    payload["escalation_required"] = False
    payload["escalation_team"] = "Cloud Operations"

    with pytest.raises(ValidationError):
        contracts.CommunicationRequest.model_validate(
            payload
        )


def test_escalation_event_requires_escalation_truth():
    contracts = _contracts()

    payload = _valid_request_payload()
    payload["event_type"] = "escalation_required"
    payload["escalation_required"] = False
    payload["escalation_team"] = None

    with pytest.raises(ValidationError):
        contracts.CommunicationRequest.model_validate(
            payload
        )


def test_result_accepts_presentation_only_content():
    contracts = _contracts()

    result = (
        contracts.CommunicationResult.model_validate(
            _valid_result_payload()
        )
    )

    assert result.headline == "Incident resolved"
    assert len(result.details) == 2


def test_result_fields_are_presentation_only():
    contracts = _contracts()

    assert (
        set(
            contracts
            .CommunicationResult
            .model_fields
        )
        == EXPECTED_RESULT_FIELDS
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("event_type", "resolved"),
        ("corporate_criticality", "high"),
        ("escalation_required", False),
        ("escalation_team", None),
        ("recommended_human_action", "Restart VM"),
        ("operation_id", "operation-01"),
        ("operation_action", "vm_start"),
        ("capability_id", "azure.vm.start"),
        ("approval_id", "approval-01"),
        ("approved", True),
        ("target_resource", "vm-synthetic"),
        (
            "resolved_parameters",
            {"vm_name": "vm-synthetic"},
        ),
        ("tenant_id", "tenant-01"),
        ("conversation_id", "conversation-01"),
        ("recipient", "operator@example.invalid"),
        ("channel", "teams"),
    ],
)
def test_result_forbids_truth_authority_and_routing_fields(
    field_name,
    field_value,
):
    contracts = _contracts()

    payload = _valid_result_payload()
    payload[field_name] = field_value

    with pytest.raises(ValidationError):
        contracts.CommunicationResult.model_validate(
            payload
        )


def test_request_is_frozen():
    contracts = _contracts()

    request = (
        contracts.CommunicationRequest.model_validate(
            _valid_request_payload()
        )
    )

    with pytest.raises(ValidationError):
        request.alert_id = "ALTERED"


def test_result_is_frozen():
    contracts = _contracts()

    result = (
        contracts.CommunicationResult.model_validate(
            _valid_result_payload()
        )
    )

    with pytest.raises(ValidationError):
        result.headline = "ALTERED"


def test_contract_is_channel_and_framework_agnostic():
    contracts = _contracts()

    source = inspect.getsource(
        contracts
    )

    assert "src.channels.teams" not in source
    assert "microsoft_teams" not in source
    assert "agent_framework" not in source
    assert "FoundryAgent" not in source