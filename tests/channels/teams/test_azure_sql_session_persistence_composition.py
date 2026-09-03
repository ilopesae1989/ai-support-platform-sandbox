from __future__ import annotations

import dataclasses
import importlib
import inspect
import textwrap

from dataclasses import fields

from src.channels.teams.bootstrap import (
    TeamsHitlPersistence,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)

from src.persistence.azure_sql.session_store import (
    AzureSqlSessionStore,
)


TARGET_MODULE = (
    "src.channels.teams.azure_sql_persistence"
)


BASE_FIELDS = (
    "store",
    "checkpoint_storage",
    "operation_dispatch_ledger",
    "continuation_store",
    "conversation_store",
)


PRODUCTION_FIELDS = (
    *BASE_FIELDS,
    "session_store",
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _settings():
    return AzureSqlManagedIdentitySettings(
        server=(
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        database=(
            "ai_support_platform_sbx"
        ),
    )


def test_production_bundle_extends_base_with_exact_session_store_field():
    module = _module()

    bundle_type = getattr(
        module,
        "AzureSqlTeamsHitlPersistence",
        None,
    )

    assert bundle_type is not None

    assert dataclasses.is_dataclass(
        bundle_type
    )

    assert issubclass(
        bundle_type,
        TeamsHitlPersistence,
    )

    assert tuple(
        field.name
        for field in fields(
            bundle_type
        )
    ) == PRODUCTION_FIELDS


def test_builder_return_contract_is_production_bundle():
    module = _module()

    builder = (
        module
        .build_azure_sql_teams_hitl_persistence
    )

    signature = inspect.signature(
        builder
    )

    assert (
        "AzureSqlTeamsHitlPersistence"
        in str(
            signature.return_annotation
        )
    )


def test_composition_builds_six_adapters_with_one_shared_factory(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    provider_calls = []
    connection_open_attempts = []

    adapter_names = (
        "store",
        "checkpoint_storage",
        "operation_dispatch_ledger",
        "continuation_store",
        "conversation_store",
        "session_store",
    )

    adapter_calls = {
        name: []
        for name in adapter_names
    }

    sentinels = {
        name: object()
        for name in adapter_names
    }

    def shared_connection_factory():
        connection_open_attempts.append(
            object()
        )

        raise AssertionError(
            "La composicion no debe abrir SQL."
        )

    def fake_provider(
        actual_settings,
    ):
        provider_calls.append(
            actual_settings
        )

        return shared_connection_factory

    def fake_adapter(
        name,
    ):
        def constructor(
            **kwargs,
        ):
            adapter_calls[
                name
            ].append(
                kwargs
            )

            return sentinels[
                name
            ]

        return constructor

    monkeypatch.setattr(
        module,
        "build_mssql_python_connection_factory",
        fake_provider,
    )

    monkeypatch.setattr(
        module,
        "AzureSqlPendingApprovalStore",
        fake_adapter(
            "store"
        ),
    )

    monkeypatch.setattr(
        module,
        "AzureSqlCheckpointStorage",
        fake_adapter(
            "checkpoint_storage"
        ),
    )

    monkeypatch.setattr(
        module,
        "AzureSqlOperationDispatchLedger",
        fake_adapter(
            "operation_dispatch_ledger"
        ),
    )

    monkeypatch.setattr(
        module,
        "AzureSqlIncidentContinuationStore",
        fake_adapter(
            "continuation_store"
        ),
    )

    monkeypatch.setattr(
        module,
        "AzureSqlTeamsConversationBindingStore",
        fake_adapter(
            "conversation_store"
        ),
    )

    monkeypatch.setattr(
        module,
        "AzureSqlSessionStore",
        fake_adapter(
            "session_store"
        ),
    )

    monkeypatch.setattr(
        module,
        "incident_checkpoint_allowed_types",
        lambda: {
            "tests.phase21_5:TypeA",
            "tests.phase21_5:TypeB",
        },
    )

    persistence = (
        module
        .build_azure_sql_teams_hitl_persistence(
            settings
        )
    )

    assert provider_calls == [
        settings
    ]

    assert connection_open_attempts == []

    for name in (
        "store",
        "operation_dispatch_ledger",
        "continuation_store",
        "conversation_store",
        "session_store",
    ):
        assert adapter_calls[
            name
        ] == [
            {
                "connection_factory": (
                    shared_connection_factory
                )
            }
        ]

    assert len(
        adapter_calls[
            "checkpoint_storage"
        ]
    ) == 1

    checkpoint_kwargs = (
        adapter_calls[
            "checkpoint_storage"
        ][0]
    )

    assert (
        checkpoint_kwargs[
            "connection_factory"
        ]
        is shared_connection_factory
    )

    assert checkpoint_kwargs[
        "allowed_checkpoint_types"
    ] == [
        "tests.phase21_5:TypeA",
        "tests.phase21_5:TypeB",
    ]

    assert persistence.store is sentinels[
        "store"
    ]

    assert (
        persistence.checkpoint_storage
        is sentinels[
            "checkpoint_storage"
        ]
    )

    assert (
        persistence.operation_dispatch_ledger
        is sentinels[
            "operation_dispatch_ledger"
        ]
    )

    assert (
        persistence.continuation_store
        is sentinels[
            "continuation_store"
        ]
    )

    assert (
        persistence.conversation_store
        is sentinels[
            "conversation_store"
        ]
    )

    assert (
        persistence.session_store
        is sentinels[
            "session_store"
        ]
    )


def test_real_session_store_is_lazy_and_uses_shared_factory(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    provider_calls = []
    connection_open_attempts = []

    def forbidden_connection_factory():
        connection_open_attempts.append(
            object()
        )

        raise AssertionError(
            "La composicion no debe abrir SQL."
        )

    def fake_provider(
        actual_settings,
    ):
        provider_calls.append(
            actual_settings
        )

        return forbidden_connection_factory

    monkeypatch.setattr(
        module,
        "build_mssql_python_connection_factory",
        fake_provider,
    )

    persistence = (
        module
        .build_azure_sql_teams_hitl_persistence(
            settings
        )
    )

    assert provider_calls == [
        settings
    ]

    assert connection_open_attempts == []

    assert isinstance(
        persistence,
        module.AzureSqlTeamsHitlPersistence,
    )

    assert isinstance(
        persistence,
        TeamsHitlPersistence,
    )

    assert isinstance(
        persistence.session_store,
        AzureSqlSessionStore,
    )

    assert (
        persistence.session_store
        ._connection_factory
        is forbidden_connection_factory
    )


def test_composition_adds_session_store_without_new_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    for required in (
        "azuresqlsessionstore",
        "session_store",
        "azuresqlteamshitlpersistence",
        "build_mssql_python_connection_factory",
    ):
        assert required in lowered

    assert (
        lowered.count(
            "build_mssql_python_connection_factory("
        )
        == 1
    )

    for forbidden in (
        "os.environ",
        "os.getenv",
        "mssql_python.connect",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "create table",
        "alter table",
        "drop table",
        "truncate table",
        "sqlite",
        "cosmos",
        "servicebus",
        "agent.run",
        "create_session",
        "get_session",
        "service_session_id ==",
        "service_session_id !=",
    ):
        assert forbidden not in lowered
