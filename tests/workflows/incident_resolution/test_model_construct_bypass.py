import pytest

from src.agents.contracts import (
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.operation_models import (
    OperationEvidence,
    OperationResult,
)

from src.workflows.incident_resolution.procedure_transition_gate import (
    apply_procedure_validation_transition,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
    ProcedureValidationRequest,
    ProcedureValidationStep,
)

from tests.workflows.incident_resolution.test_post_registration_tampering import (
    create_context,
    create_registered_validation_boundary,
)


def field_values(
    model,
    model_type,
):
    """
    Extrae los valores reales de los fields sin
    pasar por model_dump.

    Esto es deliberado: queremos conservar objetos
    nested reales y después usar model_construct()
    para saltarnos Pydantic.
    """

    return {
        field_name: getattr(
            model,
            field_name,
        )
        for field_name
        in model_type.model_fields
    }


def assert_gate_rejects_without_mutating_state(
    *,
    state,
    context,
):
    before = state.model_dump(
        mode="json"
    )

    with pytest.raises(
        ValueError,
    ):
        apply_procedure_validation_transition(
            state=state,
            context=context,
        )

    after = state.model_dump(
        mode="json"
    )

    assert after == before


@pytest.mark.asyncio
async def test_model_construct_cannot_bypass_operation_evidence_identity():
    """
    Ataque:

    OperationResult.operation_id = atacante

    pero:

    OperationEvidence.operation_id = original

    Ambos objetos se crean mediante
    model_construct(), evitando sus validadores.

    El Transition Gate debe revalidar el contexto
    antes de confiar en él.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    original_result = (
        request.operation_result
    )

    original_evidence = (
        original_result.evidence
    )

    assert (
        original_evidence
        is not None
    )

    attacker_operation_id = (
        "op-33333333-3333-4333-"
        "8333-333333333333"
    )

    assert (
        attacker_operation_id
        != original_result.operation_id
    )

    evidence_data = field_values(
        original_evidence,
        OperationEvidence,
    )

    #
    # Conservamos deliberadamente el operation_id
    # ORIGINAL en la evidencia.
    #
    forged_evidence = (
        OperationEvidence.model_construct(
            **evidence_data
        )
    )

    result_data = field_values(
        original_result,
        OperationResult,
    )

    result_data[
        "operation_id"
    ] = attacker_operation_id

    result_data[
        "evidence"
    ] = forged_evidence

    #
    # Esta construcción no ejecuta la validación
    # normal de OperationResult.
    #
    forged_result = (
        OperationResult.model_construct(
            **result_data
        )
    )

    assert (
        forged_result.operation_id
        == attacker_operation_id
    )

    assert (
        forged_result
        .evidence
        .operation_id
        != forged_result.operation_id
    )

    forged_request = (
        ProcedureValidationRequest
        .model_construct(
            operation_result=(
                forged_result
            ),
            step=request.step,
        )
    )

    valid_context = create_context(
        request
    )

    forged_context = (
        ProcedureValidationContext
        .model_construct(
            request=forged_request,
            result=valid_context.result,
        )
    )

    assert_gate_rejects_without_mutating_state(
        state=state,
        context=forged_context,
    )


@pytest.mark.asyncio
async def test_model_construct_cannot_bypass_cognitive_operation_id_binding():
    """
    Ataque:

    ProcedureValidationResult.operation_id
    se altera mediante model_construct().

    ProcedureValidationContext también se crea con
    model_construct(), por lo que su validator de
    correlación no se ejecuta inicialmente.

    El Gate debe revalidarlo.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    valid_context = create_context(
        request
    )

    attacker_operation_id = (
        "op-44444444-4444-4444-"
        "8444-444444444444"
    )

    assert (
        attacker_operation_id
        != request
        .operation_result
        .operation_id
    )

    original_result = (
        valid_context.result
    )

    result_data = field_values(
        original_result,
        ProcedureValidationResult,
    )

    result_data[
        "operation_id"
    ] = attacker_operation_id

    forged_result = (
        ProcedureValidationResult
        .model_construct(
            **result_data
        )
    )

    assert (
        forged_result.operation_id
        == attacker_operation_id
    )

    forged_context = (
        ProcedureValidationContext
        .model_construct(
            request=request,
            result=forged_result,
        )
    )

    assert (
        forged_context
        .request
        .operation_result
        .operation_id
        != forged_context
        .result
        .operation_id
    )

    assert_gate_rejects_without_mutating_state(
        state=state,
        context=forged_context,
    )


@pytest.mark.asyncio
async def test_model_construct_cannot_bypass_step_identity_binding():
    """
    Ataque nested:

    ProcedureValidationStep.step_id = 999

    pero OperationResult conserva el step_id
    autoritativo.

    Se usan model_construct() tanto para Step como
    para Request y Context para impedir que la
    inconsistencia sea rechazada durante la
    fabricación del ataque.

    El Gate debe detectarla al revalidar.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    original_step = (
        request.step
    )

    attacker_step_id = "999"

    assert (
        attacker_step_id
        != original_step.step_id
    )

    step_data = field_values(
        original_step,
        ProcedureValidationStep,
    )

    step_data[
        "step_id"
    ] = attacker_step_id

    forged_step = (
        ProcedureValidationStep
        .model_construct(
            **step_data
        )
    )

    assert (
        forged_step.step_id
        == attacker_step_id
    )

    assert (
        request
        .operation_result
        .step_id
        != forged_step.step_id
    )

    forged_request = (
        ProcedureValidationRequest
        .model_construct(
            operation_result=(
                request.operation_result
            ),
            step=forged_step,
        )
    )

    valid_context = create_context(
        request
    )

    forged_context = (
        ProcedureValidationContext
        .model_construct(
            request=forged_request,
            result=valid_context.result,
        )
    )

    assert_gate_rejects_without_mutating_state(
        state=state,
        context=forged_context,
    )


@pytest.mark.asyncio
async def test_model_construct_cannot_bypass_runtime_lifecycle():
    """
    Ataque al propio runtime:

    estado registrado:
        step     = WAITING_VALIDATION
        workflow = WAITING_VALIDATION

    objeto forjado:
        step     = WAITING_VALIDATION
        workflow = RUNNING

    model_construct() evita cualquier validación
    inicial del ProcedureRuntimeState.

    El Transition Gate debe seguir exigiendo la
    pareja exacta WAITING_VALIDATION /
    WAITING_VALIDATION.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    assert (
        state.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        state.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
    )

    state_data = field_values(
        state,
        ProcedureRuntimeState,
    )

    state_data[
        "workflow_status"
    ] = WorkflowStatus.RUNNING

    forged_state = (
        ProcedureRuntimeState
        .model_construct(
            **state_data
        )
    )

    assert (
        forged_state.step_status
        == StepStatus.WAITING_VALIDATION
    )

    assert (
        forged_state.workflow_status
        == WorkflowStatus.RUNNING
    )

    context = create_context(
        request
    )

    before = forged_state.model_dump(
        mode="json"
    )

    with pytest.raises(
        ValueError,
    ):
        apply_procedure_validation_transition(
            state=forged_state,
            context=context,
        )

    after = forged_state.model_dump(
        mode="json"
    )

    assert (
        after
        == before
    )
