from dataclasses import (
    replace,
)

import pytest

import src.channels.teams.approval_bridge as approval_bridge

from src.runtime.procedure.approval_correlation import (
    PendingApprovalCorrelation,
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

REQUEST_ID = (
    "request-info-phase18-notify-001"
)

CHECKPOINT_ID = (
    "checkpoint-phase18-notify-001"
)


def create_approval_request():
    return replace(
        create_request(),
        conversation_id=CONVERSATION_ID,
    )


def create_correlation(
    request,
    *,
    request_id=REQUEST_ID,
):
    return PendingApprovalCorrelation(
        approval_id=(
            request.approval_id
        ),
        workflow_id=(
            request.workflow_id
        ),
        request_id=(
            request_id
        ),
        checkpoint_id=(
            CHECKPOINT_ID
        ),
    )


class FakeRegisteredApprovalStore:
    """
    Este fake NO implementa register().

    Esta fase sólo puede consultar una
    correlación ya persistida.
    """

    def __init__(
        self,
        correlation,
    ):
        self.correlation = correlation
        self.lookups = []

    def get_by_approval_id(
        self,
        approval_id,
    ):
        self.lookups.append(
            approval_id
        )

        return self.correlation


@pytest.mark.asyncio
async def test_notifies_only_after_exact_registered_correlation(
    monkeypatch,
):
    request = create_approval_request()

    correlation = create_correlation(
        request
    )

    store = FakeRegisteredApprovalStore(
        correlation
    )

    sent = []
    expected_result = object()

    async def fake_notify_teams_approval(
        *,
        request,
        outbound,
        tenant_id,
        conversation_id,
    ):
        sent.append(
            (
                request,
                outbound,
                tenant_id,
                conversation_id,
            )
        )

        return expected_result

    monkeypatch.setattr(
        approval_bridge,
        "notify_teams_approval",
        fake_notify_teams_approval,
        raising=False,
    )

    outbound = object()

    result = await (
        approval_bridge
        .notify_registered_teams_approval(
            request=request,
            request_id=REQUEST_ID,
            store=store,
            outbound=outbound,
            tenant_id=TENANT_ID,
            conversation_id=(
                CONVERSATION_ID
            ),
        )
    )

    assert result is expected_result

    assert store.lookups == [
        request.approval_id
    ]

    assert sent == [
        (
            request,
            outbound,
            TENANT_ID,
            CONVERSATION_ID,
        )
    ]


@pytest.mark.asyncio
async def test_request_id_mismatch_fails_closed_before_send(
    monkeypatch,
):
    request = create_approval_request()

    correlation = create_correlation(
        request,
        request_id=(
            "different-request-id"
        ),
    )

    store = FakeRegisteredApprovalStore(
        correlation
    )

    sent = []

    async def fake_notify_teams_approval(
        **kwargs,
    ):
        sent.append(
            kwargs
        )

        return object()

    monkeypatch.setattr(
        approval_bridge,
        "notify_teams_approval",
        fake_notify_teams_approval,
        raising=False,
    )

    with pytest.raises(
        approval_bridge.TeamsApprovalBridgeError
    ):
        await (
            approval_bridge
            .notify_registered_teams_approval(
                request=request,
                request_id=REQUEST_ID,
                store=store,
                outbound=object(),
                tenant_id=TENANT_ID,
                conversation_id=(
                    CONVERSATION_ID
                ),
            )
        )

    assert sent == []


@pytest.mark.asyncio
async def test_transport_failure_can_retry_without_reregistering(
    monkeypatch,
):
    request = create_approval_request()

    correlation = create_correlation(
        request
    )

    store = FakeRegisteredApprovalStore(
        correlation
    )

    attempts = []
    expected_result = object()

    async def flaky_notify(
        **kwargs,
    ):
        attempts.append(
            kwargs
        )

        if len(attempts) == 1:
            raise RuntimeError(
                "synthetic Teams transport failure"
            )

        return expected_result

    monkeypatch.setattr(
        approval_bridge,
        "notify_teams_approval",
        flaky_notify,
        raising=False,
    )

    kwargs = {
        "request": request,
        "request_id": REQUEST_ID,
        "store": store,
        "outbound": object(),
        "tenant_id": TENANT_ID,
        "conversation_id": (
            CONVERSATION_ID
        ),
    }

    with pytest.raises(
        RuntimeError,
        match="synthetic Teams transport failure",
    ):
        await (
            approval_bridge
            .notify_registered_teams_approval(
                **kwargs
            )
        )

    #
    # Segundo intento:
    #
    # NO registra otra correlación.
    # Sólo vuelve a validar la existente
    # y reintenta el transporte.
    #
    result = await (
        approval_bridge
        .notify_registered_teams_approval(
            **kwargs
        )
    )

    assert result is expected_result

    assert len(attempts) == 2

    assert store.lookups == [
        request.approval_id,
        request.approval_id,
    ]

    assert (
        store.correlation
        is correlation
    )
