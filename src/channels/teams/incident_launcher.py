from __future__ import annotations

from collections.abc import (
    Callable,
)

from typing import (
    Any,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from .incident_workflow_host import (
    run_incident_until_teams_approval,
)


async def start_teams_incident_from_normalized_alert(
    *,
    alert: NormalizedAlert,
    workflow_factory: Callable[[], Any],
    checkpoint_storage: Any,
    store: Any,
    outbound: Any,
    tenant_id: str,
    conversation_id: str,
):
    """
    Inicia el workflow Teams desde una alerta que
    ya ha atravesado una frontera de normalización
    autoritativa.

    Este launcher NO:

    - interpreta payloads Azure Monitor;
    - normaliza JSON;
    - lee correo;
    - interpreta mensajes Teams;
    - obtiene tenant/conversation desde la alerta;
    - concede autoridad operacional;
    - ejecuta Azure directamente.

    Teams continúa siendo únicamente el canal de
    transporte y aprobación.
    """

    if not isinstance(
        alert,
        NormalizedAlert,
    ):
        raise TypeError(
            "alert debe ser NormalizedAlert."
        )

    if not callable(
        workflow_factory
    ):
        raise TypeError(
            "workflow_factory debe ser callable."
        )

    workflow = (
        workflow_factory()
    )

    return await (
        run_incident_until_teams_approval(
            workflow=workflow,
            alert=alert,
            checkpoint_storage=(
                checkpoint_storage
            ),
            store=store,
            outbound=outbound,
            tenant_id=tenant_id,
            conversation_id=(
                conversation_id
            ),
        )
    )
