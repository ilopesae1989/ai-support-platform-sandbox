from __future__ import annotations

from dataclasses import (
    dataclass,
)

from microsoft_teams.api import (
    MessageActivity,
)

from microsoft_teams.apps import (
    ActivityContext,
    App,
)

from .conversation_binding import (
    TeamsConversationBindingError,
    build_teams_conversation_binding,
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
class TeamsConversationHandlerDependencies:
    """
    Dependencias exclusivas del boundary de
    transporte conversacional Teams.

    expected_tenant_id:
        tenant exacto permitido para registrar
        destinos de transporte.

    store:
        persistencia durable del binding.

    No contiene autoridad Azure ni HITL.
    """

    expected_tenant_id: str

    store: TeamsConversationBindingStore

    def __post_init__(
        self,
    ) -> None:
        _require_exact_string(
            name="expected_tenant_id",
            value=self.expected_tenant_id,
        )


async def handle_teams_conversation_message(
    *,
    ctx: ActivityContext[
        MessageActivity
    ],
    dependencies: TeamsConversationHandlerDependencies,
) -> None:
    """
    Boundary:

        authenticated MessageActivity
                    ↓
        transport binding extraction
                    ↓
        exact tenant gate
                    ↓
        durable binding store
                    ↓
        reactive acknowledgement

    El contenido textual del mensaje nunca
    concede autoridad operacional.
    """

    if not isinstance(
        dependencies,
        TeamsConversationHandlerDependencies,
    ):
        raise TypeError(
            "dependencies debe ser "
            "TeamsConversationHandlerDependencies."
        )

    try:
        binding = (
            build_teams_conversation_binding(
                ctx.activity
            )
        )

    except TeamsConversationBindingError:
        # Fail closed.
        #
        # No persistimos contexto incompleto
        # o procedente de otro canal.
        return

    if (
        binding.tenant_id
        != dependencies.expected_tenant_id
    ):
        # Fail closed ante tenant diferente.
        return

    dependencies.store.upsert(
        binding
    )

    await ctx.send(
        "AI Support Platform: "
        "conversación Teams registrada."
    )


def register_teams_conversation_handler(
    *,
    app: App,
    dependencies: TeamsConversationHandlerDependencies,
):
    """
    Registra el boundary MessageActivity real.

    No enruta todavía a agentes, workflows,
    Azure Operations ni MCP.
    """

    @app.on_message
    async def handle(
        ctx: ActivityContext[
            MessageActivity
        ],
    ) -> None:
        await (
            handle_teams_conversation_message(
                ctx=ctx,
                dependencies=dependencies,
            )
        )

    return handle
