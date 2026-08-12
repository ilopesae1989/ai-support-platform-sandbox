from __future__ import annotations

from typing import (
    Literal,
)

from microsoft_teams.api import (
    AdaptiveCardInvokeActivity,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)


class TeamsApprovalActionError(
    ValueError
):
    """
    La acción recibida desde Teams no cumple
    el contrato mínimo permitido para HITL.
    """

    pass


class TeamsApprovalActionPayload(
    BaseModel
):
    """
    Datos exactos permitidos dentro de:

        activity.value.action.data

    La clave "action" sirve exclusivamente para
    routing del handler Teams.

    La autoridad HITL que llega al core sigue
    reducida a:

        approval_id
        decision

    Cualquier campo adicional provoca rechazo.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    action: Literal[
        "approval_decision"
    ]

    approval_id: str

    decision: ApprovalDecision


def parse_teams_approval_action(
    activity: AdaptiveCardInvokeActivity,
) -> ApprovalChannelAction:
    """
    Convierte un Action.Execute real de Teams
    en el contrato mínimo independiente del canal.

    Validaciones:

    - actividad AdaptiveCardInvokeActivity;
    - invoke name = adaptiveCard/action;
    - action type = Action.Execute;
    - routing action = approval_decision;
    - sólo approval_id + decision como datos HITL;
    - ningún campo operacional adicional.

    No extrae identidad del operador.

    Esa responsabilidad pertenece exclusivamente
    a extract_teams_operator_identity().
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
        activity.name
        != "adaptiveCard/action"
    ):
        raise TeamsApprovalActionError(
            "La actividad no es "
            "adaptiveCard/action."
        )

    if (
        activity.value is None
        or activity.value.action is None
    ):
        raise TeamsApprovalActionError(
            "La actividad Teams no contiene "
            "una acción Adaptive Card."
        )

    invoke_action = (
        activity.value.action
    )

    if (
        invoke_action.type
        != "Action.Execute"
    ):
        raise TeamsApprovalActionError(
            "La acción HITL debe ser "
            "Action.Execute."
        )

    data = (
        invoke_action.data
    )

    if not isinstance(
        data,
        dict,
    ):
        raise TeamsApprovalActionError(
            "Action.Execute.data debe ser "
            "un objeto."
        )

    try:
        payload = (
            TeamsApprovalActionPayload
            .model_validate(
                data
            )
        )

        return ApprovalChannelAction(
            approval_id=(
                payload.approval_id
            ),

            decision=(
                payload.decision
            ),
        )

    except ValidationError as exc:
        raise TeamsApprovalActionError(
            "El payload Action.Execute no cumple "
            "el contrato HITL permitido."
        ) from exc