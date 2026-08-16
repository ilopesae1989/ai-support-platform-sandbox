from __future__ import annotations

import sqlite3

import pytest

from src.channels.teams.conversation_binding import (
    TeamsConversationBinding,
)

from src.channels.teams.conversation_binding_store import (
    SqliteTeamsConversationBindingStore,
    TeamsConversationBindingNotFoundError,
)


TENANT_ID = (
    "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb"
)

OTHER_TENANT_ID = (
    "11111111-2222-3333-4444-555555555555"
)

CONVERSATION_ID = (
    "19:test-conversation@thread.v2"
)

SERVICE_URL = (
    "https://smba.trafficmanager.net/emea/"
)

UPDATED_SERVICE_URL = (
    "https://smba.trafficmanager.net/teams/"
)


def _binding(
    *,
    tenant_id: str = TENANT_ID,
    conversation_id: str = CONVERSATION_ID,
    service_url: str = SERVICE_URL,
) -> TeamsConversationBinding:
    return TeamsConversationBinding(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        service_url=service_url,
    )


def test_round_trip_binding(
    tmp_path,
):
    database_path = (
        tmp_path
        / "teams-bindings.db"
    )

    store = (
        SqliteTeamsConversationBindingStore(
            database_path
        )
    )

    binding = _binding()

    store.upsert(
        binding
    )

    loaded = (
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert loaded == binding


def test_binding_survives_store_recreation(
    tmp_path,
):
    database_path = (
        tmp_path
        / "teams-bindings.db"
    )

    first_store = (
        SqliteTeamsConversationBindingStore(
            database_path
        )
    )

    first_store.upsert(
        _binding()
    )

    second_store = (
        SqliteTeamsConversationBindingStore(
            database_path
        )
    )

    loaded = (
        second_store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert loaded == _binding()


def test_upsert_refreshes_service_url_for_exact_binding(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    store.upsert(
        _binding()
    )

    store.upsert(
        _binding(
            service_url=(
                UPDATED_SERVICE_URL
            )
        )
    )

    loaded = (
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
    )

    assert (
        loaded.service_url
        == UPDATED_SERVICE_URL
    )


def test_same_conversation_id_isolated_by_tenant(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    first = _binding()

    second = _binding(
        tenant_id=OTHER_TENANT_ID,
        service_url=UPDATED_SERVICE_URL,
    )

    store.upsert(
        first
    )

    store.upsert(
        second
    )

    assert (
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
        == first
    )

    assert (
        store.get_exact(
            tenant_id=OTHER_TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )
        == second
    )


def test_missing_exact_binding_fails_closed(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
        )


def test_no_fuzzy_or_prefix_lookup(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    store.upsert(
        _binding()
    )

    with pytest.raises(
        TeamsConversationBindingNotFoundError
    ):
        store.get_exact(
            tenant_id=TENANT_ID,
            conversation_id=(
                "19:test-conversation"
            ),
        )


@pytest.mark.parametrize(
    (
        "tenant_id",
        "conversation_id",
    ),
    [
        ("", CONVERSATION_ID),
        (" ", CONVERSATION_ID),
        (TENANT_ID, ""),
        (TENANT_ID, " "),
    ],
)
def test_lookup_requires_exact_non_empty_values(
    tmp_path,
    tenant_id,
    conversation_id,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    with pytest.raises(
        ValueError
    ):
        store.get_exact(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )


def test_upsert_rejects_wrong_type(
    tmp_path,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    with pytest.raises(
        TypeError
    ):
        store.upsert(
            object()
        )


@pytest.mark.parametrize(
    "binding",
    [
        TeamsConversationBinding(
            tenant_id=" ",
            conversation_id=CONVERSATION_ID,
            service_url=SERVICE_URL,
        ),
        TeamsConversationBinding(
            tenant_id=TENANT_ID,
            conversation_id=" ",
            service_url=SERVICE_URL,
        ),
        TeamsConversationBinding(
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            service_url=" ",
        ),
    ],
)
def test_upsert_revalidates_binding_boundary(
    tmp_path,
    binding,
):
    store = (
        SqliteTeamsConversationBindingStore(
            tmp_path
            / "teams-bindings.db"
        )
    )

    with pytest.raises(
        ValueError
    ):
        store.upsert(
            binding
        )


def test_database_schema_contains_only_transport_authority(
    tmp_path,
):
    database_path = (
        tmp_path
        / "teams-bindings.db"
    )

    SqliteTeamsConversationBindingStore(
        database_path
    )

    with sqlite3.connect(
        database_path
    ) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    teams_conversation_bindings
                )
                """
            )
        }

    assert columns == {
        "tenant_id",
        "conversation_id",
        "service_url",
    }
