from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
)

from .approval_channel import (
    ApprovalChannelAction,
    ApprovalDecision,
)

from .approval_store import (
    PendingApprovalStore,
)


class ApprovalResumeInstruction(
    BaseModel
):
    """
    Instrucción técnica necesaria para reanudar
    exactamente una solicitud HITL.

    No contiene autoridad operacional.

    Los valores:

        workflow_id
        request_id
        checkpoint_id

    proceden exclusivamente del PendingApprovalStore.

    El canal humano sólo puede proporcionar:

        approval_id
        decision
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    approval_id: str
    workflow_id: str

    request_id: str
    checkpoint_id: str

    approved: bool


def resolve_approval_channel_action(
    *,
    action: ApprovalChannelAction,
    store: PendingApprovalStore,
) -> ApprovalResumeInstruction:
    """
    Convierte una decisión mínima del canal en una
    instrucción técnica de reanudación.

    El canal NO puede proporcionar:

        workflow_id
        request_id
        checkpoint_id

    Esos valores se recuperan del store utilizando
    exclusivamente approval_id como clave exacta.

    Tampoco se reconstruye ninguna autoridad
    operacional.
    """

    if not isinstance(
        action,
        ApprovalChannelAction,
    ):
        raise TypeError(
            "action debe ser "
            "ApprovalChannelAction."
        )

    correlation = (
        store.get_by_approval_id(
            action.approval_id
        )
    )

    # Defensa explícita aunque el store ya realiza
    # lookup exacto.
    if (
        correlation.approval_id
        != action.approval_id
    ):
        raise RuntimeError(
            "La correlación recuperada no "
            "corresponde al approval_id solicitado."
        )

    if (
        action.decision
        == ApprovalDecision.APPROVE
    ):
        approved = True

    elif (
        action.decision
        == ApprovalDecision.REJECT
    ):
        approved = False

    else:
        # Normalmente imposible porque Pydantic +
        # Enum ya validan la entrada.
        #
        # Se conserva fail-closed como última defensa.
        raise ValueError(
            "Decisión HITL no soportada."
        )

    return ApprovalResumeInstruction(
        approval_id=(
            correlation.approval_id
        ),

        workflow_id=(
            correlation.workflow_id
        ),

        request_id=(
            correlation.request_id
        ),

        checkpoint_id=(
            correlation.checkpoint_id
        ),

        approved=(
            approved
        ),
    )