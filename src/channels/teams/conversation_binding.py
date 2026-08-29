from __future__ import annotations

from dataclasses import (
    dataclass,
)

from microsoft_teams.api import (
    MessageActivity,
)


class TeamsConversationBindingError(
    ValueError
):
    """
    La actividad Teams no contiene suficiente
    contexto de transporte confiable para registrar
    una conversación.
    """

    pass


@dataclass(
    frozen=True
)
class TeamsConversationBinding:
    """
    Binding mínimo de transporte Teams.

    Contiene exclusivamente información necesaria
    para volver a localizar una conversación.

    NO contiene:

        workflow_id
        procedure_id
        capability_id
        operation
        target_resource
        parameters
        approval decision

    Por tanto no constituye autoridad operacional.
    """

    tenant_id: str

    conversation_id: str

    service_url: str


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
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise TeamsConversationBindingError(
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


def build_teams_conversation_binding(
    activity: MessageActivity,
) -> TeamsConversationBinding:
    """
    Construye un binding exclusivamente desde
    metadatos de una MessageActivity autenticada
    recibida por el runtime Teams.

    El texto y cualquier payload controlable por
    el usuario se ignoran completamente.
    """

    if not isinstance(
        activity,
        MessageActivity,
    ):
        raise TypeError(
            "activity debe ser MessageActivity."
        )

    if (
        activity.channel_id
        != "msteams"
    ):
        raise TeamsConversationBindingError(
            "La actividad no procede del canal "
            "msteams."
        )

    sender = (
        activity.from_
    )

    if (
        sender.type is not None
        and sender.type != "person"
    ):
        raise TeamsConversationBindingError(
            "La actividad no procede de una "
            "identidad humana de Teams."
        )

    conversation = (
        activity.conversation
    )

    conversation_id = (
        _require_exact_string(
            name="conversation_id",
            value=conversation.id,
        )
    )

    conversation_tenant_id = None

    if conversation.tenant_id is not None:
        conversation_tenant_id = (
            _require_exact_string(
                name="conversation_tenant_id",
                value=conversation.tenant_id,
            )
        )

    channel_tenant_id = None

    channel_data = (
        activity.channel_data
    )

    if channel_data is not None:
        tenant = (
            channel_data.tenant
        )

        if tenant is not None:
            channel_tenant_id = (
                _require_exact_string(
                    name="channel_tenant_id",
                    value=tenant.id,
                )
            )

    if (
        conversation_tenant_id is None
        and channel_tenant_id is None
    ):
        raise TeamsConversationBindingError(
            "La actividad Teams no contiene "
            "tenant autenticado."
        )

    if (
        conversation_tenant_id is not None
        and channel_tenant_id is not None
        and conversation_tenant_id
        != channel_tenant_id
    ):
        raise TeamsConversationBindingError(
            "Las fuentes autenticadas de tenant "
            "no coinciden."
        )

    tenant_id = (
        conversation_tenant_id
        if conversation_tenant_id is not None
        else channel_tenant_id
    )

    service_url = (
        _require_exact_string(
            name="service_url",
            value=activity.service_url,
        )
    )

    return TeamsConversationBinding(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        service_url=service_url,
    )
