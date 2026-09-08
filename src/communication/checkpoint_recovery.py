from __future__ import annotations

from pydantic import ValidationError

from .context import SafeCommunicationContext
from .context_state import (
    SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
)


class CommunicationCheckpointRecoveryError(
    RuntimeError
):
    """
    Fallo fail-closed al recuperar el snapshot
    comunicable desde un checkpoint exacto.
    """

    pass


def _require_exact_text(
    value: object,
    *,
    field_name: str,
) -> str:
    if (
        type(value) is not str
        or not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{field_name} debe ser un string "
            "no vacío y exacto."
        )

    return value


async def recover_safe_communication_context_from_checkpoint(
    *,
    checkpoint_storage: object,
    workflow_name: str,
    checkpoint_id: str,
) -> SafeCommunicationContext:
    list_checkpoints = getattr(
        checkpoint_storage,
        "list_checkpoints",
        None,
    )

    if not callable(list_checkpoints):
        raise TypeError(
            "checkpoint_storage debe implementar "
            "list_checkpoints."
        )

    trusted_workflow_name = _require_exact_text(
        workflow_name,
        field_name="workflow_name",
    )

    trusted_checkpoint_id = _require_exact_text(
        checkpoint_id,
        field_name="checkpoint_id",
    )

    checkpoints = await list_checkpoints(
        workflow_name=trusted_workflow_name
    )

    matches = [
        checkpoint
        for checkpoint in checkpoints
        if (
            getattr(
                checkpoint,
                "checkpoint_id",
                None,
            )
            == trusted_checkpoint_id
        )
    ]

    if len(matches) != 1:
        raise CommunicationCheckpointRecoveryError(
            "La identidad exacta del checkpoint "
            "no produce un único resultado."
        )

    checkpoint = matches[0]

    state = getattr(
        checkpoint,
        "state",
        None,
    )

    if type(state) is not dict:
        raise CommunicationCheckpointRecoveryError(
            "El checkpoint exacto no contiene "
            "un estado válido."
        )

    if (
        SAFE_COMMUNICATION_CONTEXT_STATE_KEY
        not in state
    ):
        raise CommunicationCheckpointRecoveryError(
            "El checkpoint exacto no contiene "
            "el snapshot seguro de comunicación."
        )

    payload = state[
        SAFE_COMMUNICATION_CONTEXT_STATE_KEY
    ]

    try:
        return SafeCommunicationContext.model_validate(
            payload
        )
    except ValidationError as exc:
        raise CommunicationCheckpointRecoveryError(
            "El snapshot seguro del checkpoint "
            "no supera validación estricta."
        ) from exc