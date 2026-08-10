from __future__ import annotations

from collections.abc import (
    Mapping,
)

from src.runtime.procedure.models import (
    NextAction,
    ProcedureExecutionResult,
    ProcedureRuntimeState,
    StepEvidence,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.runtime import (
    ProcedureRuntime,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationContext,
)


def _revalidate_state(
    state: ProcedureRuntimeState,
) -> ProcedureRuntimeState:
    """
    Devuelve una copia revalidada.

    El gate nunca modifica el objeto recibido
    por el caller.
    """

    return ProcedureRuntimeState.model_validate(
        state.model_dump(
            mode="python"
        )
    )


def _revalidate_context(
    context: ProcedureValidationContext,
) -> ProcedureValidationContext:
    """
    Revalida también snapshots que pudieran haber
    sido construidos saltándose validadores.
    """

    return ProcedureValidationContext.model_validate(
        context.model_dump(
            mode="python"
        )
    )


def _load_registered_operation_result(
    state: ProcedureRuntimeState,
) -> OperationResult:
    """
    Recupera el OperationResult completo registrado
    por 16.5 dentro de StepEvidence.result.
    """

    evidence = state.operation_result

    if evidence is None:
        raise ValueError(
            "No existe operation_result registrado."
        )

    if not isinstance(
        evidence.result,
        Mapping,
    ):
        raise ValueError(
            "operation_result no contiene un "
            "OperationResult estructurado."
        )

    try:
        result = OperationResult.model_validate(
            evidence.result
        )

    except Exception as exc:
        raise ValueError(
            "OperationResult registrado no supera "
            "la revalidación estructural."
        ) from exc

    if evidence.success != result.success:
        raise ValueError(
            "OperationResult registrado contiene "
            "success inconsistente."
        )

    if evidence.error != result.error:
        raise ValueError(
            "OperationResult registrado contiene "
            "error inconsistente."
        )

    return result


def _validate_runtime_state(
    state: ProcedureRuntimeState,
) -> None:
    if (
        state.step_status
        != StepStatus.WAITING_VALIDATION
        or state.workflow_status
        != WorkflowStatus.WAITING_VALIDATION
    ):
        raise ValueError(
            "Transition Gate requiere "
            "waiting_validation."
        )

    if state.operation_result is None:
        raise ValueError(
            "Transition Gate requiere "
            "operation_result."
        )

    if state.verification_result is not None:
        raise ValueError(
            "Validation replay bloqueado: "
            "verification_result ya existe."
        )


def _validate_operation_result(
    *,
    state: ProcedureRuntimeState,
    request_result: OperationResult,
    registered_result: OperationResult,
) -> None:
    """
    Prueba que el resultado enviado a Procedure
    Validation es exactamente el resultado
    operacional autoritativo registrado.
    """

    request_payload = (
        request_result.model_dump(
            mode="json"
        )
    )

    registered_payload = (
        registered_result.model_dump(
            mode="json"
        )
    )

    if (
        request_payload
        != registered_payload
    ):
        raise ValueError(
            "OperationResult de Procedure Validation "
            "no coincide exactamente con el "
            "OperationResult registrado."
        )

    runtime_fields = {
        "workflow_id":
            state.workflow_id,

        "approval_id":
            state.approval_id,

        "alert_id":
            state.alert_id,

        "correlation_id":
            state.correlation_id,

        "conversation_id":
            state.conversation_id,

        "procedure_id":
            state.procedure.id,

        "procedure_version":
            state.procedure.version,

        "current_step":
            state.current_step,

        "step_id":
            state.step.id,

        "operation_domain":
            state.step.operation_domain,

        "operation_kind":
            state.step.operation_kind,

        "target_resource":
            state.step.target_resource,

        "required_parameters":
            state.step.required_parameters,
    }

    changed_fields = []

    for (
        field_name,
        expected_value,
    ) in runtime_fields.items():
        if (
            getattr(
                request_result,
                field_name,
            )
            != expected_value
        ):
            changed_fields.append(
                field_name
            )

    runtime_resolved = [
        item.model_dump(
            mode="json"
        )
        for item
        in state.resolved_parameters
    ]

    request_resolved = [
        item.model_dump(
            mode="json"
        )
        for item
        in request_result.resolved_parameters
    ]

    if (
        runtime_resolved
        != request_resolved
    ):
        changed_fields.append(
            "resolved_parameters"
        )

    if (
        request_result.next_action
        != NextAction.EXECUTE_STEP
    ):
        changed_fields.append(
            "next_action"
        )

    if changed_fields:
        raise ValueError(
            "OperationResult no corresponde al "
            "ProcedureRuntimeState. Campos distintos: "
            + ", ".join(
                changed_fields
            )
        )


def _validate_step(
    *,
    state: ProcedureRuntimeState,
    context: ProcedureValidationContext,
) -> None:
    """
    El LLM nunca puede sustituir el paso autorizado
    antes de aplicar una transición.
    """

    supplied = (
        context.request.step
    )

    expected = {
        "procedure_id":
            state.procedure.id,

        "procedure_version":
            state.procedure.version,

        "current_step":
            state.current_step,

        "step_id":
            state.step.id,

        "description":
            state.step.description,

        "expected_result":
            state.step.expected_result,

        "verification":
            state.step.verification,
    }

    changed_fields = [
        field_name
        for (
            field_name,
            expected_value,
        )
        in expected.items()
        if (
            getattr(
                supplied,
                field_name,
            )
            != expected_value
        )
    ]

    if changed_fields:
        raise ValueError(
            "ProcedureValidationStep no corresponde "
            "al paso autoritativo. Campos distintos: "
            + ", ".join(
                changed_fields
            )
        )


def _validate_cognitive_result(
    context: ProcedureValidationContext,
) -> None:
    result = context.result

    operation_result = (
        context.request.operation_result
    )

    if (
        result.operation_id
        != operation_result.operation_id
    ):
        raise ValueError(
            "ProcedureValidationResult contiene "
            "un operation_id diferente."
        )

    #
    # Un workflow sólo puede cerrarse cuando
    # Procedure Validation ha demostrado que
    # el criterio está satisfecho.
    #
    if (
        result.proposed_next_action
        == "resolved"
        and result.validation_status
        != "satisfied"
    ):
        raise ValueError(
            "resolved requiere "
            "validation_status=satisfied."
        )

    escalation = result.escalation

    if (
        result.proposed_next_action
        == "escalate"
    ):
        if not escalation.required:
            raise ValueError(
                "escalate requiere "
                "escalation.required=true."
            )

    else:
        if escalation.required:
            raise ValueError(
                "escalation.required sólo puede ser "
                "true cuando la acción es escalate."
            )


def _build_runtime_decision(
    context: ProcedureValidationContext,
) -> ProcedureExecutionResult:
    result = context.result

    return ProcedureExecutionResult(
        next_action=NextAction(
            result.proposed_next_action
        ),

        escalation_required=(
            result.escalation.required
        ),

        escalation_team=(
            result.escalation.team
        ),

        escalation_level=(
            result.escalation.level
        ),

        escalation_criteria=(
            result.escalation.criteria
        ),
    )


def _build_verification_evidence(
    context: ProcedureValidationContext,
) -> StepEvidence:
    result = context.result

    return StepEvidence(
        #
        # success aquí representa únicamente
        # si el criterio de procedimiento quedó
        # demostrado como satisfecho.
        #
        success=(
            result.validation_status
            == "satisfied"
        ),

        result=(
            result.model_dump(
                mode="json"
            )
        ),

        error=None,
    )


def apply_procedure_validation_transition(
    *,
    state: ProcedureRuntimeState,
    context: ProcedureValidationContext,
) -> ProcedureRuntimeState:
    """
    Única puerta determinista entre:

        ProcedureValidationResult
                    ↓
        ProcedureRuntimeState

    No llama:
    - agentes;
    - Foundry;
    - MCP;
    - tools;
    - APIs externas.

    Procedure Validation propone.
    Python autoriza y aplica la transición.
    """

    trusted_state = (
        _revalidate_state(
            state
        )
    )

    trusted_context = (
        _revalidate_context(
            context
        )
    )

    _validate_runtime_state(
        trusted_state
    )

    registered_result = (
        _load_registered_operation_result(
            trusted_state
        )
    )

    request_result = (
        OperationResult.model_validate(
            trusted_context
            .request
            .operation_result
            .model_dump(
                mode="python"
            )
        )
    )

    _validate_operation_result(
        state=trusted_state,
        request_result=request_result,
        registered_result=(
            registered_result
        ),
    )

    _validate_step(
        state=trusted_state,
        context=trusted_context,
    )

    _validate_cognitive_result(
        trusted_context
    )

    runtime = ProcedureRuntime()

    runtime.register_verification_result(
        trusted_state,

        _build_verification_evidence(
            trusted_context
        ),
    )

    runtime.apply_procedure_decision(
        trusted_state,

        _build_runtime_decision(
            trusted_context
        ),
    )

    return trusted_state
