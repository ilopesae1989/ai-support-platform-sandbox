from __future__ import annotations

from src.communication.context import (
    SafeCommunicationContext,
)

from src.communication.contracts import (
    CommunicationRequest,
)

from src.runtime.procedure.models import (
    ApprovalStatus,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)


class CommunicationProjectionError(
    RuntimeError
):
    """
    El estado autoritativo no puede proyectarse
    de forma segura a comunicación humana.
    """

    pass


def _require_context(
    context: object,
) -> TriagedAlertContext:
    if type(context) is not TriagedAlertContext:
        raise TypeError(
            "context debe ser exactamente "
            "TriagedAlertContext."
        )

    return context


def _require_safe_context(
    context: object,
) -> SafeCommunicationContext:
    if type(context) is not SafeCommunicationContext:
        raise TypeError(
            "context debe ser exactamente "
            "SafeCommunicationContext."
        )

    return context


def _require_runtime_state(
    state: object,
) -> ProcedureRuntimeState:
    if type(state) is not ProcedureRuntimeState:
        raise TypeError(
            "state debe ser exactamente "
            "ProcedureRuntimeState."
        )

    return state


def _procedure_identity_from_context(
    context: TriagedAlertContext,
) -> tuple[
    str | None,
    str | None,
]:
    procedure = context.triage.procedure

    if procedure is None:
        return (
            None,
            None,
        )

    return (
        procedure.id,
        procedure.name,
    )


def _build_safe_request(
    *,
    context: TriagedAlertContext,
    event_type: str,
    status_summary: str,
    escalation_required: bool,
    escalation_team: str | None,
) -> CommunicationRequest:
    (
        procedure_id,
        procedure_name,
    ) = _procedure_identity_from_context(
        context
    )

    return CommunicationRequest(
        event_type=event_type,
        alert_id=context.alert.alert_id,
        technical_domain=(
            context.triage.technical_domain
        ),
        corporate_criticality=(
            context
            .triage
            .corporate_criticality
        ),
        affected_resource=(
            context.triage.affected_resource
        ),
        technical_summary=(
            context.triage.technical_summary
        ),
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        status_summary=status_summary,
        escalation_required=(
            escalation_required
        ),
        escalation_team=(
            escalation_team
        ),
    )


def build_incident_detected_communication_request(
    context: TriagedAlertContext,
) -> CommunicationRequest:
    """
    Proyecta únicamente la información comunicable
    ya gobernada por Triage.

    No utiliza OperationalContext, aprobación,
    capability, parámetros, target ni routing
    de canal.
    """

    trusted_context = _require_context(
        context
    )

    return _build_safe_request(
        context=trusted_context,
        event_type="incident_detected",
        status_summary=(
            "The governed triage identified "
            "an incident."
        ),
        escalation_required=(
            trusted_context
            .triage
            .escalation
            .required
        ),
        escalation_team=(
            trusted_context
            .triage
            .escalation
            .team
        ),
    )


def _validate_runtime_correlation(
    *,
    context: SafeCommunicationContext,
    state: ProcedureRuntimeState,
) -> None:
    if state.alert_id != context.alert_id:
        raise CommunicationProjectionError(
            "El runtime no corresponde "
            "a la alerta comunicada."
        )

    if (
        context.procedure_id is None
        or context.procedure_name is None
    ):
        raise CommunicationProjectionError(
            "El runtime de procedimiento requiere "
            "un procedimiento en el contexto "
            "seguro de comunicación."
        )

    if state.procedure.id != context.procedure_id:
        raise CommunicationProjectionError(
            "El procedimiento del runtime "
            "no corresponde al procedimiento "
            "del contexto seguro de comunicación."
        )

    if state.procedure.name != context.procedure_name:
        raise CommunicationProjectionError(
            "El nombre del procedimiento del runtime "
            "no corresponde al contexto seguro "
            "de comunicación."
        )


def _resolve_runtime_event(
    state: ProcedureRuntimeState,
) -> tuple[
    str,
    str,
]:
    if (
        state.approval_status
        == ApprovalStatus.REJECTED
        and state.step_status
        == StepStatus.REJECTED
        and state.workflow_status
        == WorkflowStatus.BLOCKED
    ):
        return (
            "operation_rejected",
            (
                "The operator rejected the "
                "requested operation."
            ),
        )

    if (
        state.workflow_status
        == WorkflowStatus.WAITING_VALIDATION
        and state.step_status
        == StepStatus.WAITING_VALIDATION
    ):
        return (
            "waiting_validation",
            (
                "The governed runtime is waiting "
                "for validation."
            ),
        )

    if (
        state.workflow_status
        == WorkflowStatus.RESOLVED
        and state.step_status
        == StepStatus.SUCCEEDED
    ):
        verification = (
            state.verification_result
        )

        if (
            verification is None
            or verification.success is not True
        ):
            raise CommunicationProjectionError(
                "RESOLVED requiere verificación "
                "positiva antes de comunicar "
                "resolución."
            )

        return (
            "resolved",
            (
                "The governed runtime reports "
                "the incident as resolved."
            ),
        )

    if (
        state.workflow_status
        == WorkflowStatus.ESCALATION_REQUIRED
        and state.step_status
        == StepStatus.FAILED
        and state.escalation_required is True
    ):
        return (
            "escalation_required",
            (
                "The governed runtime requires "
                "human escalation."
            ),
        )

    if (
        state.workflow_status
        == WorkflowStatus.BLOCKED
        and state.step_status
        == StepStatus.BLOCKED
    ):
        return (
            "blocked",
            (
                "The governed runtime blocked "
                "automatic resolution."
            ),
        )

    if (
        state.workflow_status
        == WorkflowStatus.FAILED
        and state.step_status
        == StepStatus.FAILED
    ):
        return (
            "failed",
            (
                "The governed runtime reports "
                "automatic resolution failed."
            ),
        )

    raise CommunicationProjectionError(
        "El estado autoritativo no corresponde "
        "a un evento comunicable soportado."
    )


def build_runtime_communication_request(
    *,
    context: SafeCommunicationContext,
    state: ProcedureRuntimeState,
) -> CommunicationRequest:
    """
    Convierte un estado autoritativo ya gobernado
    y su snapshot comunicable durable en una
    proyección exclusivamente comunicable.

    El LLM nunca recibe el ProcedureRuntimeState
    completo.

    Deliberadamente no se proyectan:
    - workflow_id;
    - correlation_id;
    - approval_id;
    - conversation_id;
    - operation_result;
    - operation_action;
    - capability_id;
    - target_resource operacional;
    - resolved_parameters;
    - retry/recheck authority;
    - identificadores de checkpoint;
    - evidencia MCP.
    """

    trusted_context = _require_safe_context(
        context
    )

    trusted_state = _require_runtime_state(
        state
    )

    _validate_runtime_correlation(
        context=trusted_context,
        state=trusted_state,
    )

    (
        event_type,
        status_summary,
    ) = _resolve_runtime_event(
        trusted_state
    )

    return CommunicationRequest(
        event_type=event_type,
        alert_id=trusted_context.alert_id,
        technical_domain=(
            trusted_context.technical_domain
        ),
        corporate_criticality=(
            trusted_context.corporate_criticality
        ),
        affected_resource=(
            trusted_context.affected_resource
        ),
        technical_summary=(
            trusted_context.technical_summary
        ),
        procedure_id=(
            trusted_context.procedure_id
        ),
        procedure_name=(
            trusted_context.procedure_name
        ),
        status_summary=status_summary,
        escalation_required=(
            trusted_state.escalation_required
        ),
        escalation_team=(
            trusted_state.escalation_team
        ),
    )