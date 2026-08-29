from collections.abc import (
    Iterable,
    Mapping,
)
from typing import (
    Any,
)


class TeamsApprovalBridgeError(
    RuntimeError
):
    """
    Error fail-closed del bridge HITL hacia Teams.
    """

    pass


def resolve_pending_approval_checkpoint(
    *,
    checkpoints: Iterable[Any],
    request_id: str,
):
    """
    Resuelve el Ãºnico checkpoint que contiene
    exactamente el RequestInfoEvent pendiente
    indicado.

    No usa:

    - timestamp;
    - orden;
    - latest checkpoint;
    - fuzzy matching;
    - fallback.

    Debe existir exactamente una coincidencia.
    """

    if (
        not isinstance(
            request_id,
            str,
        )
        or not request_id.strip()
        or request_id
        != request_id.strip()
    ):
        raise TeamsApprovalBridgeError(
            "request_id debe ser un string "
            "exacto no vacÃ­o y sin espacios "
            "laterales."
        )

    try:
        checkpoint_list = list(
            checkpoints
        )
    except TypeError as exc:
        raise TeamsApprovalBridgeError(
            "checkpoints debe ser iterable."
        ) from exc

    matches = []

    for checkpoint in checkpoint_list:
        pending = getattr(
            checkpoint,
            "pending_request_info_events",
            None,
        )

        if not isinstance(
            pending,
            Mapping,
        ):
            raise TeamsApprovalBridgeError(
                "El checkpoint no contiene "
                "pending_request_info_events "
                "con el contrato esperado."
            )

        if request_id in pending:
            matches.append(
                checkpoint
            )

    if len(matches) != 1:
        raise TeamsApprovalBridgeError(
            "Debe existir exactamente un "
            "checkpoint pendiente para "
            f"request_id={request_id!r}. "
            f"matches={len(matches)}."
        )

    checkpoint = matches[0]

    checkpoint_id = getattr(
        checkpoint,
        "checkpoint_id",
        None,
    )

    if (
        not isinstance(
            checkpoint_id,
            str,
        )
        or not checkpoint_id.strip()
        or checkpoint_id
        != checkpoint_id.strip()
    ):
        raise TeamsApprovalBridgeError(
            "El checkpoint correlacionado "
            "no contiene checkpoint_id "
            "exacto vÃ¡lido."
        )

    return checkpoint

from src.runtime.procedure.approval_correlation import (
    build_pending_approval_correlation,
)


def register_pending_approval_correlation(
    *,
    request: Any,
    request_id: str,
    checkpoints: Iterable[Any],
    store: Any,
):
    """
    Registra la correlación durable de una
    solicitud HITL usando exclusivamente el
    checkpoint que contiene el request_id exacto.

    No selecciona checkpoints por:

    - timestamp;
    - orden;
    - latest;
    - fallback.

    No envía nada al canal.
    """

    checkpoint = (
        resolve_pending_approval_checkpoint(
            checkpoints=checkpoints,
            request_id=request_id,
        )
    )

    register = getattr(
        store,
        "register",
        None,
    )

    if not callable(register):
        raise TeamsApprovalBridgeError(
            "store debe exponer un método "
            "register callable."
        )

    correlation = (
        build_pending_approval_correlation(
            request=request,
            request_id=request_id,
            checkpoint_id=(
                checkpoint.checkpoint_id
            ),
        )
    )

    register(
        correlation
    )

    return correlation

from src.channels.teams.approval_notifier import (
    notify_teams_approval,
)


async def notify_registered_teams_approval(
    *,
    request: Any,
    request_id: str,
    store: Any,
    outbound: Any,
    tenant_id: str,
    conversation_id: str,
):
    """
    Publica una aprobación en Teams sólo después
    de verificar una correlación HITL ya durable.

    Esta función NO registra correlaciones.

    Puede reintentarse tras un fallo de transporte:
    cada intento vuelve a verificar exactamente la
    misma correlación persistida antes de enviar.
    """

    if (
        not isinstance(
            request_id,
            str,
        )
        or not request_id.strip()
        or request_id
        != request_id.strip()
    ):
        raise TeamsApprovalBridgeError(
            "request_id debe ser un string "
            "exacto no vacío y sin espacios "
            "laterales."
        )

    get_by_approval_id = getattr(
        store,
        "get_by_approval_id",
        None,
    )

    if not callable(
        get_by_approval_id
    ):
        raise TeamsApprovalBridgeError(
            "store debe exponer "
            "get_by_approval_id callable."
        )

    approval_id = getattr(
        request,
        "approval_id",
        None,
    )

    workflow_id = getattr(
        request,
        "workflow_id",
        None,
    )

    if (
        not isinstance(
            approval_id,
            str,
        )
        or not approval_id.strip()
        or approval_id
        != approval_id.strip()
    ):
        raise TeamsApprovalBridgeError(
            "request no contiene approval_id "
            "exacto válido."
        )

    if (
        not isinstance(
            workflow_id,
            str,
        )
        or not workflow_id.strip()
        or workflow_id
        != workflow_id.strip()
    ):
        raise TeamsApprovalBridgeError(
            "request no contiene workflow_id "
            "exacto válido."
        )

    correlation = get_by_approval_id(
        approval_id
    )

    if (
        getattr(
            correlation,
            "approval_id",
            None,
        )
        != approval_id
    ):
        raise TeamsApprovalBridgeError(
            "approval_id registrado no coincide "
            "exactamente con ApprovalRequest."
        )

    if (
        getattr(
            correlation,
            "workflow_id",
            None,
        )
        != workflow_id
    ):
        raise TeamsApprovalBridgeError(
            "workflow_id registrado no coincide "
            "exactamente con ApprovalRequest."
        )

    if (
        getattr(
            correlation,
            "request_id",
            None,
        )
        != request_id
    ):
        raise TeamsApprovalBridgeError(
            "request_id registrado no coincide "
            "exactamente con RequestInfoEvent."
        )

    return await notify_teams_approval(
        request=request,
        outbound=outbound,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )
