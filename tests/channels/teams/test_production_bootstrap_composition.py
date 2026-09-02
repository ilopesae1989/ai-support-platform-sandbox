from __future__ import annotations

import ast
import importlib
import inspect
import textwrap

import pytest

from src.channels.teams.bootstrap import (
    TeamsHitlAppSettings,
    TeamsHitlSettings,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.channels.teams.production_bootstrap"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


class FakePowerStateReader:
    def read_power_state(
        self,
        *,
        subscription_id,
        resource_group,
        vm_name,
    ):
        raise AssertionError(
            "El reader no debe ejecutarse "
            "durante composición."
        )


def _reader():
    return FakePowerStateReader()


def _app_settings():
    return TeamsHitlAppSettings(
        client_id="teams-app-client-id",
        client_secret="test-client-secret",
        bot_tenant_id="bot-tenant-id",
        teams_channel_tenant_id=(
            "channel-tenant-id"
        ),
        approver_aad_object_id=(
            "approver-object-id"
        ),
    )


def _azure_sql_settings():
    return AzureSqlManagedIdentitySettings(
        server=(
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        database=(
            "ai_support_platform_sbx"
        ),
    )


def test_production_builder_has_exact_explicit_surface():
    module = _module()

    builder = getattr(
        module,
        "build_production_teams_hitl_app",
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
            "app_settings",
            "azure_sql_settings",
            "azure_vm_power_state_reader",
        )
    )

    reader_parameter = (
        signature.parameters[
            "azure_vm_power_state_reader"
        ]
    )

    assert (
        reader_parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert (
        reader_parameter.default
        is inspect.Parameter.empty
    )


def test_production_builder_rejects_local_persistence_settings(
    tmp_path,
):
    module = _module()

    local_settings = TeamsHitlSettings(
        client_id="client-id",
        client_secret="secret",
        bot_tenant_id="tenant",
        teams_channel_tenant_id="tenant",
        approver_aad_object_id="approver",
        pending_database_path=(
            tmp_path / "pending.db"
        ),
        checkpoint_path=(
            tmp_path / "checkpoints"
        ),
        operation_dispatch_database_path=(
            tmp_path / "dispatch.db"
        ),
        conversation_binding_database_path=(
            tmp_path / "conversation.db"
        ),
    )

    with pytest.raises(
        TypeError
    ):
        module.build_production_teams_hitl_app(
            local_settings,
            _azure_sql_settings(),
            azure_vm_power_state_reader=_reader(),
        )


def test_production_builder_rejects_unstructured_azure_sql_configuration():
    module = _module()

    with pytest.raises(
        TypeError
    ):
        module.build_production_teams_hitl_app(
            _app_settings(),
            (
                "Server=forbidden;"
                "Database=forbidden;"
                "Password=forbidden;"
            ),
            azure_vm_power_state_reader=_reader(),
        )


def test_production_builder_requires_post_operation_reader():
    module = _module()

    with pytest.raises(
        TypeError
    ):
        module.build_production_teams_hitl_app(
            _app_settings(),
            _azure_sql_settings(),
            azure_vm_power_state_reader=None,
        )


def test_production_builder_rejects_reader_without_contract():
    module = _module()

    with pytest.raises(
        TypeError
    ):
        module.build_production_teams_hitl_app(
            _app_settings(),
            _azure_sql_settings(),
            azure_vm_power_state_reader=object(),
        )


def test_production_builder_composes_azure_sql_once_and_injects_exactly(
    monkeypatch,
):
    module = _module()

    app_settings = _app_settings()
    azure_sql_settings = (
        _azure_sql_settings()
    )

    reader = _reader()
    persistence = object()
    bootstrap = object()

    persistence_calls = []
    teams_calls = []

    def fake_build_persistence(
        settings,
    ):
        persistence_calls.append(
            settings
        )

        return persistence

    def fake_build_teams(
        settings,
        *,
        persistence,
        azure_vm_power_state_reader,
    ):
        teams_calls.append(
            {
                "settings": settings,
                "persistence": persistence,
                "azure_vm_power_state_reader": (
                    azure_vm_power_state_reader
                ),
            }
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_azure_sql_teams_hitl_persistence",
        fake_build_persistence,
    )

    monkeypatch.setattr(
        module,
        "build_teams_hitl_app",
        fake_build_teams,
    )

    result = (
        module
        .build_production_teams_hitl_app(
            app_settings,
            azure_sql_settings,
            azure_vm_power_state_reader=reader,
        )
    )

    assert result is bootstrap

    assert (
        persistence_calls
        == [
            azure_sql_settings
        ]
    )

    assert (
        teams_calls
        == [
            {
                "settings": (
                    app_settings
                ),
                "persistence": (
                    persistence
                ),
                "azure_vm_power_state_reader": (
                    reader
                ),
            }
        ]
    )


def test_production_composition_contains_no_local_fallback_environment_or_runtime_side_effect():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    tree = ast.parse(
        source
    )

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

    forbidden_names = {
        "getenv",
        "environ",
        "from_environment",
        "build_local_teams_hitl_persistence",
        "SqlitePendingApprovalStore",
        "SqliteOperationDispatchLedger",
        "SqliteIncidentContinuationStore",
        "SqliteTeamsConversationBindingStore",
        "AzureCliCredential",
        "ManagedIdentityCredential",
        "DefaultAzureCredential",
    }

    assert forbidden_names.isdisjoint(
        observed_names
    )

    lowered = source.lower()

    forbidden_fragments = (
        "os.getenv",
        "os.environ",
        "sqlite",
        "client_secret=",
        "connection_string",
        "password=",
        "mssql_python.connect",
        "create table",
        "alter table",
        "drop table",
        ".start(",
        ".run(",
        "asyncio.run",
        "servicebus",
        "cosmos",
    )

    for fragment in forbidden_fragments:
        assert fragment not in lowered
