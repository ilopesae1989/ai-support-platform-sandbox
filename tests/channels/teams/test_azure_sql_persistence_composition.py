from __future__ import annotations

import ast
import importlib
import inspect
import textwrap

import pytest

from dataclasses import fields

from src.channels.teams import (
    bootstrap as teams_bootstrap,
)

from src.persistence.azure_sql.checkpoint_storage import (
    AzureSqlCheckpointStorage,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)

from src.persistence.azure_sql.conversation_binding_store import (
    AzureSqlTeamsConversationBindingStore,
)

from src.persistence.azure_sql.incident_continuation_store import (
    AzureSqlIncidentContinuationStore,
)

from src.persistence.azure_sql.operation_dispatch_ledger import (
    AzureSqlOperationDispatchLedger,
)

from src.persistence.azure_sql.wait_recheck_consumption_ledger import (
    AzureSqlWaitRecheckConsumptionLedger,
)

from src.persistence.azure_sql.pending_approval_store import (
    AzureSqlPendingApprovalStore,
)

from src.workflows.incident_resolution.checkpoint_storage import (
    incident_checkpoint_allowed_types,
)


TARGET_MODULE = (
    "src.channels.teams.azure_sql_persistence"
)


EXPECTED_PERSISTENCE_FIELDS = (
    "store",
    "checkpoint_storage",
    "operation_dispatch_ledger",
    "wait_recheck_consumption_ledger",
    "continuation_store",
    "conversation_store",
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


def test_azure_sql_composition_builder_has_exact_surface():
    module = _module()

    builder = getattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        None,
    )

    assert callable(
        builder
    )

    signature = inspect.signature(
        builder
    )

    assert (
        tuple(
            signature.parameters
        )
        == (
            "settings",
        )
    )

    parameter = signature.parameters[
        "settings"
    ]

    assert parameter.kind in {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }


def test_azure_sql_composition_rejects_unstructured_connection_input():
    module = _module()

    builder = (
        module
        .build_azure_sql_teams_hitl_persistence
    )

    with pytest.raises(
        TypeError
    ):
        builder(
            "Server=forbidden;"
            "Database=forbidden;"
            "User ID=forbidden;"
            "Password=forbidden;"
        )


def test_azure_sql_composition_builds_one_shared_factory_and_exact_bundle(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    provider_calls = []

    adapter_calls = {
        "store": [],
        "checkpoint_storage": [],
        "operation_dispatch_ledger": [],
        "wait_recheck_consumption_ledger": [],
        "continuation_store": [],
        "conversation_store": [],
    }

    sentinels = {
        name: object()
        for name in adapter_calls
    }

    connection_factory_calls = []

    def shared_connection_factory():
        connection_factory_calls.append(
            object()
        )

        raise AssertionError(
            "La composición no debe abrir "
            "una conexión SQL."
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
            adapter_calls[name].append(
                kwargs
            )

            return sentinels[name]

        return constructor

    expected_allowed_types = {
        (
            "tests.phase20_30:"
            + f"Type{index:02d}"
        )
        for index in range(
            53
        )
    }

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
        "AzureSqlWaitRecheckConsumptionLedger",
        fake_adapter(
            "wait_recheck_consumption_ledger"
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
        "incident_checkpoint_allowed_types",
        lambda: set(
            expected_allowed_types
        ),
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

    assert connection_factory_calls == []

    assert (
        adapter_calls["store"]
        == [
            {
                "connection_factory": (
                    shared_connection_factory
                )
            }
        ]
    )

    assert (
        adapter_calls[
            "operation_dispatch_ledger"
        ]
        == [
            {
                "connection_factory": (
                    shared_connection_factory
                )
            }
        ]
    )

    assert (
        adapter_calls[
            "wait_recheck_consumption_ledger"
        ]
        == [
            {
                "connection_factory": (
                    shared_connection_factory
                )
            }
        ]
    )

    assert (
        adapter_calls[
            "continuation_store"
        ]
        == [
            {
                "connection_factory": (
                    shared_connection_factory
                )
            }
        ]
    )

    assert (
        adapter_calls[
            "conversation_store"
        ]
        == [
            {
                "connection_factory": (
                    shared_connection_factory
                )
            }
        ]
    )

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

    assert (
        checkpoint_kwargs[
            "allowed_checkpoint_types"
        ]
        == sorted(
            expected_allowed_types
        )
    )

    assert (
        persistence.store
        is sentinels["store"]
    )

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
        persistence.wait_recheck_consumption_ledger
        is sentinels[
            "wait_recheck_consumption_ledger"
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


def test_azure_sql_composition_is_lazy_and_opens_no_connection(
    monkeypatch,
):
    module = _module()

    settings = _settings()

    connection_open_attempts = []

    def forbidden_connection_factory():
        connection_open_attempts.append(
            object()
        )

        raise AssertionError(
            "No debe abrirse SQL durante composición."
        )

    provider_calls = []

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
        teams_bootstrap.TeamsHitlPersistence,
    )

    assert isinstance(
        persistence.store,
        AzureSqlPendingApprovalStore,
    )

    assert isinstance(
        persistence.checkpoint_storage,
        AzureSqlCheckpointStorage,
    )

    assert isinstance(
        persistence.operation_dispatch_ledger,
        AzureSqlOperationDispatchLedger,
    )

    assert isinstance(
        persistence.wait_recheck_consumption_ledger,
        AzureSqlWaitRecheckConsumptionLedger,
    )

    assert isinstance(
        persistence.continuation_store,
        AzureSqlIncidentContinuationStore,
    )

    assert isinstance(
        persistence.conversation_store,
        AzureSqlTeamsConversationBindingStore,
    )

    assert (
        persistence.store._connection_factory
        is forbidden_connection_factory
    )

    assert (
        persistence.checkpoint_storage
        ._connection_factory
        is forbidden_connection_factory
    )

    assert (
        persistence.operation_dispatch_ledger
        ._connection_factory
        is forbidden_connection_factory
    )

    assert (
        persistence.wait_recheck_consumption_ledger
        ._connection_factory
        is forbidden_connection_factory
    )

    assert (
        persistence.continuation_store
        ._connection_factory
        is forbidden_connection_factory
    )

    assert (
        persistence.conversation_store
        ._connection_factory
        is forbidden_connection_factory
    )

    expected_allowed_types = (
        incident_checkpoint_allowed_types()
    )

    assert len(
        expected_allowed_types
    ) == 55

    assert (
        persistence.checkpoint_storage
        ._allowed_types
        == frozenset(
            expected_allowed_types
        )
    )


def test_azure_sql_composition_returns_exact_teams_persistence_contract():
    module = _module()

    persistence_type = getattr(
        teams_bootstrap,
        "TeamsHitlPersistence",
        None,
    )

    assert persistence_type is not None

    assert (
        tuple(
            field.name
            for field in fields(
                persistence_type
            )
        )
        == EXPECTED_PERSISTENCE_FIELDS
    )

    source = textwrap.dedent(
        inspect.getsource(
            module
            .build_azure_sql_teams_hitl_persistence
        )
    )

    assert (
        "TeamsHitlPersistence"
        in source
    )


def test_azure_sql_composition_reads_no_environment_and_exposes_no_secret_surface():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    tree = ast.parse(
        source
    )

    forbidden_names = {
        "os",
        "environ",
        "getenv",
        "_required_environment_value",
    }

    observed_names = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Name,
        ):
            observed_names.add(
                node.id
            )

        elif isinstance(
            node,
            ast.Attribute,
        ):
            observed_names.add(
                node.attr
            )

    assert forbidden_names.isdisjoint(
        observed_names
    )

    forbidden_source_fragments = (
        "connection_string",
        "client_secret",
        "password",
        "sql_password",
        "user_password",
    )

    lowered = source.lower()

    for fragment in (
        forbidden_source_fragments
    ):
        assert fragment not in lowered


def test_azure_sql_composition_contains_no_runtime_ddl_cloud_or_alternate_backend():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    forbidden_fragments = (
        "create table",
        "alter table",
        "drop table",
        "truncate table",
        "platform/azure-sql/migrations",
        "platform\\azure-sql\\migrations",
        "mssql_python.connect",
        "defaultazurecredential",
        "azureclicredential",
        "aiprojectclient",
        "cosmos",
        "servicebus",
        "sqlite",
    )

    for fragment in forbidden_fragments:
        assert fragment not in lowered


def test_azure_sql_composition_does_not_modify_local_persistence_authority():
    _module()

    local_factory = (
        teams_bootstrap
        .build_local_teams_hitl_persistence
    )

    signature = inspect.signature(
        local_factory
    )

    assert (
        tuple(
            signature.parameters
        )
        == (
            "settings",
        )
    )

    source = textwrap.dedent(
        inspect.getsource(
            local_factory
        )
    )

    forbidden_fragments = (
        "AzureSql",
        "build_mssql_python_connection_factory",
        "AzureSqlManagedIdentitySettings",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
