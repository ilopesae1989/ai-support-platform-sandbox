from __future__ import annotations

from typing import (
    Any,
)

from .approval_bridge import (
    notify_registered_teams_approval,
    register_pending_approval_correlation,
)

from src.workflows.incident_resolution.workflow_input import (
    IncidentWorkflowInput,
)


class IncidentWorkflowHostError(
    RuntimeError
):
    """
    Error fail-closed del host application-level
    que conecta el workflow de incidente con Teams.

    No concede autoridad operacional.
    """

    pass


def _require_exact_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
        or value
        != value.strip()
    ):
        raise IncidentWorkflowHostError(
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


async def run_incident_until_teams_approval(
    *,
    workflow: Any,
    alert: Any,
    checkpoint_storage: Any,
    store: Any,
    outbound: Any,
    tenant_id: str,
    conversation_id: str,
):
    """
    Ejecuta un incidente exclusivamente hasta su
    frontera HITL y publica la aprobación en Teams.

    Orden obligatorio:

        incident workflow
            ↓
        RequestInfoEvent
            ↓
        finalizar ejecución suspendida
            ↓
        listar checkpoints
            ↓
        correlacionar request_id exacto
            ↓
        registrar correlación durable
            ↓
        notificar Teams

    Esta función NO:

    - responde al HITL;
    - aprueba ni rechaza;
    - reanuda el workflow;
    - ejecuta Azure directamente;
    - reconstruye autoridad desde Teams.
    """

    tenant_id = _require_exact_string(
        name="tenant_id",
        value=tenant_id,
    )

    conversation_id = _require_exact_string(
        name="conversation_id",
        value=conversation_id,
    )

    workflow_name = _require_exact_string(
        name="workflow.name",
        value=getattr(
            workflow,
            "name",
            None,
        ),
    )

    pending_requests = []

    #
    # El stream se consume COMPLETO.
    #
    # No buscamos checkpoints dentro del
    # async-for porque Agent Framework crea
    # checkpoints al terminar el superstep.
    #
    workflow_input = (
        IncidentWorkflowInput(
            alert=alert,
            conversation_id=(
                conversation_id
            ),
        )
    )

    async for event in workflow.run(
        workflow_input,
        stream=True,
        checkpoint_storage=(
            checkpoint_storage
        ),
    ):
        if (
            getattr(
                event,
                "type",
                None,
            )
            == "request_info"
        ):
            pending_requests.append(
                event
            )

    if len(
        pending_requests
    ) != 1:
        raise IncidentWorkflowHostError(
            "El workflow debe producir "
            "exactamente una solicitud HITL. "
            f"Actual={len(pending_requests)}."
        )

    request_event = (
        pending_requests[0]
    )

    request_id = _require_exact_string(
        name="request_id",
        value=getattr(
            request_event,
            "request_id",
            None,
        ),
    )

    request = getattr(
        request_event,
        "data",
        None,
    )

    list_checkpoints = getattr(
        checkpoint_storage,
        "list_checkpoints",
        None,
    )

    if not callable(
        list_checkpoints
    ):
        raise IncidentWorkflowHostError(
            "checkpoint_storage debe exponer "
            "list_checkpoints callable."
        )

    checkpoints = await list_checkpoints(
        workflow_name=(
            workflow_name
        )
    )

    #
    # Primero persistencia.
    #
    register_pending_approval_correlation(
        request=request,
        request_id=request_id,
        checkpoints=checkpoints,
        store=store,
    )

    #
    # Sólo después puede existir transporte.
    #
    return await (
        notify_registered_teams_approval(
            request=request,
            request_id=request_id,
            store=store,
            outbound=outbound,
            tenant_id=tenant_id,
            conversation_id=(
                conversation_id
            ),
        )
    )
