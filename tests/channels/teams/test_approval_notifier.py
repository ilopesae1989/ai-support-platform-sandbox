from __future__ import annotations

from dataclasses import replace

import pytest

from microsoft_teams.cards import (
    AdaptiveCard,
)

from src.channels.teams.approval_notifier import (
    TeamsApprovalNotificationError,
    notify_teams_approval,
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
)

from tests.channels.teams.test_approval_card import (
    create_request,
)


TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

CONVERSATION_ID = (
    "a:test-approval-conversation"
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


def _request():
    return replace(
        create_request(),
        conversation_id=(
            CONVERSATION_ID
        ),
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

    outbound = (
        TeamsOutboundDependencies(
            app=app,
            store=store,
        )
    )

    return (
        outbound,
        app,
        store,
    )


def _register(
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
async def test_sends_governed_approval_card_to_exact_conversation(
    tmp_path,
):
    outbound, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register(
        store
    )

    result = await notify_teams_approval(
        request=_request(),
        outbound=outbound,
        tenant_id=TENANT_ID,
        conversation_id=CONVERSATION_ID,
    )

    assert result is not None

    assert len(
        app.sent
    ) == 1

    sent_conversation_id, card = (
        app.sent[0]
    )

    assert (
        sent_conversation_id
        == CONVERSATION_ID
    )

    assert isinstance(
        card,
        AdaptiveCard,
    )

    payload = card.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )

    serialized = str(
        payload
    )

    assert (
        _request().approval_id
        in serialized
    )

    assert (
        "APROBAR"
        in serialized
    )

    assert (
        "RECHAZAR"
        in serialized
    )


@pytest.mark.asyncio
async def test_request_conversation_mismatch_fails_closed(
    tmp_path,
):
    outbound, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register(
        store
    )

    request = replace(
        _request(),
        conversation_id=(
            "a:different-conversation"
        ),
    )

    with pytest.raises(
        TeamsApprovalNotificationError
    ):
        await notify_teams_approval(
            request=request,
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )

    assert (
        app.sent
        == []
    )


@pytest.mark.asyncio
async def test_missing_request_conversation_fails_closed(
    tmp_path,
):
    outbound, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register(
        store
    )

    request = replace(
        _request(),
        conversation_id=None,
    )

    with pytest.raises(
        TeamsApprovalNotificationError
    ):
        await notify_teams_approval(
            request=request,
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )

    assert (
        app.sent
        == []
    )


@pytest.mark.asyncio
async def test_missing_binding_fails_closed(
    tmp_path,
):
    outbound, app, _ = (
        _dependencies(
            tmp_path
        )
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await notify_teams_approval(
            request=_request(),
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )

    assert (
        app.sent
        == []
    )


@pytest.mark.asyncio
async def test_wrong_tenant_cannot_receive_approval(
    tmp_path,
):
    outbound, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register(
        store
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        await notify_teams_approval(
            request=_request(),
            outbound=outbound,
            tenant_id=(
                "11111111-2222-3333-"
                "4444-555555555555"
            ),
            conversation_id=CONVERSATION_ID,
        )

    assert (
        app.sent
        == []
    )


@pytest.mark.asyncio
async def test_requires_real_approval_request(
    tmp_path,
):
    outbound, app, store = (
        _dependencies(
            tmp_path
        )
    )

    _register(
        store
    )

    with pytest.raises(
        TypeError
    ):
        await notify_teams_approval(
            request=object(),
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )

    assert (
        app.sent
        == []
    )
