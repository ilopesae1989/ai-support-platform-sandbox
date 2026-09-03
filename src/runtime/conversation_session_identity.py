from __future__ import annotations

import hashlib

from dataclasses import dataclass


def _require_exact_string(
    *,
    name: str,
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} debe ser str."
        )

    if (
        not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} debe ser un string exacto no vacío."
        )

    return value


@dataclass(
    frozen=True
)
class ConversationSessionIdentity:
    tenant_id: str
    conversation_id: str
    agent_key: str

    def __post_init__(
        self,
    ) -> None:
        _require_exact_string(
            name="tenant_id",
            value=self.tenant_id,
        )

        _require_exact_string(
            name="conversation_id",
            value=self.conversation_id,
        )

        _require_exact_string(
            name="agent_key",
            value=self.agent_key,
        )


def _encode_component(
    value: str,
) -> bytes:
    encoded = value.encode(
        "utf-8"
    )

    return (
        len(encoded).to_bytes(
            8,
            byteorder="big",
            signed=False,
        )
        + encoded
    )


def build_conversation_session_store_id(
    identity,
) -> str:
    if not isinstance(
        identity,
        ConversationSessionIdentity,
    ):
        raise TypeError(
            "identity debe ser "
            "ConversationSessionIdentity."
        )

    canonical = (
        b"conversation-session:v1"
        + _encode_component(
            identity.tenant_id
        )
        + _encode_component(
            identity.conversation_id
        )
        + _encode_component(
            identity.agent_key
        )
    )

    digest = hashlib.sha256(
        canonical
    ).hexdigest()

    return "cs1:" + digest
