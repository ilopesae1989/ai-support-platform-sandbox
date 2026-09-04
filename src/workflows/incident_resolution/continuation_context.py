from __future__ import annotations

from agent_framework import (
    WorkflowContext,
)

from pydantic import (
    BaseModel,
    ConfigDict,
)

from src.workflows.incident_resolution.alert_models import (
    IncidentOrigin,
)


PROCEDURE_CONTINUATION_CONTEXT_STATE_KEY = (
    "procedure_continuation_context"
)


class ProcedureContinuationContext(BaseModel):
    """
    Contexto mínimo durable necesario para preparar
    un ProcedureExecutionInput posterior.

    No contiene autoridad ya poseída por
    ProcedureRuntimeState:

    - workflow_id;
    - alert_id;
    - correlation_id;
    - procedure identity;
    - cursor;
    - step;
    - approval;
    - operation result;
    - verification result.

    Sólo conserva contexto base que no puede
    reconstruirse desde ProcedureRuntimeState.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    request_affected_resource: str
    incident_description: str

    operational_affected_resource: str | None = None
    resource_type: str | None = None
    service: str | None = None
    environment: str | None = None

    incident_origin: IncidentOrigin = "observed"

    subscription_id: str | None = None
    resource_group: str | None = None
    vm_name: str | None = None
    tenant_id: str | None = None


def store_procedure_continuation_context(
    ctx: WorkflowContext,
    context: ProcedureContinuationContext,
) -> None:
    """
    Guarda únicamente payload JSON-native.

    El checkpoint del workflow es responsable de
    durabilizar shared state.
    """

    payload = context.model_dump(
        mode="json"
    )

    ctx.set_state(
        PROCEDURE_CONTINUATION_CONTEXT_STATE_KEY,
        payload,
    )


def load_procedure_continuation_context(
    ctx: WorkflowContext,
) -> ProcedureContinuationContext | None:
    """
    Rehidrata el contexto durable.

    None mantiene compatibilidad con checkpoints
    históricos anteriores a FASE 22.4.

    Un payload existente pero inválido falla cerrado
    mediante validación Pydantic.
    """

    payload = ctx.get_state(
        PROCEDURE_CONTINUATION_CONTEXT_STATE_KEY,
        None,
    )

    if payload is None:
        return None

    return (
        ProcedureContinuationContext
        .model_validate(
            payload
        )
    )
