from __future__ import annotations

from types import (
    SimpleNamespace,
)

import pytest

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.channels.teams.incident_terminal_presenter import (
    IncidentTerminalPresentationError,
    notify_teams_incident_terminal_result,
    render_incident_terminal_result,
)

from src.channels.teams.operator_identity import (
    TeamsOperatorIdentity,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
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


def _state(
    *,
    workflow_status=WorkflowStatus.RESOLVED,
    step_status=StepStatus.SUCCEEDED,
    approval_status=ApprovalStatus.APPROVED,
    verification_success=True,
    conversation_id="conversation-terminal-test",
):
    verification = None

    if verification_success is not None:
        verification = StepEvidence(
            success=verification_success,
            result={
                "observed": "local-test",
            },
        )

    return ProcedureRuntimeState(
        workflow_id="wf-terminal-test",
        alert_id="alert-terminal-test",
        approval_id="apr-terminal-test",
        conversation_id=conversation_id,
        procedure=ProcedureReference(
            id="PROC-TERMINAL-001",
            name="Procedimiento terminal test",
            version="1.0",
        ),
        total_steps=1,
        current_step=1,
        step=ProcedureStep(
            id="step-1",
            description="Paso local",
            step_type="azure_operation",
            operation_domain="azure",
            operation_kind=OperationKind.WRITE,
        ),
        workflow_status=workflow_status,
        step_status=step_status,
        approval_status=approval_status,
        verification_result=verification,
    )


def _invocation():
    return AuthorizedTeamsApprovalInvocation(
        policy_id="teams-hitl-sandbox-v1",
        operator=TeamsOperatorIdentity(
            tenant_id="tenant-terminal-test",
            aad_object_id="aad-terminal-test",
            teams_user_id="teams-terminal-test",
            conversation_id=(
                "conversation-terminal-test"
            ),
            display_name="Terminal Tester",
        ),
        action=ApprovalChannelAction(
            approval_id="apr-terminal-test",
            decision=ApprovalDecision.APPROVE,
        ),
    )


def test_resolved_message_requires_positive_verification():
    state = _state()

    message = (
        render_incident_terminal_result(
            state
        )
    )

    assert "Incidencia resuelta" in message
    assert "PROC-TERMINAL-001" in message

    assert "subscription" not in message.lower()
    assert "resource_group" not in message.lower()
    assert "capability" not in message.lower()


def test_resolved_without_verification_fails_closed():
    state = _state(
        verification_success=None
    )

    with pytest.raises(
        IncidentTerminalPresentationError
    ):
        render_incident_terminal_result(
            state
        )


def test_rejected_message_never_claims_execution():
    state = _state(
        workflow_status=(
            WorkflowStatus.BLOCKED
        ),
        step_status=StepStatus.REJECTED,
        approval_status=(
            ApprovalStatus.REJECTED
        ),
        verification_success=None,
    )

    message = (
        render_incident_terminal_result(
            state
        )
    )

    assert "Operación rechazada" in message
    assert "No se ha ejecutado" in message


def test_non_terminal_state_fails_closed():
    state = _state(
        workflow_status=(
            WorkflowStatus.RUNNING
        ),
        step_status=StepStatus.RUNNING,
        verification_success=None,
    )

    with pytest.raises(
        IncidentTerminalPresentationError
    ):
        render_incident_terminal_result(
            state
        )


@pytest.mark.asyncio
async def test_notifier_uses_authorized_teams_destination(
    monkeypatch,
):
    captured = {}

    async def fake_send(
        *,
        dependencies,
        tenant_id,
        conversation_id,
        text,
    ):
        captured["dependencies"] = dependencies
        captured["tenant_id"] = tenant_id
        captured["conversation_id"] = (
            conversation_id
        )
        captured["text"] = text

        return "sent"

    monkeypatch.setattr(
        "src.channels.teams."
        "incident_terminal_presenter."
        "send_teams_message",
        fake_send,
    )

    invocation = _invocation()

    processed = SimpleNamespace(
        workflow_result=_state()
    )

    outbound = object()

    result = await (
        notify_teams_incident_terminal_result(
            invocation=invocation,
            processed=processed,
            outbound=outbound,
        )
    )

    assert result == "sent"

    assert (
        captured["tenant_id"]
        == invocation.operator.tenant_id
    )

    assert (
        captured["conversation_id"]
        == invocation.operator.conversation_id
    )


@pytest.mark.asyncio
async def test_notifier_rejects_conversation_substitution(
    monkeypatch,
):
    async def should_not_send(**kwargs):
        raise AssertionError(
            "send no debe ejecutarse"
        )

    monkeypatch.setattr(
        "src.channels.teams."
        "incident_terminal_presenter."
        "send_teams_message",
        should_not_send,
    )

    processed = SimpleNamespace(
        workflow_result=_state(
            conversation_id=(
                "foreign-conversation"
            )
        )
    )

    with pytest.raises(
        IncidentTerminalPresentationError
    ):
        await (
            notify_teams_incident_terminal_result(
                invocation=_invocation(),
                processed=processed,
                outbound=object(),
            )
        )