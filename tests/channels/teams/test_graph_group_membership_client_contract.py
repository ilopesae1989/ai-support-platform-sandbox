from __future__ import annotations

import importlib

import pytest


USER_OBJECT_ID = (
    "44444444-4444-4444-"
    "8444-444444444444"
)

GROUP_OBJECT_ID = (
    "55555555-5555-4555-"
    "8555-555555555555"
)

OTHER_GROUP_OBJECT_ID = (
    "66666666-6666-4666-"
    "8666-666666666666"
)

GRAPH_SCOPE = (
    "https://graph.microsoft.com/.default"
)

EXPECTED_URL = (
    "https://graph.microsoft.com/v1.0/"
    f"users/{USER_OBJECT_ID}/checkMemberGroups"
)


class Token:
    token = "test-token"


class CredentialStub:
    def __init__(self):
        self.calls = []

    async def get_token(
        self,
        *scopes,
        **kwargs,
    ):
        self.calls.append(
            {
                "scopes": scopes,
                "kwargs": kwargs,
            }
        )

        return Token()


class TransportStub:
    def __init__(
        self,
        *,
        response=None,
        error: Exception | None = None,
    ):
        self.response = (
            {"value": [GROUP_OBJECT_ID]}
            if response is None
            else response
        )

        self.error = error
        self.calls = []

    async def post_json(
        self,
        *,
        url,
        headers,
        payload,
        timeout_seconds,
    ):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response


def _contract():
    module = importlib.import_module(
        "src.channels.teams.graph_group_membership"
    )

    client_cls = getattr(
        module,
        "MicrosoftGraphGroupMembershipClient",
    )

    error_cls = getattr(
        module,
        "GraphMembershipClientError",
    )

    return (
        client_cls,
        error_cls,
    )


@pytest.mark.asyncio
async def test_client_uses_exact_v1_check_member_groups_contract():
    client_cls, _error_cls = (
        _contract()
    )

    credential = CredentialStub()
    transport = TransportStub()

    client = client_cls(
        credential=credential,
        transport=transport,
        timeout_seconds=3.0,
    )

    result = await (
        client.is_transitive_member(
            user_object_id=USER_OBJECT_ID,
            group_object_id=GROUP_OBJECT_ID,
        )
    )

    assert result is True

    assert credential.calls == [
        {
            "scopes": (
                GRAPH_SCOPE,
            ),
            "kwargs": {},
        }
    ]

    assert len(
        transport.calls
    ) == 1

    call = transport.calls[0]

    assert (
        call["url"]
        == EXPECTED_URL
    )

    assert call["payload"] == {
        "groupIds": [
            GROUP_OBJECT_ID
        ]
    }

    assert (
        call["headers"]["Authorization"]
        == "Bearer test-token"
    )

    assert (
        call["timeout_seconds"]
        == 3.0
    )


@pytest.mark.asyncio
async def test_empty_check_member_groups_result_means_not_member():
    client_cls, _error_cls = (
        _contract()
    )

    client = client_cls(
        credential=CredentialStub(),
        transport=TransportStub(
            response={
                "value": []
            }
        ),
        timeout_seconds=3.0,
    )

    assert (
        await client.is_transitive_member(
            user_object_id=USER_OBJECT_ID,
            group_object_id=GROUP_OBJECT_ID,
        )
        is False
    )


@pytest.mark.asyncio
async def test_different_group_in_response_does_not_authorize():
    client_cls, _error_cls = (
        _contract()
    )

    client = client_cls(
        credential=CredentialStub(),
        transport=TransportStub(
            response={
                "value": [
                    OTHER_GROUP_OBJECT_ID
                ]
            }
        ),
        timeout_seconds=3.0,
    )

    assert (
        await client.is_transitive_member(
            user_object_id=USER_OBJECT_ID,
            group_object_id=GROUP_OBJECT_ID,
        )
        is False
    )


@pytest.mark.asyncio
async def test_transport_failure_is_wrapped_in_graph_membership_error():
    client_cls, error_cls = (
        _contract()
    )

    client = client_cls(
        credential=CredentialStub(),
        transport=TransportStub(
            error=RuntimeError(
                "backend unavailable"
            )
        ),
        timeout_seconds=3.0,
    )

    with pytest.raises(
        error_cls,
    ):
        await client.is_transitive_member(
            user_object_id=USER_OBJECT_ID,
            group_object_id=GROUP_OBJECT_ID,
        )


@pytest.mark.asyncio
async def test_transport_timeout_is_wrapped_in_graph_membership_error():
    client_cls, error_cls = (
        _contract()
    )

    client = client_cls(
        credential=CredentialStub(),
        transport=TransportStub(
            error=TimeoutError(
                "request timeout"
            )
        ),
        timeout_seconds=3.0,
    )

    with pytest.raises(
        error_cls,
    ):
        await client.is_transitive_member(
            user_object_id=USER_OBJECT_ID,
            group_object_id=GROUP_OBJECT_ID,
        )


@pytest.mark.asyncio
async def test_malformed_graph_response_fails_closed():
    client_cls, error_cls = (
        _contract()
    )

    client = client_cls(
        credential=CredentialStub(),
        transport=TransportStub(
            response={
                "value": {
                    "attacker": (
                        GROUP_OBJECT_ID
                    )
                }
            }
        ),
        timeout_seconds=3.0,
    )

    with pytest.raises(
        error_cls,
    ):
        await client.is_transitive_member(
            user_object_id=USER_OBJECT_ID,
            group_object_id=GROUP_OBJECT_ID,
        )