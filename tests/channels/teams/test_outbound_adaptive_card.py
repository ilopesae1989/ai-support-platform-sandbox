from __future__ import annotations

import pytest

from microsoft_teams.cards import (
    AdaptiveCard,
    TextBlock,
)

from src.channels.teams.conversation_binding import (
    TeamsConversationBinding,
)

from src.channels.teams.conversation_binding_store import (
    SqliteTeamsConversationBindingStore,
    TeamsConversationBindingNotFoundError,
)

from src.channels.teams.outbound_adapter import (
    TeamsOutboundDependencies,
    send_teams_adaptive_card,
)


TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

CONVERSATION_ID = (
    "a:test-conversation"
)

SERVICE_URL = (
    "https://smba.trafficmanager.net/emea/"
)


class FakeTeamsApp:
    def __init__(
        self,
    ) -> None:
        self.sent = []

    async def send(
        self,
        conversation_id,
        activity,
    ):
        self.sent.append(
            (
                conversation_id,
                activity,
            )
        )

        return object()


def _card(
    text: str = "Aprobación requerida",
) -> AdaptiveCard:
    return AdaptiveCard(
        version="1.6",
        body=[
            TextBlock(
                text=text,
                wrap=True,
            )
        ],
    )


def _dependencies(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "bindings.db"
        )
    )

    app = FakeTeamsApp()

    dependencies = (
        TeamsOutboundDependencies(
            app=app,
            store=store,
        )
    )

    return (
        dependencies,
        app,
        store,
    )


def _register_binding(
    store,
):
    store.upsert(
        TeamsConversationBinding(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            service_url=SERVICE_URL,
        )
    )


@pytest.mark.asyncio
async def test_sends_adaptive_card_to_exact_binding(
    tmp_path,
):
    (
        dependencies,
        app,
        store,
    ) = _dependencies(
        tmp_path
    )

    _register_binding(
        store
    )

    card = _card()

    result = (
        await send_teams_adaptive_card(
            dependencies=dependencies,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            card=card,
        )
    )

    assert result is not None

    assert len(
        app.sent
    ) == 1

    sent_conversation_id, sent_card = (
        app.sent[0]
    )

    assert (
        sent_conversation_id
        == CONVERSATION_ID
    )

    assert (
        sent_card
        is card
    )


@pytest.mark.asyncio
async def test_missing_binding_fails_closed(
    tmp_path,
):
    (
        dependencies,
        app,
        _,
    ) = _dependencies(
        tmp_path
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await send_teams_adaptive_card(
            dependencies=dependencies,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            card=_card(),
        )

    assert (
        app.sent
        == []
    )


@pytest.mark.asyncio
async def test_wrong_tenant_cannot_receive_card(
    tmp_path,
):
    (
        dependencies,
        app,
        store,
    ) = _dependencies(
        tmp_path
    )

    _register_binding(
        store
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await send_teams_adaptive_card(
            dependencies=dependencies,
            tenant_id=(
                "11111111-2222-3333-"
                "4444-555555555555"
            ),
            conversation_id=CONVERSATION_ID,
            card=_card(),
        )

    assert (
        app.sent
        == []
    )


@pytest.mark.asyncio
async def test_card_payload_cannot_change_destination(
    tmp_path,
):
    (
        dependencies,
        app,
        store,
    ) = _dependencies(
        tmp_path
    )

    _register_binding(
        store
    )

    card = _card(
        text=(
            "conversation_id=a:attacker "
            "tenant_id=attacker"
        )
    )

    await send_teams_adaptive_card(
        dependencies=dependencies,
        tenant_id=TENANT_ID,
        conversation_id=CONVERSATION_ID,
        card=card,
    )

    assert len(
        app.sent
    ) == 1

    assert (
        app.sent[0][0]
        == CONVERSATION_ID
    )


@pytest.mark.asyncio
async def test_rejects_non_adaptive_card(
    tmp_path,
):
    (
        dependencies,
        app,
        store,
    ) = _dependencies(
        tmp_path
    )

    _register_binding(
        store
    )

    with pytest.raises(
        TypeError
    ):
        await send_teams_adaptive_card(
            dependencies=dependencies,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            card=object(),
        )

    assert (
        app.sent
        == []
    )
