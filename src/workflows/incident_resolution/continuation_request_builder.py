from __future__ import annotations

from src.runtime.procedure.models import (
    ApprovalStatus,
    NextAction,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.runtime import (
    CERTIFIED_MAX_PROCEDURE_OPERATION_ATTEMPTS,
)

from src.workflows.incident_resolution.continuation_context import (
    ProcedureContinuationContext,
)

from src.workflows.incident_resolution.models import (
    ExecutionIdentity,
    ProcedureExecutionInput,
    ProcedureExecutionRequest,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.procedure_transition_gate import (
    ProcedureTransitionOutcome,
)


def _revalidate_outcome(
    outcome: ProcedureTransitionOutcome,
) -> ProcedureTransitionOutcome:
    """
    Revalida incluso snapshots construidos saltando
    validadores normales.
    """

    return ProcedureTransitionOutcome.model_validate(
        outcome.model_dump(
            mode="python"
        )
    )


def _revalidate_continuation(
    continuation: ProcedureContinuationContext,
) -> ProcedureContinuationContext:
    """
    El snapshot durable vuelve a atravesar
    validacion estructural antes de convertirse
    en un nuevo request.
    """

    return ProcedureContinuationContext.model_validate(
        continuation.model_dump(
            mode="python"
        )
    )


def _validate_continue_authority(
    *,
    outcome: ProcedureTransitionOutcome,
    continuation: ProcedureContinuationContext,
) -> None:
    """
    Fail closed.

    N+1 solo puede prepararse cuando Python ya ha
    producido una decision efectiva CONTINUE y el
    estado mutado por esa misma decision es
    consistente con la transicion.
    """

    state = outcome.state
    decision = outcome.decision

    if (
        decision.next_action
        != NextAction.CONTINUE
    ):
        raise ValueError(
            "Continuation builder requiere "
            "una decision efectiva CONTINUE."
        )

    if decision.escalation_required:
        raise ValueError(
            "Estado de transicion CONTINUE "
            "inconsistente."
        )

    if (
        state.step_status
        != StepStatus.SUCCEEDED
        or state.workflow_status
        != WorkflowStatus.RUNNING
    ):
        raise ValueError(
            "Estado de transicion CONTINUE "
            "inconsistente."
        )

    if state.verification_result is None:
        raise ValueError(
            "Estado de transicion CONTINUE "
            "inconsistente."
        )

    if (
        state.total_steps <= 0
        or state.current_step <= 0
        or state.current_step
        >= state.total_steps
    ):
        raise ValueError(
            "CONTINUE no dispone de un "
            "paso posterior autoritativo."
        )

    if (
        continuation.procedure_found
        is not True
        or continuation.procedure_match
        != "exact"
        or continuation.execution_eligible
        is not True
    ):
        raise ValueError(
            "Procedure continuation admission "
            "snapshot no esta autorizado."
        )


def build_procedure_continuation_input(
    *,
    outcome: ProcedureTransitionOutcome,
    continuation: ProcedureContinuationContext,
) -> ProcedureExecutionInput:
    """
    Construye exclusivamente el envelope cognitivo
    de N+1.

    No:
    - modifica ProcedureRuntimeState;
    - modifica ProcedureContinuationContext;
    - escribe workflow state;
    - envia mensajes;
    - llama agentes;
    - llama Foundry;
    - llama MCP;
    - ejecuta operaciones.

    Autoridad:
    - transition decision: ProcedureTransitionOutcome;
    - identity/procedure/cursor: ProcedureRuntimeState;
    - admission y contexto original:
      ProcedureContinuationContext.
    """

    trusted_outcome = (
        _revalidate_outcome(
            outcome
        )
    )

    trusted_continuation = (
        _revalidate_continuation(
            continuation
        )
    )

    _validate_continue_authority(
        outcome=trusted_outcome,
        continuation=trusted_continuation,
    )

    state = trusted_outcome.state

    requested_step = (
        state.current_step + 1
    )

    request = ProcedureExecutionRequest(
        alert_id=state.alert_id,

        procedure_found=(
            trusted_continuation
            .procedure_found
        ),

        procedure_match=(
            trusted_continuation
            .procedure_match
        ),

        execution_eligible=(
            trusted_continuation
            .execution_eligible
        ),

        procedure_id=(
            state.procedure.id
        ),

        procedure_name=(
            state.procedure.name
        ),

        procedure_version=(
            state.procedure.version
        ),

        requested_step=(
            requested_step
        ),

        affected_resource=(
            trusted_continuation
            .request_affected_resource
        ),

        incident_description=(
            trusted_continuation
            .incident_description
        ),
    )

    execution_identity = ExecutionIdentity(
        workflow_id=state.workflow_id,
        alert_id=state.alert_id,
        correlation_id=state.correlation_id,
    )

    operational_context = OperationalContext(
        alert_id=state.alert_id,

        affected_resource=(
            trusted_continuation
            .operational_affected_resource
        ),

        resource_type=(
            trusted_continuation
            .resource_type
        ),

        service=(
            trusted_continuation
            .service
        ),

        environment=(
            trusted_continuation
            .environment
        ),

        incident_origin=(
            trusted_continuation
            .incident_origin
        ),

        subscription_id=(
            trusted_continuation
            .subscription_id
        ),

        resource_group=(
            trusted_continuation
            .resource_group
        ),

        vm_name=(
            trusted_continuation
            .vm_name
        ),

        tenant_id=(
            trusted_continuation
            .tenant_id
        ),

        correlation_id=state.correlation_id,
    )

    return ProcedureExecutionInput(
        request=request,
        execution_identity=execution_identity,
        operational_context=operational_context,
    )


def _validate_repeat_authority(
    *,
    outcome: ProcedureTransitionOutcome,
    continuation: ProcedureContinuationContext,
) -> None:
    """
    Fail closed.

    REPEAT representa un nuevo intento concreto
    del mismo paso.

    Nunca reutiliza:
    - approval_id;
    - aprobación previa;
    - parámetros resueltos previos;
    - operation_result;
    - verification_result.

    El cursor no avanza.
    """

    state = outcome.state
    decision = outcome.decision

    if (
        decision.next_action
        != NextAction.REPEAT
    ):
        raise ValueError(
            "Repeat builder requiere "
            "una decision efectiva REPEAT."
        )

    if decision.escalation_required:
        raise ValueError(
            "Estado REPEAT inconsistente."
        )

    if (
        state.step_status
        != StepStatus.PENDING
        or state.workflow_status
        != WorkflowStatus.RUNNING
    ):
        raise ValueError(
            "Estado REPEAT inconsistente."
        )

    if state.approval_id is not None:
        raise ValueError(
            "REPEAT no puede reutilizar approval_id."
        )

    if (
        state.approval_status
        != ApprovalStatus.PENDING
    ):
        raise ValueError(
            "REPEAT requiere aprobación nueva."
        )

    if state.resolved_parameters:
        raise ValueError(
            "REPEAT no puede reutilizar "
            "resolved_parameters."
        )

    if state.operation_result is not None:
        raise ValueError(
            "REPEAT no puede reutilizar "
            "operation_result."
        )

    if state.verification_result is not None:
        raise ValueError(
            "REPEAT no puede reutilizar "
            "verification_result."
        )

    if state.escalation_required:
        raise ValueError(
            "Estado REPEAT inconsistente."
        )

    if state.escalation_team is not None:
        raise ValueError(
            "Estado REPEAT inconsistente."
        )

    if state.escalation_level is not None:
        raise ValueError(
            "Estado REPEAT inconsistente."
        )

    if state.escalation_criteria is not None:
        raise ValueError(
            "Estado REPEAT inconsistente."
        )

    if (
        state.total_steps <= 0
        or state.current_step <= 0
        or state.current_step
        > state.total_steps
    ):
        raise ValueError(
            "REPEAT no dispone de un "
            "cursor autoritativo válido."
        )

    if state.retry_count <= 0:
        raise ValueError(
            "REPEAT requiere retry_count "
            "incrementado por ProcedureRuntime."
        )

    total_attempts = (
        state.total_steps
        + state.retry_count
    )

    if (
        total_attempts
        > CERTIFIED_MAX_PROCEDURE_OPERATION_ATTEMPTS
    ):
        raise ValueError(
            "Procedure iteration budget exceeded."
        )

    if (
        continuation.procedure_found
        is not True
        or continuation.procedure_match
        != "exact"
        or continuation.execution_eligible
        is not True
    ):
        raise ValueError(
            "Procedure continuation admission "
            "snapshot no esta autorizado."
        )


def build_procedure_repeat_input(
    *,
    outcome: ProcedureTransitionOutcome,
    continuation: ProcedureContinuationContext,
) -> ProcedureExecutionInput:
    """
    Construye exclusivamente un nuevo envelope
    cognitivo para el MISMO paso después de REPEAT.

    No:
    - avanza current_step;
    - modifica ProcedureRuntimeState;
    - modifica ProcedureContinuationContext;
    - reutiliza approval;
    - reutiliza operation identity;
    - escribe workflow state;
    - envia mensajes;
    - llama agentes;
    - llama Foundry;
    - llama MCP.

    requested_step permanece Python-owned.
    """

    trusted_outcome = (
        _revalidate_outcome(
            outcome
        )
    )

    trusted_continuation = (
        _revalidate_continuation(
            continuation
        )
    )

    _validate_repeat_authority(
        outcome=trusted_outcome,
        continuation=trusted_continuation,
    )

    state = trusted_outcome.state

    request = ProcedureExecutionRequest(
        alert_id=state.alert_id,

        procedure_found=(
            trusted_continuation
            .procedure_found
        ),

        procedure_match=(
            trusted_continuation
            .procedure_match
        ),

        execution_eligible=(
            trusted_continuation
            .execution_eligible
        ),

        procedure_id=(
            state.procedure.id
        ),

        procedure_name=(
            state.procedure.name
        ),

        procedure_version=(
            state.procedure.version
        ),

        requested_step=(
            state.current_step
        ),

        affected_resource=(
            trusted_continuation
            .request_affected_resource
        ),

        incident_description=(
            trusted_continuation
            .incident_description
        ),
    )

    execution_identity = ExecutionIdentity(
        workflow_id=state.workflow_id,
        alert_id=state.alert_id,
        correlation_id=state.correlation_id,
    )

    operational_context = OperationalContext(
        alert_id=state.alert_id,

        affected_resource=(
            trusted_continuation
            .operational_affected_resource
        ),

        resource_type=(
            trusted_continuation
            .resource_type
        ),

        service=(
            trusted_continuation
            .service
        ),

        environment=(
            trusted_continuation
            .environment
        ),

        incident_origin=(
            trusted_continuation
            .incident_origin
        ),

        subscription_id=(
            trusted_continuation
            .subscription_id
        ),

        resource_group=(
            trusted_continuation
            .resource_group
        ),

        vm_name=(
            trusted_continuation
            .vm_name
        ),

        tenant_id=(
            trusted_continuation
            .tenant_id
        ),

        correlation_id=state.correlation_id,
    )

    return ProcedureExecutionInput(
        request=request,
        execution_identity=execution_identity,
        operational_context=operational_context,
    )
