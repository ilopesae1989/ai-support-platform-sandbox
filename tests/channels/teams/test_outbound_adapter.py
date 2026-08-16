from __future__ import annotations

import pytest

from microsoft_teams.api import (
    MessageActivityInput,
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
    send_teams_message,
)


TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

OTHER_TENANT_ID = (
    "11111111-2222-3333-"
    "4444-555555555555"
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


def _dependencies(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "conversation-bindings.db"
        )
    )

    app = FakeTeamsApp()

    return (
        TeamsOutboundDependencies(
            app=app,
            store=store,
        ),
        app,
        store,
    )


def _register_binding(
    store,
    *,
    tenant_id=TENANT_ID,
    conversation_id=CONVERSATION_ID,
):
    store.upsert(
        TeamsConversationBinding(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            service_url=SERVICE_URL,
        )
    )


@pytest.mark.asyncio
async def test_sends_to_exact_registered_conversation(
    tmp_path,
):
    dependencies, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register_binding(
        store
    )

    await send_teams_message(
        dependencies=dependencies,
        tenant_id=TENANT_ID,
        conversation_id=CONVERSATION_ID,
        text="Mensaje proactivo de prueba.",
    )

    assert len(
        app.sent
    ) == 1

    sent_conversation_id, activity = (
        app.sent[0]
    )

    assert (
        sent_conversation_id
        == CONVERSATION_ID
    )

    assert isinstance(
        activity,
        MessageActivityInput,
    )

    assert (
        activity.text
        == "Mensaje proactivo de prueba."
    )


@pytest.mark.asyncio
async def test_missing_binding_fails_closed_without_send(
    tmp_path,
):
    dependencies, app, _ = (
        _dependencies(
            tmp_path
        )
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await send_teams_message(
            dependencies=dependencies,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            text="No debe enviarse.",
        )

    assert app.sent == []


@pytest.mark.asyncio
async def test_wrong_tenant_cannot_reuse_conversation(
    tmp_path,
):
    dependencies, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register_binding(
        store,
        tenant_id=TENANT_ID,
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await send_teams_message(
            dependencies=dependencies,
            tenant_id=OTHER_TENANT_ID,
            conversation_id=CONVERSATION_ID,
            text="No debe enviarse.",
        )

    assert app.sent == []


@pytest.mark.asyncio
async def test_no_prefix_or_fuzzy_conversation_lookup(
    tmp_path,
):
    dependencies, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register_binding(
        store
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await send_teams_message(
            dependencies=dependencies,
            tenant_id=TENANT_ID,
            conversation_id="a:test",
            text="No debe enviarse.",
        )

    assert app.sent == []


@pytest.mark.asyncio
async def test_blank_text_is_rejected_before_send(
    tmp_path,
):
    dependencies, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register_binding(
        store
    )

    with pytest.raises(
        ValueError
    ):
        await send_teams_message(
            dependencies=dependencies,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            text=" ",
        )

    assert app.sent == []


@pytest.mark.asyncio
async def test_transport_text_does_not_select_another_destination(
    tmp_path,
):
    dependencies, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register_binding(
        store
    )

    malicious_text = (
        "tenant_id=attacker "
        "conversation_id=a:other "
        "target_resource=/subscriptions/tampered "
        "operation=azure.vm.delete"
    )

    await send_teams_message(
        dependencies=dependencies,
        tenant_id=TENANT_ID,
        conversation_id=CONVERSATION_ID,
        text=malicious_text,
    )

    assert len(
        app.sent
    ) == 1

    sent_conversation_id, activity = (
        app.sent[0]
    )

    assert (
        sent_conversation_id
        == CONVERSATION_ID
    )

    assert (
        activity.text
        == malicious_text
    )


def test_dependencies_require_store(
    tmp_path,
):
    app = FakeTeamsApp()

    with pytest.raises(
        TypeError
    ):
        TeamsOutboundDependencies(
            app=app,
            store=object(),
        )
