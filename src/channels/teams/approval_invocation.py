from __future__ import annotations

from microsoft_teams.api import (
    AdaptiveCardInvokeActivity,
)

from pydantic import (
    BaseModel,
    ConfigDict,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
)

from .action_parser import (
    parse_teams_approval_action,
)

from .activity_identity import (
    extract_teams_operator_identity,
)

from .operator_identity import (
    TeamsOperatorIdentity,
)


class TeamsApprovalInvocation(
    BaseModel
):
    """
    Entrada limpia al backend HITL procedente
    de Microsoft Teams.

    Une dos fronteras distintas:

        operator
            identidad obtenida exclusivamente
            de la Activity autenticada.

        action
            decisión mínima obtenida exclusivamente
            de Action.Execute.data.

    No contiene autoridad operacional.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    operator: TeamsOperatorIdentity

    action: ApprovalChannelAction


def build_teams_approval_invocation(
    activity: AdaptiveCardInvokeActivity,
) -> TeamsApprovalInvocation:
    """
    Construye una invocación HITL Teams a partir
    de una única Activity autenticada.

    La identidad del operador y la decisión humana
    se extraen por rutas independientes.

    Nunca se permite que Action.Execute.data
    sustituya identidad autenticada de Teams.
    """

    if not isinstance(
        activity,
        AdaptiveCardInvokeActivity,
    ):
        raise TypeError(
            "activity debe ser "
            "AdaptiveCardInvokeActivity."
        )

    operator = (
        extract_teams_operator_identity(
            activity
        )
    )

    action = (
        parse_teams_approval_action(
            activity
        )
    )

    return TeamsApprovalInvocation(
        operator=operator,
        action=action,
    )