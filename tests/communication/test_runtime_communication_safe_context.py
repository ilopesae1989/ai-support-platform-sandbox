from __future__ import annotations

import inspect

import pytest

from src.communication.context import (
    SafeCommunicationContext,
)

from src.communication.projection import (
    CommunicationProjectionError,
    build_runtime_communication_request,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)


def _safe_context(
    *,
    alert_id: str = "ALERT-SYNTHETIC-001",
    procedure_id: str = "PROC-SYNTHETIC-001",
    procedure_name: str = "Synthetic recovery procedure",
) -> SafeCommunicationContext:
    return SafeCommunicationContext(
        alert_id=alert_id,
        technical_domain="azure",
        corporate_criticality="high",
        affected_resource="vm-display-safe",
        technical_summary=(
            "Synthetic service availability incident."
        ),
        procedure_id=procedure_id,
        procedure_name=procedure_name,
    )


def _runtime_state(
    *,
    alert_id: str = "ALERT-SYNTHETIC-001",
    procedure_id: str = "PROC-SYNTHETIC-001",
    procedure_name: str = "Synthetic recovery procedure",
    workflow_status: WorkflowStatus = WorkflowStatus.RESOLVED,
    step_status: StepStatus = StepStatus.SUCCEEDED,
    verification_success: bool | None = True,
) -> ProcedureRuntimeState:
    verification = None

    if verification_success is not None:
        verification = StepEvidence(
            success=verification_success,
            result={
                "private_runtime_result":
                    "must-not-be-projected"
            },
        )

    return ProcedureRuntimeState(
        workflow_id="workflow-synthetic-001",
        alert_id=alert_id,
        correlation_id="correlation-private-001",
        approval_id="approval-private-001",
        conversation_id="conversation-private-001",
        procedure=ProcedureReference(
            id=procedure_id,
            name=procedure_name,
            version="1",
        ),
        total_steps=1,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description="Synthetic governed step.",
            step_type="validation",
            operation_domain="azure",
            operation_kind=OperationKind.READ,
            target_resource=(
                "/subscriptions/private/"
                "resourceGroups/private/"
                "providers/Microsoft.Compute/"
                "virtualMachines/private"
            ),
            required_parameters=[],
            preconditions=[],
            expected_result="Synthetic expected result.",
            verification="Synthetic verification.",
        ),
        workflow_status=workflow_status,
        step_status=step_status,
        approval_status=ApprovalStatus.APPROVED,
        verification_result=verification,
    )


def test_runtime_projection_accepts_safe_context_for_resolved():
    context = _safe_context()
    state = _runtime_state()

    request = build_runtime_communication_request(
        context=context,
        state=state,
    )

    assert request.event_type == "resolved"

    assert request.alert_id == context.alert_id
    assert (
        request.technical_domain
        == context.technical_domain
    )
    assert (
        request.corporate_criticality
        == context.corporate_criticality
    )
    assert (
        request.affected_resource
        == context.affected_resource
    )
    assert (
        request.technical_summary
        == context.technical_summary
    )
    assert (
        request.procedure_id
        == context.procedure_id
    )
    assert (
        request.procedure_name
        == context.procedure_name
    )

    assert request.escalation_required is False
    assert request.escalation_team is None

    payload = request.model_dump(
        mode="json"
    )

    forbidden = {
        "workflow_id",
        "correlation_id",
        "approval_id",
        "conversation_id",
        "subscription_id",
        "resource_group",
        "vm_name",
        "tenant_id",
        "capability_id",
        "operation_action",
        "target_resource",
        "resolved_parameters",
        "operation_result",
        "verification_result",
    }

    assert forbidden.isdisjoint(
        payload
    )


def test_runtime_projection_accepts_safe_context_for_waiting_validation():
    context = _safe_context()

    state = _runtime_state(
        workflow_status=(
            WorkflowStatus.WAITING_VALIDATION
        ),
        step_status=(
            StepStatus.WAITING_VALIDATION
        ),
        verification_success=None,
    )

    request = build_runtime_communication_request(
        context=context,
        state=state,
    )

    assert (
        request.event_type
        == "waiting_validation"
    )

    assert request.alert_id == context.alert_id


def test_runtime_projection_rejects_safe_context_alert_mismatch():
    context = _safe_context()

    state = _runtime_state(
        alert_id="OTHER-ALERT"
    )

    with pytest.raises(
        CommunicationProjectionError
    ):
        build_runtime_communication_request(
            context=context,
            state=state,
        )


def test_runtime_projection_rejects_safe_context_procedure_mismatch():
    context = _safe_context()

    state = _runtime_state(
        procedure_id="OTHER-PROCEDURE",
        procedure_name="Other procedure",
    )

    with pytest.raises(
        CommunicationProjectionError
    ):
        build_runtime_communication_request(
            context=context,
            state=state,
        )


def test_runtime_projection_source_contract_uses_safe_context():
    source = inspect.getsource(
        build_runtime_communication_request
    )

    assert (
        "SafeCommunicationContext"
        in source
    )

    assert (
        "TriagedAlertContext"
        not in source
    )