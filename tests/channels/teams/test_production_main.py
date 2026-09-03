from __future__ import annotations

import importlib
import inspect
import textwrap

import pytest


TARGET_MODULE = (
    "src.channels.teams.production_main"
)


TEAMS_IDENTITY = (
    "11111111-1111-4111-8111-111111111111"
)

SQL_IDENTITY = (
    "22222222-2222-4222-8222-222222222222"
)

VM_IDENTITY = (
    "a3333333-3333-4333-8333-333333333333"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _valid_environment():
    return {
        "CLIENT_ID": (
            "teams-app-client-id"
        ),
        "MANAGED_IDENTITY_CLIENT_ID": (
            TEAMS_IDENTITY
        ),
        "TENANT_ID": (
            "bot-tenant-id"
        ),
        "TEAMS_CHANNEL_TENANT_ID": (
            "channel-tenant-id"
        ),
        "TEAMS_HITL_APPROVER_AAD_OBJECT_ID": (
            "approver-object-id"
        ),
        "AZURE_SQL_SERVER": (
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        "AZURE_SQL_DATABASE": (
            "ai_support_platform_sbx"
        ),
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID": (
            SQL_IDENTITY
        ),
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
            VM_IDENTITY
        ),
    }


def test_main_has_exact_sync_surface():
    module = _module()

    main = getattr(
        module,
        "main",
        None,
    )

    assert callable(
        main
    )

    assert not inspect.iscoroutinefunction(
        main
    )

    signature = inspect.signature(
        main
    )

    assert tuple(
        signature.parameters
    ) == ()


def test_main_captures_snapshot_and_delegates_exactly(
    monkeypatch,
):
    module = _module()

    environment = {
        "KEY_A": "value-a",
        "KEY_B": "value-b",
    }

    monkeypatch.setattr(
        module.os,
        "environ",
        environment,
    )

    bootstrap = object()
    runtime_awaitable = object()

    observed = {}

    def fake_builder(
        actual_environment,
    ):
        observed[
            "environment"
        ] = actual_environment

        return bootstrap

    def fake_runtime(
        actual_bootstrap,
    ):
        observed[
            "runtime_bootstrap"
        ] = actual_bootstrap

        return runtime_awaitable

    def fake_asyncio_run(
        actual_awaitable,
    ):
        observed[
            "asyncio_awaitable"
        ] = actual_awaitable

    monkeypatch.setattr(
        module,
        "build_production_teams_host",
        fake_builder,
    )

    monkeypatch.setattr(
        module,
        "run_production_teams_host",
        fake_runtime,
    )

    monkeypatch.setattr(
        module.asyncio,
        "run",
        fake_asyncio_run,
    )

    module.main()

    assert observed[
        "environment"
    ] == environment

    assert observed[
        "environment"
    ] is not environment

    assert observed[
        "runtime_bootstrap"
    ] is bootstrap

    assert observed[
        "asyncio_awaitable"
    ] is runtime_awaitable


def test_main_preserves_three_identity_values_exactly(
    monkeypatch,
):
    module = _module()

    environment = (
        _valid_environment()
    )

    monkeypatch.setattr(
        module.os,
        "environ",
        environment,
    )

    observed = {}

    bootstrap = object()
    runtime_awaitable = object()

    def fake_builder(
        actual_environment,
    ):
        observed.update(
            actual_environment
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_production_teams_host",
        fake_builder,
    )

    monkeypatch.setattr(
        module,
        "run_production_teams_host",
        lambda actual_bootstrap: (
            runtime_awaitable
        ),
    )

    monkeypatch.setattr(
        module.asyncio,
        "run",
        lambda actual_awaitable: None,
    )

    module.main()

    assert observed[
        "MANAGED_IDENTITY_CLIENT_ID"
    ] == TEAMS_IDENTITY

    assert observed[
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
    ] == SQL_IDENTITY

    assert observed[
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID"
    ] == VM_IDENTITY


def test_client_secret_policy_reaches_governed_composition(
    monkeypatch,
):
    module = _module()

    environment = (
        _valid_environment()
    )

    environment[
        "CLIENT_SECRET"
    ] = "forbidden-secret"

    monkeypatch.setattr(
        module.os,
        "environ",
        environment,
    )

    runtime_called = []

    monkeypatch.setattr(
        module,
        "run_production_teams_host",
        lambda bootstrap: (
            runtime_called.append(
                bootstrap
            )
        ),
    )

    with pytest.raises(
        ValueError
    ):
        module.main()

    assert runtime_called == []


def test_main_has_single_global_environment_capture():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    assert lowered.count(
        "os.environ"
    ) == 1

    assert lowered.count(
        "asyncio.run"
    ) == 1

    assert (
        "dict(os.environ)"
        in lowered
    )

    required = (
        "build_production_teams_host",
        "run_production_teams_host",
    )

    for fragment in required:
        assert fragment in lowered


def test_main_does_not_reimplement_composition_runtime_or_resources():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    forbidden = (
        "os.getenv",
        "from_environment",
        "build_production_teams_host_settings",
        "build_production_teams_hitl_app",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
        "build_azure_vm_observation_credential",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "get_token(",
        "read_power_state(",
        "computemanagementclient",
        "virtual_machines",
        "instance_view(",
        "build_azure_sql_teams_hitl_persistence",
        "mssql_python",
        ".app.start(",
        "continuation_worker",
        "taskgroup",
        "stop_event",
        "client_secret",
        "sqlite",
        "cosmos",
        "servicebus",
        "foundry",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_module_has_explicit_process_entry_guard():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    compact = (
        source
        .replace(
            " ",
            "",
        )
        .replace(
            "'",
            '"',
        )
    )

    assert (
        'if__name__=="__main__":'
        in compact
    )

    assert "main()" in compact
