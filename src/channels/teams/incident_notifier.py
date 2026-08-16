from __future__ import annotations

from src.workflows.incident_resolution.models import (
    TriagedAlertContext,
)

from .incident_notification import (
    build_teams_incident_notification,
    render_teams_incident_notification,
)

from .outbound_adapter import (
    TeamsOutboundDependencies,
    send_teams_message,
)


async def notify_teams_incident(
    *,
    context: TriagedAlertContext,
    outbound: TeamsOutboundDependencies,
    tenant_id: str,
    conversation_id: str,
):
    """
    Publica en Microsoft Teams un incidente ya
    gobernado y tipado por el core.

    Responsabilidades:

        TriagedAlertContext
            ↓
        TeamsIncidentNotification
            ↓
        renderer informativo
            ↓
        TeamsOutboundAdapter

    El notifier NO:

    - clasifica alertas;
    - decide criticidad;
    - selecciona procedimientos;
    - concede capacidades;
    - interpreta parámetros operacionales;
    - selecciona destinatarios desde el texto;
    - reconstruye autoridad desde Teams.

    tenant_id y conversation_id son referencias
    explícitas de transporte y se validan de nuevo
    en TeamsOutboundAdapter mediante lookup exacto.
    """

    if not isinstance(
        context,
        TriagedAlertContext,
    ):
        raise TypeError(
            "context debe ser "
            "TriagedAlertContext."
        )

    if not isinstance(
        outbound,
        TeamsOutboundDependencies,
    ):
        raise TypeError(
            "outbound debe ser "
            "TeamsOutboundDependencies."
        )

    notification = (
        build_teams_incident_notification(
            context
        )
    )

    message = (
        render_teams_incident_notification(
            notification
        )
    )

    return await send_teams_message(
        dependencies=outbound,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        text=message,
    )
