import json

import pytest

from agent_framework import (
    InMemoryCheckpointStorage,
)

from src.agents.contracts import (
    ProcedureValidationEscalation,
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.operation_result_correlation import (
    validate_operation_result_against_runtime,
)

from src.workflows.incident_resolution.procedure_transition_gate import (
    apply_procedure_validation_transition,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
    ProcedureValidationStep,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


class ReplaySecurityFakeFoundryAgents(
    AzureWorkflowFakeFoundryAgents
):
    """
    Ejecuta un único ciclo real offline y conserva
    los artefactos necesarios para intentar replay.

    El workflow, HITL, correlación, registration y
    Transition Gate continúan siendo producción.
    """

    def __init__(
        self,
        *,
        validation_status: str,
        proposed_next_action: str,
    ) -> None:
        super().__init__()

        self.validation_status = (
            validation_status
        )

        self.proposed_next_action = (
            proposed_next_action
        )

        self.validation_payload: (
            dict | None
        ) = None

    async def run_procedure_validation(
        self,
        message: str,
    ) -> ProcedureValidationResult:
        self.calls.append(
            "procedure_validation"
        )

        self.procedure_validation_prompt = (
            message
        )

        payload = json.loads(
            message
        )

        self.validation_payload = payload

        operation_id = (
            payload[
                "trusted_identity"
            ][
                "operation_id"
            ]
        )

        return ProcedureValidationResult(
            operation_id=operation_id,

            validation_status=(
                self.validation_status
            ),

            proposed_next_action=(
                self.proposed_next_action
            ),

            validation_summary=(
                "Validation result used for "
                "replay security testing."
            ),

            escalation=(
                ProcedureValidationEscalation(
                    required=False
                )
            ),
        )


async def run_cycle(
    *,
    validation_status: str,
    proposed_next_action: str,
):
    agents = ReplaySecurityFakeFoundryAgents(
        validation_status=(
            validation_status
        ),
        proposed_next_action=(
            proposed_next_action
        ),
    )

    storage = (
        InMemoryCheckpointStorage()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "request_info":
            responses[
                event.request_id
            ] = True

    assert len(responses) == 1

    outputs = []
    fresh_requests = []

    async for event in workflow.run(
        responses=responses,
        stream=True,
        checkpoint_storage=storage,
    ):
        if event.type == "output":
            outputs.append(
                event.data
            )

        elif event.type == "request_info":
            fresh_requests.append(
                event
            )

    assert (
        agents.validation_payload
        is not None
    )

    if (
        proposed_next_action
        != "repeat"
    ):
        assert len(outputs) == 1
        assert fresh_requests == []

        state = outputs[0]

        assert isinstance(
            state,
            ProcedureRuntimeState,
        )

        return (
            agents,
            state,
        )

    assert outputs == []
    assert len(fresh_requests) == 1

    fresh_request = (
        fresh_requests[0]
    )

    checkpoints = (
        await storage.list_checkpoints(
            workflow_name=workflow.name
        )
    )

    candidates = []

    for checkpoint in checkpoints:
        snapshot = checkpoint.state.get(
            "procedure_runtime_state"
        )

        if snapshot is None:
            continue

        if (
            fresh_request.request_id
            not in checkpoint
            .pending_request_info_events
        ):
            continue

        state = (
            ProcedureRuntimeState
            .model_validate(
                snapshot
            )
        )

        if (
            state.retry_count == 1
            and state.step_status
            == StepStatus.WAITING_APPROVAL
            and state.workflow_status
            == WorkflowStatus.WAITING_HUMAN
            and state.approval_status
            == ApprovalStatus.PENDING
            and state.approval_id
            == fresh_request.data.approval_id
            and state.operation_result
            is None
            and state.verification_result
            is None
        ):
            candidates.append(
                state
            )

    assert len(candidates) == 1

    return (
        agents,
        candidates[0],
    )


def rebuild_validation_context(
    payload: dict,
) -> ProcedureValidationContext:
    """
    Reconstruye el contexto cognitivo exacto
    utilizado por un ciclo anterior.

    Es deliberadamente un REPLAY.

    ProcedureValidationRequest sólo contiene:

    - operation_result;
    - step.

    trusted_identity pertenece al envelope del
    prompt y no se inyecta como campos extra
    dentro del contrato autoritativo.
    """

    request = (
        ProcedureValidationRequest
        .model_validate(
            {
                "operation_result": (
                    payload[
                        "operation_result"
                    ]
                ),

                "step": (
                    payload[
                        "step"
                    ]
                ),
            }
        )
    )

    result = (
        ProcedureValidationResult(
            operation_id=(
                payload[
                    "trusted_identity"
                ][
                    "operation_id"
                ]
            ),

            validation_status=(
                "indeterminate"
            ),

            proposed_next_action=(
                "wait"
            ),

            validation_summary=(
                "Replayed validation context."
            ),

            escalation=(
                ProcedureValidationEscalation(
                    required=False
                )
            ),
        )
    )

    return ProcedureValidationContext(
        request=request,
        result=result,
    )


@pytest.mark.asyncio
async def test_validation_context_cannot_be_replayed_after_continue():
    """
    Una validación ya consumida por CONTINUE no
    puede aplicarse otra vez.

    Tras la primera transición el runtime ya no
    está WAITING_VALIDATION.
    """

    (
        agents,
        state,
    ) = await run_cycle(
        validation_status="satisfied",
        proposed_next_action="continue",
    )

    assert (
        state.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        state.workflow_status
        == WorkflowStatus.RESOLVED
    )

    replay_context = (
        rebuild_validation_context(
            agents.validation_payload
        )
    )

    with pytest.raises(
        ValueError,
        match="waiting_validation",
    ):
        apply_procedure_validation_transition(
            state=state,
            context=replay_context,
        )


@pytest.mark.asyncio
async def test_wait_state_rejects_second_validation_of_same_result():
    """
    WAIT conserva OperationResult y
    verification_result.

    Precisamente por eso un segundo contexto
    cognitivo no puede consumir de nuevo el mismo
    resultado sin un nuevo lifecycle explícito.
    """

    (
        agents,
        state,
    ) = await run_cycle(
        validation_status="indeterminate",
        proposed_next_action="wait",
    )

    assert (
        state.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        state.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    assert (
        state.operation_result
        is not None
    )

    assert (
        state.verification_result
        is not None
    )

    replay_context = (
        rebuild_validation_context(
            agents.validation_payload
        )
    )

    with pytest.raises(
        ValueError,
    ):
        apply_procedure_validation_transition(
            state=state,
            context=replay_context,
        )


@pytest.mark.asyncio
async def test_repeat_state_rejects_old_operation_result_replay():
    """
    Tras REPEAT existe ya un NUEVO HITL,
    pero el resultado operacional anterior
    continúa sin autoridad sobre ese intento.
    """

    (
        agents,
        state,
    ) = await run_cycle(
        validation_status="not_satisfied",
        proposed_next_action="repeat",
    )

    payload = agents.validation_payload

    old_result = (
        OperationResult.model_validate(
            payload[
                "operation_result"
            ]
        )
    )

    assert (
        state.step_status
        == StepStatus.WAITING_APPROVAL
    )

    assert (
        state.workflow_status
        == WorkflowStatus.WAITING_HUMAN
    )

    assert state.retry_count == 1

    assert state.approval_id is not None

    assert (
        state.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        old_result.approval_id
        != state.approval_id
    )

    assert state.operation_result is None
    assert state.verification_result is None

    with pytest.raises(
        ValueError,
    ):
        validate_operation_result_against_runtime(
            old_result,
            state,
        )


@pytest.mark.asyncio
async def test_repeat_does_not_preserve_old_operation_identity_as_authority():
    """
    El nuevo intento REPEAT posee un HITL fresco.

    Antes de aprobarlo:
    - no existe segundo OperationResult;
    - no existe segunda validation;
    - el approval_id anterior no es autoridad;
    - sólo ocurrió una operación Azure.
    """

    (
        agents,
        state,
    ) = await run_cycle(
        validation_status="not_satisfied",
        proposed_next_action="repeat",
    )

    payload = agents.validation_payload

    old_result = (
        OperationResult.model_validate(
            payload[
                "operation_result"
            ]
        )
    )

    old_operation_id = (
        old_result.operation_id
    )

    assert old_operation_id

    assert state.retry_count == 1

    assert state.approval_id is not None

    assert (
        state.approval_id
        != old_result.approval_id
    )

    assert state.operation_result is None
    assert state.verification_result is None

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_execution"
        )
        == 2
    )
