from dataclasses import (
    replace,
)

import pytest

from src.runtime.procedure.identity import (
    create_approval_id,
    create_workflow_id,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
)


ALERT_ID = (
    "ALT-AZ-RG-LIST-001"
)

CORRELATION_ID = (
    "corr-azure-rg-list-live-001"
)

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)


def create_pending_state(
    *,
    workflow_id: str,
    approval_id: str,
    correlation_id: str = CORRELATION_ID,
) -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id=workflow_id,

        approval_id=approval_id,

        alert_id=ALERT_ID,

        correlation_id=(
            correlation_id
        ),

        procedure=ProcedureReference(
            id="NTTSY-SBX-AZ-001",

            name=(
                "Consulta de Resource Groups "
                "de una suscripción Azure"
            ),

            version="v1.0",
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Consultar Resource Groups."
            ),

            step_type=(
                "technical_operation"
            ),

            operation_domain="azure",

            operation_kind=(
                OperationKind.READ
            ),

            target_resource=(
                "subscription"
            ),

            required_parameters=[
                "subscription_id",
            ],

            preconditions=[],

            expected_result=(
                "Lista de Resource Groups."
            ),

            verification=(
                "Validar resultado."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        workflow_status=(
            WorkflowStatus.WAITING_HUMAN
        ),

        step_status=(
            StepStatus.WAITING_APPROVAL
        ),

        approval_status=(
            ApprovalStatus.PENDING
        ),
    )


def test_same_alert_gets_different_workflow_ids():
    workflow_a = (
        create_workflow_id()
    )

    workflow_b = (
        create_workflow_id()
    )

    assert workflow_a != workflow_b

    assert workflow_a.startswith(
        "wf-"
    )

    assert workflow_b.startswith(
        "wf-"
    )


def test_new_approval_requests_get_different_approval_ids():
    approval_a = (
        create_approval_id()
    )

    approval_b = (
        create_approval_id()
    )

    assert approval_a != approval_b

    assert approval_a.startswith(
        "apr-"
    )

    assert approval_b.startswith(
        "apr-"
    )


def test_approval_from_execution_a_cannot_approve_execution_b():
    state_a = (
        create_pending_state(
            workflow_id=(
                create_workflow_id()
            ),

            approval_id=(
                create_approval_id()
            ),
        )
    )

    state_b = (
        create_pending_state(
            workflow_id=(
                create_workflow_id()
            ),

            approval_id=(
                create_approval_id()
            ),
        )
    )

    executor = (
        ProcedureApprovalExecutor()
    )

    request_a = (
        executor._build_approval_request(
            state_a
        )
    )

    executor._pending_state = (
        state_b
    )

    with pytest.raises(
        RuntimeError,
        match="workflow_id",
    ):
        executor._validate_original_request(
            request_a
        )


def test_old_approval_cannot_approve_new_request_in_same_workflow():
    workflow_id = (
        create_workflow_id()
    )

    old_state = (
        create_pending_state(
            workflow_id=workflow_id,

            approval_id=(
                create_approval_id()
            ),
        )
    )

    new_state = (
        create_pending_state(
            workflow_id=workflow_id,

            approval_id=(
                create_approval_id()
            ),
        )
    )

    executor = (
        ProcedureApprovalExecutor()
    )

    old_request = (
        executor._build_approval_request(
            old_state
        )
    )

    executor._pending_state = (
        new_state
    )

    with pytest.raises(
        RuntimeError,
        match="approval_id",
    ):
        executor._validate_original_request(
            old_request
        )


def test_correlation_id_tampering_is_rejected():
    state = (
        create_pending_state(
            workflow_id=(
                create_workflow_id()
            ),

            approval_id=(
                create_approval_id()
            ),
        )
    )

    executor = (
        ProcedureApprovalExecutor()
    )

    executor._pending_state = (
        state
    )

    request = (
        executor._build_approval_request(
            state
        )
    )

    tampered = replace(
        request,

        correlation_id=(
            "corr-attacker"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="correlation_id",
    ):
        executor._validate_original_request(
            tampered
        )


class FakeResponseContext:
    def __init__(self):
        self.messages = []
        self.outputs = []

    async def send_message(
        self,
        message,
    ):
        self.messages.append(
            message
        )

    async def yield_output(
        self,
        output,
    ):
        self.outputs.append(
            output
        )


@pytest.mark.asyncio
async def test_consumed_approval_cannot_be_replayed():
    state = (
        create_pending_state(
            workflow_id=(
                create_workflow_id()
            ),

            approval_id=(
                create_approval_id()
            ),
        )
    )

    executor = (
        ProcedureApprovalExecutor()
    )

    executor._pending_state = (
        state
    )

    request = (
        executor._build_approval_request(
            state
        )
    )

    ctx = (
        FakeResponseContext()
    )

    await executor.handle_approval_response(
        request,
        True,
        ctx,
    )

    assert (
        executor._pending_state
        is None
    )

    assert len(
        ctx.messages
    ) == 1

    approved_step = (
        ctx.messages[0]
    )

    assert (
        approved_step.workflow_id
        == state.workflow_id
    )

    assert (
        approved_step.approval_id
        == state.approval_id
    )

    assert (
        approved_step.correlation_id
        == CORRELATION_ID
    )

    #
    # Replay.
    #
    with pytest.raises(
        RuntimeError,
        match="sin estado pendiente",
    ):
        await executor.handle_approval_response(
            request,
            True,
            ctx,
        )