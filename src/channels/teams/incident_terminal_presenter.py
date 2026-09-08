from __future__ import annotations

from typing import Any

from src.runtime.procedure.models import (
    ApprovalStatus,
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.communication.context import (
    SafeCommunicationContext,
)

from src.communication.contracts import (
    CommunicationResult,
)

from src.communication.projection import (
    build_runtime_communication_request,
)

from .approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from .outbound_adapter import (
    TeamsOutboundDependencies,
    send_teams_message,
)


class IncidentTerminalPresentationError(
    RuntimeError
):
    """
    Resultado terminal no representable de forma
    segura para el canal Teams.
    """

    pass


def render_incident_terminal_result(
    state: ProcedureRuntimeState,
) -> str:
    """
    Render exclusivamente informativo.

    No concede autoridad.

    No utiliza:
    - resolved_parameters;
    - target_resource;
    - capability_id;
    - operation_action;
    - parámetros Azure/MCP.

    El mensaje procede exclusivamente de un
    ProcedureRuntimeState terminal gobernado.
    """

    if not isinstance(
        state,
        ProcedureRuntimeState,
    ):
        raise TypeError(
            "state debe ser ProcedureRuntimeState."
        )

    procedure = state.procedure

    if (
        state.approval_status
        == ApprovalStatus.REJECTED
    ):
        return (
            "⛔ Operación rechazada.\n"
            "No se ha ejecutado la acción solicitada.\n"
            f"Procedimiento: {procedure.id} - "
            f"{procedure.name}"
        )

    if (
        state.workflow_status
        == WorkflowStatus.RESOLVED
    ):
        if (
            state.step_status
            != StepStatus.SUCCEEDED
        ):
            raise IncidentTerminalPresentationError(
                "workflow resolved requiere "
                "step_status=succeeded."
            )

        verification = (
            state.verification_result
        )

        if (
            verification is None
            or verification.success is not True
        ):
            raise IncidentTerminalPresentationError(
                "workflow resolved requiere "
                "verificación positiva."
            )

        return (
            "✅ Incidencia resuelta.\n"
            "La operación autorizada terminó y "
            "la validación posterior confirmó "
            "el resultado esperado.\n"
            f"Procedimiento: {procedure.id} - "
            f"{procedure.name}"
        )

    if (
        state.workflow_status
        == WorkflowStatus.ESCALATION_REQUIRED
        or state.escalation_required
    ):
        message = (
            "⚠️ La incidencia requiere escalado.\n"
            f"Procedimiento: {procedure.id} - "
            f"{procedure.name}"
        )

        if state.escalation_team:
            message += (
                "\nEquipo de escalado: "
                f"{state.escalation_team}"
            )

        return message

    if (
        state.workflow_status
        in {
            WorkflowStatus.BLOCKED,
            WorkflowStatus.FAILED,
        }
    ):
        return (
            "❌ La incidencia no pudo resolverse "
            "automáticamente.\n"
            "No se realizará ningún reintento "
            "operacional automático.\n"
            f"Procedimiento: {procedure.id} - "
            f"{procedure.name}"
        )

    raise IncidentTerminalPresentationError(
        "El workflow_result no está en un "
        "estado terminal soportado."
    )


def _render_communication_result(
    result: CommunicationResult,
) -> str:
    if type(result) is not CommunicationResult:
        raise IncidentTerminalPresentationError(
            "Communication runner no devolvió "
            "CommunicationResult exacto."
        )

    lines = [
        result.headline,
        result.summary,
    ]

    lines.extend(
        f"- {detail}"
        for detail in result.details
    )

    return "\n".join(
        lines
    )


async def notify_teams_incident_terminal_result(
    *,
    invocation: AuthorizedTeamsApprovalInvocation,
    processed: Any,
    outbound: TeamsOutboundDependencies,
    communication_runner: Any | None = None,
):
    """
    Publica el resultado terminal gobernado.

    El destino procede exclusivamente de la
    identidad Teams autenticada y autorizada.

    Communication es exclusivamente presentación:
    Python proyecta primero el estado gobernado.

    Si falla únicamente la capa cognitiva se usa
    el renderer determinista existente.
    """

    if not isinstance(
        invocation,
        AuthorizedTeamsApprovalInvocation,
    ):
        raise TypeError(
            "invocation debe ser "
            "AuthorizedTeamsApprovalInvocation."
        )

    workflow_result = getattr(
        processed,
        "workflow_result",
        None,
    )

    if not isinstance(
        workflow_result,
        ProcedureRuntimeState,
    ):
        raise IncidentTerminalPresentationError(
            "processed no contiene un "
            "ProcedureRuntimeState terminal."
        )

    result_conversation_id = (
        workflow_result.conversation_id
    )

    if (
        result_conversation_id is not None
        and result_conversation_id
        != invocation.operator.conversation_id
    ):
        raise IncidentTerminalPresentationError(
            "conversation_id terminal no coincide "
            "con la identidad Teams autorizada."
        )

    if communication_runner is None:
        text = render_incident_terminal_result(
            workflow_result
        )

    else:
        safe_communication_context = getattr(
            processed,
            "safe_communication_context",
            None,
        )

        if type(
            safe_communication_context
        ) is not SafeCommunicationContext:
            raise IncidentTerminalPresentationError(
                "processed no contiene "
                "SafeCommunicationContext exacto."
            )

        communication_request = (
            build_runtime_communication_request(
                context=(
                    safe_communication_context
                ),
                state=workflow_result,
            )
        )

        try:
            communication_result = await (
                communication_runner(
                    communication_request
                )
            )

            text = _render_communication_result(
                communication_result
            )

        except Exception:
            text = render_incident_terminal_result(
                workflow_result
            )

    return await send_teams_message(
        dependencies=outbound,
        tenant_id=invocation.operator.tenant_id,
        conversation_id=invocation.operator.conversation_id,
        text=text,
    )