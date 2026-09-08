from __future__ import annotations

from .context import SafeCommunicationContext


SAFE_COMMUNICATION_CONTEXT_STATE_KEY = (
    "safe_communication_context"
)


def store_safe_communication_context(
    ctx: object,
    context: SafeCommunicationContext,
) -> None:
    if type(context) is not SafeCommunicationContext:
        raise TypeError(
            "context debe ser exactamente "
            "SafeCommunicationContext."
        )

    payload = context.model_dump(
        mode="json"
    )

    ctx.set_state(
        SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
        payload,
    )


def load_safe_communication_context(
    ctx: object,
) -> SafeCommunicationContext | None:
    payload = ctx.get_state(
        SAFE_COMMUNICATION_CONTEXT_STATE_KEY,
        None,
    )

    if payload is None:
        return None

    return SafeCommunicationContext.model_validate(
        payload
    )