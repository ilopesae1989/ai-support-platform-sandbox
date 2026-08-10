import json

import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    ApprovedProcedureStep,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
    ProcedureApprovalExecutor,
)

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)


PROCEDURE_RUNTIME_STATE_KEY = (
    "procedure_runtime_state"
)


class FakeWorkflowContext:
    def __init__(self) -> None:
        self.states = {}
        self.messages = []
        self.outputs = []
        self.requests = []

    def get_state(
        self,
        key: str,
        default=None,
    ):
        return self.states.get(
            key,
            default,
        )

    def set_state(
        self,
        key: str,
        value,
    ) -> None:
        self.states[key] = value

    async def send_message(
        self,
        message,
    ) -> None:
        self.messages.append(
            message
        )

    async def yield_output(
        self,
        output,
    ) -> None:
        self.outputs.append(
            output
        )

    async def request_info(
        self,
        request_data,
        response_type,
        *,
        request_id=None,
    ) -> None:
        self.requests.append(
            {
                "request_data":
                    request_data,
                "response_type":
                    response_type,
                "request_id":
                    request_id,
            }
        )


def create_state() -> ProcedureRuntimeState:
    return ProcedureRuntimeState(
        workflow_id=(
            "wf-runtime-state-001"
        ),

        alert_id=(
            "ALT-AZ-STATE-001"
        ),

        correlation_id=(
            "corr-runtime-state-001"
        ),

        conversation_id=(
            "conv-runtime-state-001"
        ),

        procedure=ProcedureReference(
            id="NTTSY-SBX-AZ-001",
            name=(
                "Consulta de Resource Groups"
            ),
            version="1.0",
        ),

        total_steps=1,
        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Consultar los Resource Groups "
                "de la suscripción autorizada."
            ),

            step_type="validation",

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
                "La lista de Resource Groups "
                "queda identificada."
            ),

            verification=(
                "Validar que Azure devuelve "
                "los Resource Groups de la "
                "suscripción autorizada."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value=(
                    "557fdabc-f3b6-4c24-"
                    "a9ae-e9e89b5ad172"
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],
    )


@pytest.mark.asyncio
async def test_runtime_executor_persists_authoritative_state_as_json_snapshot(
    monkeypatch,
):
    """
    FASE 16.2

    ProcedureRuntimeExecutor debe registrar el
    ProcedureRuntimeState autoritativo en workflow
    state antes de enviarlo al siguiente executor.

    El valor almacenado debe ser JSON-native,
    no el objeto Pydantic mutable.
    """

    state = create_state()

    executor = (
        ProcedureRuntimeExecutor()
    )

    monkeypatch.setattr(
        executor,
        "_build_runtime_state",
        lambda _: state,
    )

    ctx = FakeWorkflowContext()

    await executor.create_runtime_state(
        object(),
        ctx,
    )

    assert (
        PROCEDURE_RUNTIME_STATE_KEY
        in ctx.states
    )

    stored = ctx.states[
        PROCEDURE_RUNTIME_STATE_KEY
    ]

    assert isinstance(
        stored,
        dict,
    )

    assert (
        stored
        is not state
    )

    # Debe ser serializable sin tipos custom.
    json.dumps(
        stored
    )

    restored = (
        ProcedureRuntimeState
        .model_validate(
            stored
        )
    )

    assert restored == state

    assert ctx.messages == [
        state
    ]


@pytest.mark.asyncio
async def test_hitl_approval_updates_authoritative_runtime_state():
    """
    FASE 16.2

    El estado persistido debe contener primero:

        WAITING_APPROVAL
        +
        approval_id

    y, tras respuesta humana positiva:

        APPROVED
        +
        RUNNING
        +
        mismo approval_id
    """

    state = create_state()

    executor = (
        ProcedureApprovalExecutor()
    )

    ctx = FakeWorkflowContext()

    await executor.prepare_step(
        state,
        ctx,
    )

    assert (
        PROCEDURE_RUNTIME_STATE_KEY
        in ctx.states
    )

    waiting_payload = ctx.states[
        PROCEDURE_RUNTIME_STATE_KEY
    ]

    json.dumps(
        waiting_payload
    )

    waiting_state = (
        ProcedureRuntimeState
        .model_validate(
            waiting_payload
        )
    )

    assert (
        waiting_state.step_status
        == StepStatus.WAITING_APPROVAL
    )

    assert (
        waiting_state.workflow_status
        == WorkflowStatus.WAITING_HUMAN
    )

    assert (
        waiting_state.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        waiting_state.approval_id
        is not None
    )

    original_approval_id = (
        waiting_state.approval_id
    )

    assert len(
        ctx.requests
    ) == 1

    request = (
        ctx.requests[0][
            "request_data"
        ]
    )

    assert (
        ctx.requests[0][
            "response_type"
        ]
        is bool
    )

    await executor.handle_approval_response(
        request,
        True,
        ctx,
    )

    approved_payload = ctx.states[
        PROCEDURE_RUNTIME_STATE_KEY
    ]

    json.dumps(
        approved_payload
    )

    approved_state = (
        ProcedureRuntimeState
        .model_validate(
            approved_payload
        )
    )

    assert (
        approved_state.approval_id
        == original_approval_id
    )

    assert (
        approved_state.approval_status
        == ApprovalStatus.APPROVED
    )

    assert (
        approved_state.step_status
        == StepStatus.APPROVED
    )

    assert (
        approved_state.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert len(
        ctx.messages
    ) == 1

    assert isinstance(
        ctx.messages[0],
        ApprovedProcedureStep,
    )

    assert (
        ctx.messages[0].approval_id
        == original_approval_id
    )


@pytest.mark.asyncio
async def test_hitl_rejection_updates_authoritative_runtime_state():
    """
    FASE 16.2

    Una denegación humana también debe quedar
    reflejada en el estado autoritativo antes
    de producir ApprovalOutcome.
    """

    state = create_state()

    executor = (
        ProcedureApprovalExecutor()
    )

    ctx = FakeWorkflowContext()

    await executor.prepare_step(
        state,
        ctx,
    )

    assert len(
        ctx.requests
    ) == 1

    request = (
        ctx.requests[0][
            "request_data"
        ]
    )

    await executor.handle_approval_response(
        request,
        False,
        ctx,
    )

    assert (
        PROCEDURE_RUNTIME_STATE_KEY
        in ctx.states
    )

    rejected_payload = ctx.states[
        PROCEDURE_RUNTIME_STATE_KEY
    ]

    json.dumps(
        rejected_payload
    )

    rejected_state = (
        ProcedureRuntimeState
        .model_validate(
            rejected_payload
        )
    )

    assert (
        rejected_state.approval_status
        == ApprovalStatus.REJECTED
    )

    assert (
        rejected_state.step_status
        == StepStatus.REJECTED
    )

    assert (
        rejected_state.workflow_status
        == WorkflowStatus.BLOCKED
    )

    assert ctx.messages == []

    assert len(
        ctx.outputs
    ) == 1

    assert isinstance(
        ctx.outputs[0],
        ApprovalOutcome,
    )

    assert (
        ctx.outputs[0].approved
        is False
    )
