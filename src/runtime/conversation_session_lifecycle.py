from __future__ import annotations

from dataclasses import (
    dataclass,
)

from typing import Any

from agent_framework import (
    AgentSession,
    SessionStore,
)

from src.runtime.conversation_session_identity import (
    ConversationSessionIdentity,
    build_conversation_session_store_id,
)


@dataclass(
    frozen=True
)
class ConversationAgentTurnResult:
    session_store_id: str
    session: AgentSession
    response: Any
    created: bool


def _require_exact_message(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "message debe ser str."
        )

    if (
        not value
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            "message debe ser un string "
            "exacto no vacío."
        )

    return value


async def run_conversation_agent_turn(
    *,
    identity: ConversationSessionIdentity,
    session_store: SessionStore,
    agent: object,
    message: str,
) -> ConversationAgentTurnResult:
    if type(identity) is not ConversationSessionIdentity:
        raise TypeError(
            "identity debe ser exactamente "
            "ConversationSessionIdentity."
        )

    exact_message = _require_exact_message(
        message
    )

    if not isinstance(
        session_store,
        SessionStore,
    ):
        raise TypeError(
            "session_store debe implementar "
            "SessionStore."
        )

    create_session = getattr(
        agent,
        "create_session",
        None,
    )

    run = getattr(
        agent,
        "run",
        None,
    )

    if not callable(
        create_session
    ):
        raise TypeError(
            "agent debe exponer create_session."
        )

    if not callable(
        run
    ):
        raise TypeError(
            "agent debe exponer run."
        )

    session_store_id = (
        build_conversation_session_store_id(
            identity
        )
    )

    session = await session_store.get(
        session_store_id
    )

    created = False

    if session is None:
        session = create_session()
        created = True

    if type(session) is not AgentSession:
        raise TypeError(
            "la sesión debe ser exactamente "
            "AgentSession."
        )

    response = await agent.run(
        exact_message,
        session=session,
    )

    await session_store.set(
        session_store_id,
        session,
    )

    return ConversationAgentTurnResult(
        session_store_id=(
            session_store_id
        ),
        session=session,
        response=response,
        created=created,
    )
