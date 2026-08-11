import pytest

from src.agents.contracts import (
    ProcedureValidationEscalation,
    ProcedureValidationResult,
)

from src.runtime.procedure.models import (
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow_state import (
    load_procedure_runtime_state,
    store_procedure_runtime_state,
)

from src.workflows.incident_resolution.executors.operation_result_registration import (
    OperationResultRegistrationExecutor,
)

from src.workflows.incident_resolution.operation_models import (
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

from tests.workflows.incident_resolution.test_operation_result_registration import (
    create_result,
    create_runtime_state,
)


class FakeWorkflowContext:
    """
    Contexto mínimo compatible con el storage
    utilizado por OperationResultRegistrationExecutor.

    No sustituye ninguna lógica de producción.
    """

    def __init__(self):
        self._state = {}
        self.messages = []

    def get_state(
        self,
        key,
        default=None,
    ):
        return self._state.get(
            key,
            default,
        )

    def set_state(
        self,
        key,
        value,
    ):
        self._state[
            key
        ] = value

    async def send_message(
        self,
        message,
    ):
        self.messages.append(
            message
        )


async def create_registered_validation_boundary():
    """
    Construye la frontera real:

        RUNNING / WAITING_OPERATION
                ↓
        OperationResultRegistrationExecutor
                ↓
        WAITING_VALIDATION
                ↓
        ProcedureValidationRequest

    No fabricamos manualmente el estado posterior
    al registro.
    """

    initial_state = (
        create_runtime_state()
    )

    operation_result = (
        create_result()
    )

    ctx = FakeWorkflowContext()

    store_procedure_runtime_state(
        ctx,
        initial_state,
    )

    executor = (
        OperationResultRegistrationExecutor()
    )

    await executor.handle(
        operation_result,
        ctx,
    )

    assert len(
        ctx.messages
    ) == 1

    request = (
        ctx.messages[0]
    )

    assert isinstance(
        request,
        ProcedureValidationRequest,
    )

    state = (
        load_procedure_runtime_state(
            ctx
        )
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
        is None
    )

    return (
        state,
        request,
    )


def create_cognitive_result(
    *,
    operation_id: str,
) -> ProcedureValidationResult:
    return ProcedureValidationResult(
        operation_id=operation_id,

        validation_status=(
            "satisfied"
        ),

        proposed_next_action=(
            "continue"
        ),

        validation_summary=(
            "Controlled validation result."
        ),

        escalation=(
            ProcedureValidationEscalation(
                required=False
            )
        ),
    )


def create_context(
    request: ProcedureValidationRequest,
) -> ProcedureValidationContext:
    result = create_cognitive_result(
        operation_id=(
            request
            .operation_result
            .operation_id
        )
    )

    return ProcedureValidationContext(
        request=request,
        result=result,
    )


def tamper_operation_result(
    request: ProcedureValidationRequest,
    **updates,
) -> ProcedureValidationRequest:
    """
    Simula tampering POST-registration.

    El objeto atacante se mantiene internamente
    coherente:

        OperationResult.<identity>
            ==
        OperationEvidence.<identity>

    De esta forma el ataque supera la validación
    estructural del modelo y debe ser rechazado
    por comparación contra el resultado
    autoritativamente registrado.
    """

    original = (
        request.operation_result
    )

    #
    # Guardia del propio test:
    # un supuesto ataque no puede utilizar
    # accidentalmente el valor original.
    #
    for field_name, value in updates.items():
        if (
            getattr(
                original,
                field_name,
            )
            == value
        ):
            raise AssertionError(
                "El test no está realizando "
                "tampering real: "
                f"{field_name} conserva su "
                "valor original."
            )

    data = (
        original.model_dump(
            mode="python"
        )
    )

    data.update(
        updates
    )

    #
    # Mantener OperationEvidence coherente con la
    # identidad manipulada.
    #
    evidence_data = data.get(
        "evidence"
    )

    if evidence_data is not None:
        if hasattr(
            evidence_data,
            "model_dump",
        ):
            evidence_data = (
                evidence_data.model_dump(
                    mode="python"
                )
            )
        else:
            evidence_data = dict(
                evidence_data
            )

        for (
            field_name,
            value,
        ) in updates.items():
            if (
                field_name
                in evidence_data
            ):
                evidence_data[
                    field_name
                ] = value

        data[
            "evidence"
        ] = evidence_data

    tampered_result = (
        OperationResult.model_validate(
            data
        )
    )

    request_data = (
        request.model_dump(
            mode="python"
        )
    )

    request_data[
        "operation_result"
    ] = tampered_result

    return (
        ProcedureValidationRequest
        .model_validate(
            request_data
        )
    )


def tamper_step(
    request: ProcedureValidationRequest,
    **updates,
) -> ProcedureValidationRequest:
    """
    Altera el step manteniendo coherentes todas
    las copias de identidad necesarias para que
    el ataque alcance realmente el Transition
    Gate.
    """

    for field_name, value in updates.items():
        if (
            getattr(
                request.step,
                field_name,
            )
            == value
        ):
            raise AssertionError(
                "El test no está realizando "
                "tampering real sobre step: "
                f"{field_name} conserva su "
                "valor original."
            )

    step_data = (
        request.step.model_dump(
            mode="python"
        )
    )

    step_data.update(
        updates
    )

    tampered_step = (
        ProcedureValidationStep
        .model_validate(
            step_data
        )
    )

    #
    # ProcedureValidationRequest exige coherencia
    # entre Step y OperationResult.
    #
    operation_data = (
        request
        .operation_result
        .model_dump(
            mode="python"
        )
    )

    for (
        field_name,
        value,
    ) in updates.items():
        if (
            field_name
            in operation_data
        ):
            operation_data[
                field_name
            ] = value

    evidence_data = (
        operation_data.get(
            "evidence"
        )
    )

    if evidence_data is not None:
        if hasattr(
            evidence_data,
            "model_dump",
        ):
            evidence_data = (
                evidence_data.model_dump(
                    mode="python"
                )
            )
        else:
            evidence_data = dict(
                evidence_data
            )

        for (
            field_name,
            value,
        ) in updates.items():
            if (
                field_name
                in evidence_data
            ):
                evidence_data[
                    field_name
                ] = value

        operation_data[
            "evidence"
        ] = evidence_data

    tampered_result = (
        OperationResult.model_validate(
            operation_data
        )
    )

    request_data = (
        request.model_dump(
            mode="python"
        )
    )

    request_data[
        "operation_result"
    ] = tampered_result

    request_data[
        "step"
    ] = tampered_step

    return (
        ProcedureValidationRequest
        .model_validate(
            request_data
        )
    )


def assert_rejected_without_state_mutation(
    *,
    state,
    context,
):
    """
    Un ataque rechazado tampoco puede dejar
    mutación parcial del runtime autoritativo.
    """

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

    assert (
        after
        == before
    )


@pytest.mark.asyncio
async def test_registered_validation_boundary_accepts_exact_context():
    """
    Control positivo.

    La fixture debe demostrar que alcanza
    realmente el Transition Gate antes de empezar
    a introducir tampering.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    context = create_context(
        request
    )

    transitioned = (
        apply_procedure_validation_transition(
            state=state,
            context=context,
        )
    )

    assert (
        transitioned.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        transitioned.workflow_status
        == WorkflowStatus.RUNNING
    )

    assert (
        transitioned.verification_result
        is not None
    )


@pytest.mark.asyncio
async def test_post_registration_operation_id_tampering_is_rejected():
    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    tampered_request = (
        tamper_operation_result(
            request,
            operation_id=(
                "op-11111111-1111-4111-"
                "8111-111111111111"
            ),
        )
    )

    context = create_context(
        tampered_request
    )

    assert_rejected_without_state_mutation(
        state=state,
        context=context,
    )


@pytest.mark.asyncio
async def test_post_registration_approval_id_tampering_is_rejected():
    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    original_approval_id = (
        request
        .operation_result
        .approval_id
    )

    tampered_request = (
        tamper_operation_result(
            request,
            approval_id=(
                "apr-22222222-2222-4222-"
                "8222-222222222222"
            ),
        )
    )

    assert (
        tampered_request
        .operation_result
        .approval_id
        != original_approval_id
    )

    context = create_context(
        tampered_request
    )

    assert_rejected_without_state_mutation(
        state=state,
        context=context,
    )


@pytest.mark.asyncio
async def test_post_registration_workflow_id_tampering_is_rejected():
    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    original_workflow_id = (
        request
        .operation_result
        .workflow_id
    )

    tampered_request = (
        tamper_operation_result(
            request,
            workflow_id=(
                "wf-22222222-2222-4222-"
                "8222-222222222222"
            ),
        )
    )

    assert (
        tampered_request
        .operation_result
        .workflow_id
        != original_workflow_id
    )

    context = create_context(
        tampered_request
    )

    assert_rejected_without_state_mutation(
        state=state,
        context=context,
    )


@pytest.mark.asyncio
async def test_post_registration_step_id_tampering_is_rejected():
    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    tampered_request = (
        tamper_step(
            request,
            step_id="999",
        )
    )

    context = create_context(
        tampered_request
    )

    assert_rejected_without_state_mutation(
        state=state,
        context=context,
    )


@pytest.mark.asyncio
async def test_embedded_operation_result_content_tampering_is_rejected():
    """
    No basta con proteger sólo los IDs.

    También el contenido del OperationResult
    entregado a Procedure Validation debe ser
    exactamente el registrado.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    tampered_request = (
        tamper_operation_result(
            request,
            response_text=(
                "TAMPERED POST-REGISTRATION RESULT"
            ),
        )
    )

    context = create_context(
        tampered_request
    )

    assert_rejected_without_state_mutation(
        state=state,
        context=context,
    )


@pytest.mark.asyncio
async def test_cognitive_operation_id_tampering_is_rejected():
    """
    Incluso con request autoritativo intacto,
    Procedure Agent no puede devolver otro
    operation_id y obtener autoridad.
    """

    (
        state,
        request,
    ) = (
        await create_registered_validation_boundary()
    )

    before = state.model_dump(
        mode="json"
    )

    tampered_result = (
        create_cognitive_result(
            operation_id=(
                "op-22222222-2222-4222-"
                "8222-222222222222"
            )
        )
    )

    #
    # ProcedureValidationContext ya puede bloquear
    # esta inconsistencia antes incluso del Gate.
    #
    with pytest.raises(
        ValueError,
    ):
        ProcedureValidationContext(
            request=request,
            result=tampered_result,
        )

    assert (
        state.model_dump(
            mode="json"
        )
        == before
    )
