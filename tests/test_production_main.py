from __future__ import annotations

import ast
import importlib
import inspect
import textwrap

import pytest


TARGET_MODULE = (
    "src.production_main"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def test_application_main_has_exact_sync_surface():
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


def test_application_main_captures_environment_snapshot_and_delegates_exactly(
    monkeypatch,
):
    module = _module()

    environment = {
        "CLIENT_ID": "teams-client",
        "FOUNDRY_PROJECT_ENDPOINT": (
            "https://example.invalid/project"
        ),
        "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID": (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        ),
    }

    monkeypatch.setattr(
        module.os,
        "environ",
        environment,
    )

    bootstrap = object()
    runtime_awaitable = object()

    observed = {}

    def fake_application_builder(
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
        "build_production_application",
        fake_application_builder,
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


def test_application_main_preserves_environment_values_without_interpretation(
    monkeypatch,
):
    module = _module()

    environment = {
        "MANAGED_IDENTITY_CLIENT_ID": (
            "11111111-1111-4111-8111-111111111111"
        ),
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID": (
            "22222222-2222-4222-8222-222222222222"
        ),
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
            "33333333-3333-4333-8333-333333333333"
        ),
        "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID": (
            "44444444-4444-4444-8444-444444444444"
        ),
        "FOUNDRY_PROJECT_ENDPOINT": (
            "https://example.invalid/project"
        ),
    }

    monkeypatch.setattr(
        module.os,
        "environ",
        environment,
    )

    captured = {}

    bootstrap = object()
    runtime_awaitable = object()

    def fake_application_builder(
        actual_environment,
    ):
        captured.update(
            actual_environment
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_production_application",
        fake_application_builder,
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

    assert captured == environment


def test_application_composition_failure_prevents_runtime_start(
    monkeypatch,
):
    module = _module()

    monkeypatch.setattr(
        module.os,
        "environ",
        {
            "EXPLICIT": "mapping",
        },
    )

    runtime_calls = []
    asyncio_calls = []

    def failing_application_builder(
        environment,
    ):
        raise ValueError(
            "composition failed closed"
        )

    monkeypatch.setattr(
        module,
        "build_production_application",
        failing_application_builder,
    )

    monkeypatch.setattr(
        module,
        "run_production_teams_host",
        lambda bootstrap: (
            runtime_calls.append(
                bootstrap
            )
        ),
    )

    monkeypatch.setattr(
        module.asyncio,
        "run",
        lambda awaitable: (
            asyncio_calls.append(
                awaitable
            )
        ),
    )

    with pytest.raises(
        ValueError
    ):
        module.main()

    assert runtime_calls == []
    assert asyncio_calls == []


def test_application_main_has_exact_process_delegation_contract():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    tree = ast.parse(
        source
    )

    calls = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Name,
        ):
            name = node.func.id

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            name = node.func.attr

        else:
            name = None

        if name is not None:
            calls.append(
                name
            )

    assert calls.count(
        "dict"
    ) == 1

    assert calls.count(
        "build_production_application"
    ) == 1

    assert calls.count(
        "run_production_teams_host"
    ) == 1

    assert calls.count(
        "run"
    ) == 1

    lowered = source.casefold()

    assert lowered.count(
        "os.environ"
    ) == 1

    assert lowered.count(
        "asyncio.run"
    ) == 1


def test_application_main_does_not_reimplement_composition_or_operational_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.casefold()

    required = (
        "build_production_application",
        "run_production_teams_host",
        "dict(",
        "os.environ",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "build_foundry_production_settings",
        "build_foundry_production_communication_runner",
        "build_foundry_production_credential",
        "foundryagents",
        "managedidentitycredential",
        "azureclicredential",
        "defaultazurecredential",
        "get_token(",
        "run_communication",
        "build_production_teams_host",
        "build_production_teams_hitl_app",
        "build_teams_hitl_app",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
        "build_azure_sql_teams_hitl_persistence",
        "read_power_state(",
        "computemanagementclient",
        "mssql_python",
        "create_session",
        "agentsession",
        "session=",
        "tools=",
        "mcp",
        "client_secret",
        "sqlite",
        "cosmos",
        "servicebus",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_application_main_has_explicit_process_entry_guard():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    tree = ast.parse(
        source
    )

    guards = []

    for node in tree.body:
        if not isinstance(
            node,
            ast.If,
        ):
            continue

        test = node.test

        if not isinstance(
            test,
            ast.Compare,
        ):
            continue

        if not (
            isinstance(
                test.left,
                ast.Name,
            )
            and test.left.id == "__name__"
        ):
            continue

        values = [
            comparator.value
            for comparator in test.comparators
            if isinstance(
                comparator,
                ast.Constant,
            )
        ]

        if "__main__" not in values:
            continue

        guards.append(
            node
        )

    assert len(
        guards
    ) == 1

    guard = guards[0]

    main_calls = [
        node
        for node in ast.walk(
            guard
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id == "main"
        )
    ]

    assert len(
        main_calls
    ) == 1