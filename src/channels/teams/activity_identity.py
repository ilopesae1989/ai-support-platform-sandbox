from __future__ import annotations

from microsoft_teams.api import (
    AdaptiveCardInvokeActivity,
)

from .operator_identity import (
    TeamsOperatorIdentity,
)


class TeamsActivityIdentityError(
    ValueError
):
    """
    La actividad recibida no contiene una identidad
    Teams suficiente y confiable para procesar una
    decisión HITL.
    """

    pass


def extract_teams_operator_identity(
    activity: AdaptiveCardInvokeActivity,
) -> TeamsOperatorIdentity:
    """
    Extrae la identidad del operador exclusivamente
    de la actividad autenticada recibida por Teams.

    NUNCA utiliza:

        activity.value.action.data

    para determinar:

        tenant_id
        aad_object_id
        teams_user_id
        conversation_id
        display_name

    El payload Action.Execute pertenece a una frontera
    distinta y se considera controlable por el cliente.
    """

    if not isinstance(
        activity,
        AdaptiveCardInvokeActivity,
    ):
        raise TypeError(
            "activity debe ser "
            "AdaptiveCardInvokeActivity."
        )

    if (
        activity.channel_id
        != "msteams"
    ):
        raise TeamsActivityIdentityError(
            "La actividad HITL no procede del "
            "canal msteams."
        )

    sender = (
        activity.from_
    )

    if (
        sender.type is not None
        and sender.type != "person"
    ):
        raise TeamsActivityIdentityError(
            "La actividad HITL no procede de "
            "una identidad humana de Teams."
        )

    if (
        not sender.aad_object_id
        or not sender.aad_object_id.strip()
    ):
        raise TeamsActivityIdentityError(
            "La actividad Teams no contiene "
            "aad_object_id del operador."
        )

    if (
        not sender.id
        or not sender.id.strip()
    ):
        raise TeamsActivityIdentityError(
            "La actividad Teams no contiene "
            "teams_user_id del operador."
        )

    conversation = (
        activity.conversation
    )

    if (
        not conversation.id
        or not conversation.id.strip()
    ):
        raise TeamsActivityIdentityError(
            "La actividad Teams no contiene "
            "conversation_id."
        )

    channel_data = (
        activity.channel_data
    )

    if channel_data is None:
        raise TeamsActivityIdentityError(
            "La actividad Teams no contiene "
            "channel_data."
        )

    tenant = (
        channel_data.tenant
    )

    if (
        tenant is None
        or not tenant.id
        or not tenant.id.strip()
    ):
        raise TeamsActivityIdentityError(
            "La actividad Teams no contiene "
            "tenant_id autenticado."
        )

    return TeamsOperatorIdentity(
        tenant_id=(
            tenant.id
        ),

        aad_object_id=(
            sender.aad_object_id
        ),

        teams_user_id=(
            sender.id
        ),

        conversation_id=(
            conversation.id
        ),

        display_name=(
            sender.name
        ),
    )