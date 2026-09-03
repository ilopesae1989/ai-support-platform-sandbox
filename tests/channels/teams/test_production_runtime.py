from __future__ import annotations

import asyncio
import importlib
import inspect
import textwrap

import pytest

from src.channels.teams.bootstrap import (
    TeamsHitlBootstrap,
)


TARGET_MODULE = (
    "src.channels.teams.production_runtime"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _bootstrap(
    *,
    app,
    continuation_worker,
):
    bootstrap = object.__new__(
        TeamsHitlBootstrap
    )

    object.__setattr__(
        bootstrap,
        "app",
        app,
    )

    object.__setattr__(
        bootstrap,
        "continuation_worker",
        continuation_worker,
    )

    return bootstrap


def test_runtime_has_exact_async_surface():
    module = _module()

    runner = getattr(
        module,
        "run_production_teams_host",
        None,
    )

    assert callable(
        runner
    )

    assert inspect.iscoroutinefunction(
        runner
    )

    signature = inspect.signature(
        runner
    )

    assert tuple(
        signature.parameters
    ) == (
        "bootstrap",
    )


def test_runtime_rejects_wrong_bootstrap_type():
    module = _module()

    for invalid_bootstrap in (
        None,
        object(),
        {},
        "bootstrap",
    ):
        with pytest.raises(
            TypeError
        ):
            asyncio.run(
                module.run_production_teams_host(
                    invalid_bootstrap
                )
            )


def test_runtime_starts_app_and_worker_and_signals_completion():
    module = _module()

    app_start_calls = []
    worker_stop_events = []
    worker_completed = []

    class FakeApp:
        async def start(
            self,
        ):
            app_start_calls.append(
                "start"
            )

    class FakeWorker:
        async def run(
            self,
            *,
            stop_event,
        ):
            worker_stop_events.append(
                stop_event
            )

            await stop_event.wait()

            worker_completed.append(
                True
            )

    bootstrap = _bootstrap(
        app=FakeApp(),
        continuation_worker=FakeWorker(),
    )

    asyncio.run(
        module.run_production_teams_host(
            bootstrap
        )
    )

    assert app_start_calls == [
        "start",
    ]

    assert len(
        worker_stop_events
    ) == 1

    assert worker_stop_events[
        0
    ].is_set()

    assert worker_completed == [
        True,
    ]


def test_runtime_signals_worker_when_app_fails():
    module = _module()

    observed = {
        "worker_started": False,
        "worker_released": False,
    }

    class FailingApp:
        async def start(
            self,
        ):
            raise RuntimeError(
                "app-start-failed"
            )

    class FakeWorker:
        async def run(
            self,
            *,
            stop_event,
        ):
            observed[
                "worker_started"
            ] = True

            await stop_event.wait()

            observed[
                "worker_released"
            ] = True

    bootstrap = _bootstrap(
        app=FailingApp(),
        continuation_worker=FakeWorker(),
    )

    with pytest.raises(
        ExceptionGroup
    ) as captured:
        asyncio.run(
            module.run_production_teams_host(
                bootstrap
            )
        )

    assert observed == {
        "worker_started": True,
        "worker_released": True,
    }

    assert any(
        isinstance(
            error,
            RuntimeError,
        )
        and str(
            error
        ) == "app-start-failed"
        for error in captured.value.exceptions
    )


def test_runtime_uses_task_group_and_finally_stop_signal():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    required = (
        "asyncio.event",
        "asyncio.taskgroup",
        "bootstrap.app.start",
        "bootstrap.continuation_worker.run",
        "stop_event.set",
        "finally",
    )

    for fragment in required:
        assert fragment in lowered


def test_runtime_has_no_composition_environment_or_resource_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.lower()

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "build_production_teams_host(",
        "build_production_teams_host_settings",
        "build_production_teams_hitl_app",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
        "managedidentitycredential",
        "defaultazurecredential",
        "azureclicredential",
        "get_token(",
        "read_power_state(",
        "computemanagementclient",
        "virtual_machines",
        "instance_view(",
        "mssql_python",
        "asyncio.run",
        "client_secret",
        "sqlite",
        "cosmos",
        "servicebus",
        "foundry",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered
