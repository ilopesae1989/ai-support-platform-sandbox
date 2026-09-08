from __future__ import annotations

from importlib import import_module

import pytest

from src.agents.contracts import (
    AlertTriageResult,
    ClassificationResult,
    EscalationInfo,
    KnowledgeDocument,
    KnowledgeResult,
    ProcedureReference,
)

from src.communication.context import (
    build_safe_communication_context,
)

from src.communication.contracts import (
    CommunicationRequest,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationAction,
    OperationKind,
    ProcedureReference as RuntimeProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)


ALERT_ID = "ALERT-SYNTHETIC-001"


def _projection():
    try:
        return import_module(
            "src.communication.projection"
        )
    except ModuleNotFoundError as exc:
        if exc.name != "src.communication.projection":
            raise

        pytest.fail(
            "Governed communication projection "
            "is not implemented.",
            pytrace=False,
        )


def _context() -> TriagedAlertContext:
    return TriagedAlertContext(
        alert=NormalizedAlert(
            alert_id=ALERT_ID,
            source="azure_monitor",
            source_event_id="synthetic-event-001",
            name="Synthetic infrastructure incident",
            description=(
                "Synthetic incident used only for "
                "communication projection tests."
            ),
            source_severity="Sev2",
            affected_resource=(
                "/subscriptions/00000000-0000-0000-0000-000000000000/"
                "resourceGroups/rg-synthetic/"
                "providers/Microsoft.Compute/"
                "virtualMachines/vm-synthetic"
            ),
            resource_type=(
                "Microsoft.Compute/virtualMachines"
            ),
            service="compute",
            environment="sandbox",
        ),
        classification=ClassificationResult(
            alert_id=ALERT_ID,
            alert_classification=(
                "infrastructure_availability"
            ),
            technical_domain="azure",
            affected_resource="vm-synthetic",
            affected_service="compute",
            classification_summary=(
                "Synthetic Azure availability incident."
            ),
            requires_clarification=False,
            missing_information=[],
            confidence=0.99,
        ),
        knowledge=KnowledgeResult(
            alert_id=ALERT_ID,
            knowledge_found=True,
            documents=[
                KnowledgeDocument(
                    id="PROC-SYNTHETIC-001",
                    name="Synthetic recovery procedure",
                    version="1.0",
                    relevance_summary=(
                        "Synthetic recovery procedure "
                        "applicable to this incident."
                    ),
                )
            ],
            knowledge_summary=(
                "A matching synthetic procedure exists."
            ),
            limitations=[],
            confidence=0.99,
        ),
        triage=AlertTriageResult(
            alert_classification=(
                "infrastructure_availability"
            ),
            technical_domain="azure",
            affected_resource="vm-synthetic",
            affected_service="compute",
            technical_summary=(
                "Synthetic service availability incident."
            ),
            source_severity="Sev2",
            corporate_criticality="high",
            criticality_source="procedure",
            procedure_found=True,
            procedure_match="exact",
            execution_eligible=True,
            knowledge_coverage="complete",
            recommended_next_step="procedure_execution",
            procedure=ProcedureReference(
                id="PROC-SYNTHETIC-001",
                name="Synthetic recovery procedure",
                version="1.0",
                resolution_criteria=(
                    "Synthetic service restored."
                ),
            ),
            escalation=EscalationInfo(
                required=False,
            ),
            possible_false_positive="unlikely",
            missing_context=[],
            source_documents=[
                "PROC-SYNTHETIC-001"
            ],
            confidence=0.99,
            ai_opinion=None,
        ),
    )


def _runtime_state(
    *,
    workflow_status: WorkflowStatus,
    step_status: StepStatus,
    approval_status: ApprovalStatus = (
        ApprovalStatus.APPROVED
    ),
    verification_success: bool | None = None,
    escalation_required: bool = False,
    escalation_team: str | None = None,
) -> ProcedureRuntimeState:
    verification_result = None

    if verification_success is not None:
        verification_result = StepEvidence(
            success=verification_success,
            result={
                "power_state": "running",
            },
        )

    return ProcedureRuntimeState(
        workflow_id="workflow-synthetic-001",
        alert_id=ALERT_ID,
        correlation_id="correlation-synthetic-001",
        approval_id="approval-sensitive-001",
        conversation_id="conversation-sensitive-001",
        procedure=RuntimeProcedureReference(
            id="PROC-SYNTHETIC-001",
            name="Synthetic recovery procedure",
            version="1.0",
        ),
        total_steps=1,
        current_step=1,
        step=ProcedureStep(
            id="1",
            description="Start synthetic VM.",
            step_type="technical_operation",
            operation_domain="azure",
            operation_kind=OperationKind.WRITE,
            operation_action=OperationAction.VM_START,
            capability_id="azure.vm.start",
            hitl_required=True,
            target_resource=(
                "/subscriptions/SENSITIVE/"
                "resourceGroups/SENSITIVE/"
                "providers/Microsoft.Compute/"
                "virtualMachines/SENSITIVE"
            ),
            required_parameters=[
                "subscription_id",
                "resource_group",
                "vm_name",
            ],
            preconditions=[],
            expected_result="VM running.",
            verification="Read VM power state.",
        ),
        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",
                value="SENSITIVE-SUBSCRIPTION",
                source="operational_context",
            ),
            ResolvedParameter(
                name="resource_group",
                value="SENSITIVE-RG",
                source="operational_context",
            ),
            ResolvedParameter(
                name="vm_name",
                value="SENSITIVE-VM",
                source="operational_context",
            ),
        ],
        workflow_status=workflow_status,
        step_status=step_status,
        approval_status=approval_status,
        operation_result=StepEvidence(
            success=True,
            result={
                "backend": "SENSITIVE-MCP-EVIDENCE",
            },
        ),
        verification_result=verification_result,
        retry_count=0,
        recheck_count=0,
        escalation_required=escalation_required,
        escalation_team=escalation_team,
        escalation_level=(
            "L2"
            if escalation_required
            else None
        ),
        escalation_criteria=(
            "Synthetic escalation criteria."
            if escalation_required
            else None
        ),
    )


def test_incident_projection_builds_safe_request():
    projection = _projection()

    request = (
        projection
        .build_incident_detected_communication_request(
            _context()
        )
    )

    assert isinstance(
        request,
        CommunicationRequest,
    )

    assert request.event_type == "incident_detected"
    assert request.alert_id == ALERT_ID
    assert request.technical_domain == "azure"
    assert request.corporate_criticality == "high"
    assert request.affected_resource == "vm-synthetic"
    assert request.technical_summary == (
        "Synthetic service availability incident."
    )
    assert request.procedure_id == "PROC-SYNTHETIC-001"
    assert request.procedure_name == (
        "Synthetic recovery procedure"
    )
    assert request.escalation_required is False
    assert request.escalation_team is None


@pytest.mark.parametrize(
    (
        "state",
        "expected_event",
        "expected_status",
    ),
    [
        pytest.param(
            _runtime_state(
                workflow_status=(
                    WorkflowStatus.WAITING_VALIDATION
                ),
                step_status=(
                    StepStatus.WAITING_VALIDATION
                ),
            ),
            "waiting_validation",
            (
                "The governed runtime is waiting "
                "for validation."
            ),
            id="waiting-validation",
        ),
        pytest.param(
            _runtime_state(
                workflow_status=WorkflowStatus.RESOLVED,
                step_status=StepStatus.SUCCEEDED,
                verification_success=True,
            ),
            "resolved",
            (
                "The governed runtime reports "
                "the incident as resolved."
            ),
            id="resolved",
        ),
        pytest.param(
            _runtime_state(
                workflow_status=(
                    WorkflowStatus.ESCALATION_REQUIRED
                ),
                step_status=StepStatus.FAILED,
                escalation_required=True,
                escalation_team="Cloud Operations",
            ),
            "escalation_required",
            (
                "The governed runtime requires "
                "human escalation."
            ),
            id="escalation",
        ),
        pytest.param(
            _runtime_state(
                workflow_status=WorkflowStatus.BLOCKED,
                step_status=StepStatus.BLOCKED,
            ),
            "blocked",
            (
                "The governed runtime blocked "
                "automatic resolution."
            ),
            id="blocked",
        ),
        pytest.param(
            _runtime_state(
                workflow_status=WorkflowStatus.FAILED,
                step_status=StepStatus.FAILED,
            ),
            "failed",
            (
                "The governed runtime reports "
                "automatic resolution failed."
            ),
            id="failed",
        ),
        pytest.param(
            _runtime_state(
                workflow_status=WorkflowStatus.BLOCKED,
                step_status=StepStatus.REJECTED,
                approval_status=(
                    ApprovalStatus.REJECTED
                ),
            ),
            "operation_rejected",
            (
                "The operator rejected the "
                "requested operation."
            ),
            id="operation-rejected",
        ),
    ],
)
def test_runtime_projection_maps_only_governed_states(
    state,
    expected_event,
    expected_status,
):
    projection = _projection()

    request = (
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )
    )

    assert isinstance(
        request,
        CommunicationRequest,
    )

    assert request.event_type == expected_event
    assert request.status_summary == expected_status


def test_runtime_projection_copies_escalation_truth():
    projection = _projection()

    state = _runtime_state(
        workflow_status=(
            WorkflowStatus.ESCALATION_REQUIRED
        ),
        step_status=StepStatus.FAILED,
        escalation_required=True,
        escalation_team="Cloud Operations",
    )

    request = (
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )
    )

    assert request.escalation_required is True
    assert request.escalation_team == "Cloud Operations"


def test_runtime_projection_rejects_non_communicable_state():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RUNNING,
        step_status=StepStatus.RUNNING,
    )

    with pytest.raises(
        projection.CommunicationProjectionError
    ):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )


def test_runtime_projection_rejects_alert_mismatch():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RESOLVED,
        step_status=StepStatus.SUCCEEDED,
        verification_success=True,
    )

    state.alert_id = "OTHER-ALERT"

    with pytest.raises(
        projection.CommunicationProjectionError
    ):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )


def test_runtime_projection_rejects_procedure_mismatch():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RESOLVED,
        step_status=StepStatus.SUCCEEDED,
        verification_success=True,
    )

    state.procedure = RuntimeProcedureReference(
        id="OTHER-PROCEDURE",
        name="Other procedure",
        version="1.0",
    )

    with pytest.raises(
        projection.CommunicationProjectionError
    ):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )


def test_resolved_projection_requires_positive_verification():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RESOLVED,
        step_status=StepStatus.SUCCEEDED,
        verification_success=False,
    )

    with pytest.raises(
        projection.CommunicationProjectionError
    ):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )


def test_projection_uses_triage_display_resource_not_runtime_target():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RESOLVED,
        step_status=StepStatus.SUCCEEDED,
        verification_success=True,
    )

    request = (
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )
    )

    assert request.affected_resource == "vm-synthetic"

    assert (
        state.step.target_resource
        not in request.model_dump().values()
    )


def test_projection_does_not_leak_operational_authority():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RESOLVED,
        step_status=StepStatus.SUCCEEDED,
        verification_success=True,
    )

    request = (
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )
    )

    serialized = repr(
        request.model_dump()
    )

    forbidden_values = {
        "approval-sensitive-001",
        "conversation-sensitive-001",
        "azure.vm.start",
        "SENSITIVE-SUBSCRIPTION",
        "SENSITIVE-RG",
        "SENSITIVE-VM",
        "SENSITIVE-MCP-EVIDENCE",
        "/subscriptions/SENSITIVE/",
    }

    for value in forbidden_values:
        assert value not in serialized


def test_incident_projection_requires_exact_context_type():
    projection = _projection()

    with pytest.raises(TypeError):
        projection.build_incident_detected_communication_request(
            object()
        )


def test_runtime_projection_requires_exact_context_type():
    projection = _projection()

    state = _runtime_state(
        workflow_status=WorkflowStatus.RESOLVED,
        step_status=StepStatus.SUCCEEDED,
        verification_success=True,
    )

    with pytest.raises(TypeError):
        projection.build_runtime_communication_request(
            context=object(),
            state=state,
        )


def test_runtime_projection_requires_exact_state_type():
    projection = _projection()

    with pytest.raises(TypeError):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=object(),
        )

def test_rejected_projection_requires_blocked_workflow_status():
    projection = _projection()

    state = _runtime_state(
        workflow_status=(
            WorkflowStatus.WAITING_HUMAN
        ),
        step_status=StepStatus.REJECTED,
        approval_status=(
            ApprovalStatus.REJECTED
        ),
    )

    with pytest.raises(
        projection.CommunicationProjectionError
    ):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )


def test_escalation_projection_requires_failed_step_status():
    projection = _projection()

    state = _runtime_state(
        workflow_status=(
            WorkflowStatus.ESCALATION_REQUIRED
        ),
        step_status=StepStatus.SUCCEEDED,
        escalation_required=True,
        escalation_team="Cloud Operations",
    )

    with pytest.raises(
        projection.CommunicationProjectionError
    ):
        projection.build_runtime_communication_request(
            context=build_safe_communication_context(_context()),
            state=state,
        )
