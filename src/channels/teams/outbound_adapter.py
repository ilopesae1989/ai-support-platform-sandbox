from __future__ import annotations

from dataclasses import (
    dataclass,
)

from microsoft_teams.api import (
    MessageActivityInput,
)

from microsoft_teams.apps import (
    App,
)

from microsoft_teams.cards import (
    AdaptiveCard,
)

from .conversation_binding_store import (
    TeamsConversationBindingStore,
)


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
        raise ValueError(
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


@dataclass(
    frozen=True
)
class TeamsOutboundDependencies:
    """
    Dependencias del adaptador outbound Teams.

    app:
        transporte Microsoft Teams.

    store:
        resolución exacta de una conversación
        previamente registrada.

    El adaptador NO selecciona destinatarios
    de forma implícita.
    """

    app: App

    store: TeamsConversationBindingStore

    def __post_init__(
        self,
    ) -> None:
        if not hasattr(
            self.app,
            "send",
        ):
            raise TypeError(
                "app debe soportar send()."
            )

        if (
            not hasattr(
                self.store,
                "get_exact",
            )
            or not hasattr(
                self.store,
                "upsert",
            )
        ):
            raise TypeError(
                "store debe implementar "
                "TeamsConversationBindingStore."
            )


async def send_teams_message(
    *,
    dependencies: TeamsOutboundDependencies,
    tenant_id: str,
    conversation_id: str,
    text: str,
):
    """
    Envía un mensaje proactivo a una conversación
    Teams previamente registrada.

    El destino sólo puede proceder de:

        tenant_id exacto
        conversation_id exacto
        durable binding store

    El texto no participa nunca en la resolución
    del destinatario ni concede autoridad.
    """

    if not isinstance(
        dependencies,
        TeamsOutboundDependencies,
    ):
        raise TypeError(
            "dependencies debe ser "
            "TeamsOutboundDependencies."
        )

    tenant_id = (
        _require_exact_string(
            name="tenant_id",
            value=tenant_id,
        )
    )

    conversation_id = (
        _require_exact_string(
            name="conversation_id",
            value=conversation_id,
        )
    )

    text = (
        _require_exact_string(
            name="text",
            value=text,
        )
    )

    binding = (
        dependencies
        .store
        .get_exact(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
    )

    activity = (
        MessageActivityInput(
            text=text
        )
    )

    return await dependencies.app.send(
        binding.conversation_id,
        activity,
    )


async def send_teams_adaptive_card(
    *,
    dependencies: TeamsOutboundDependencies,
    tenant_id: str,
    conversation_id: str,
    card: AdaptiveCard,
):
    """
    Envía una Adaptive Card proactiva a una
    conversación Teams previamente registrada.

    El destino procede exclusivamente de:

        tenant_id exacto
        conversation_id exacto
        durable binding store

    El contenido de la tarjeta nunca participa
    en la selección del destinatario.

    La tarjeta tampoco constituye una nueva
    fuente de autoridad operacional.
    """

    if not isinstance(
        dependencies,
        TeamsOutboundDependencies,
    ):
        raise TypeError(
            "dependencies debe ser "
            "TeamsOutboundDependencies."
        )

    tenant_id = (
        _require_exact_string(
            name="tenant_id",
            value=tenant_id,
        )
    )

    conversation_id = (
        _require_exact_string(
            name="conversation_id",
            value=conversation_id,
        )
    )

    if not isinstance(
        card,
        AdaptiveCard,
    ):
        raise TypeError(
            "card debe ser AdaptiveCard."
        )

    binding = (
        dependencies
        .store
        .get_exact(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
    )

    return await dependencies.app.send(
        binding.conversation_id,
        card,
    )
