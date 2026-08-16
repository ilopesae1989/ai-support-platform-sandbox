from __future__ import annotations

from src.runtime.procedure.workflow import (
    ApprovalRequest,
)

from .approval_card import (
    build_teams_approval_card,
)

from .outbound_adapter import (
    TeamsOutboundDependencies,
    send_teams_adaptive_card,
)


class TeamsApprovalNotificationError(
    ValueError
):
    """
    Error de correlación al intentar presentar
    una aprobación gobernada en Microsoft Teams.

    Este error debe producir fail-closed:
    ninguna tarjeta debe enviarse.
    """

    pass


def _require_request_conversation_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise TeamsApprovalNotificationError(
            "ApprovalRequest requiere "
            "conversation_id exacto no vacío."
        )

    return value


def _require_transport_conversation_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise TeamsApprovalNotificationError(
            "conversation_id de transporte debe "
            "ser un string exacto no vacío."
        )

    return value


async def notify_teams_approval(
    *,
    request: ApprovalRequest,
    outbound: TeamsOutboundDependencies,
    tenant_id: str,
    conversation_id: str,
):
    """
    Presenta en Teams una ApprovalRequest
    previamente construida por el workflow.

    Esta función:

        ApprovalRequest
            ↓
        correlación conversation_id
            ↓
        AdaptiveCard
            ↓
        TeamsOutboundAdapter

    No:

    - crea approval_id;
    - registra correlaciones HITL;
    - modifica el checkpoint;
    - decide aprobación;
    - concede capacidades;
    - modifica parámetros;
    - deriva el destino desde el contenido
      de la tarjeta.

    El conversation_id almacenado en la
    ApprovalRequest debe coincidir exactamente
    con el conversation_id explícito utilizado
    por el transporte.
    """

    if not isinstance(
        request,
        ApprovalRequest,
    ):
        raise TypeError(
            "request debe ser "
            "ApprovalRequest."
        )

    if not isinstance(
        outbound,
        TeamsOutboundDependencies,
    ):
        raise TypeError(
            "outbound debe ser "
            "TeamsOutboundDependencies."
        )

    request_conversation_id = (
        _require_request_conversation_id(
            request.conversation_id
        )
    )

    transport_conversation_id = (
        _require_transport_conversation_id(
            conversation_id
        )
    )

    if (
        request_conversation_id
        != transport_conversation_id
    ):
        raise TeamsApprovalNotificationError(
            "ApprovalRequest pertenece a una "
            "conversation_id distinta del "
            "destino de transporte."
        )

    card = (
        build_teams_approval_card(
            request
        )
    )

    return await send_teams_adaptive_card(
        dependencies=outbound,
        tenant_id=tenant_id,
        conversation_id=(
            transport_conversation_id
        ),
        card=card,
    )
