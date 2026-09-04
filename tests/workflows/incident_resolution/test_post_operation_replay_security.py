import json

import pytest

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

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            responses[
                event.request_id
            ] = True

    assert len(responses) == 1

    outputs = []

    async for event in workflow.run(
        responses=responses,
        stream=True,
    ):
        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    assert len(outputs) == 1

    state = outputs[0]

    assert isinstance(
        state,
        ProcedureRuntimeState,
    )

    assert (
        agents.validation_payload
        is not None
    )

    return (
        agents,
        state,
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
    REPEAT invalida la autoridad del ciclo anterior.

    El OperationResult viejo puede seguir existiendo
    fuera del runtime como dato histórico, pero no
    puede volver a registrarse como autoridad.
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
        == StepStatus.PENDING
    )

    assert (
        state.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert (
        state.approval_id
        is None
    )

    assert (
        state.approval_status
        == ApprovalStatus.PENDING
    )

    assert (
        state.operation_result
        is None
    )

    assert (
        state.verification_result
        is None
    )

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
    Tras REPEAT:

    - no approval_id;
    - no registered OperationResult;
    - no verification result;
    - no segundo Azure call;
    - no segundo Procedure Validation.

    La identidad del intento anterior sólo puede
    permanecer fuera del runtime como evidencia
    histórica, nunca como autorización vigente.
    """

    (
        agents,
        state,
    ) = await run_cycle(
        validation_status="not_satisfied",
        proposed_next_action="repeat",
    )

    old_operation_id = (
        agents.validation_payload[
            "trusted_identity"
        ][
            "operation_id"
        ]
    )

    assert old_operation_id

    assert (
        state.approval_id
        is None
    )

    assert (
        state.operation_result
        is None
    )

    assert (
        state.verification_result
        is None
    )

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

    #
    # FASE 16 no genera una identidad operacional
    # para el próximo intento.
    #
    assert (
        old_operation_id
        not in {
            getattr(
                state,
                "operation_id",
                None,
            ),
        }
    )
