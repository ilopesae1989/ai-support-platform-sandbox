import asyncio
from dataclasses import fields
from threading import Event
from types import SimpleNamespace

import pytest

from src.channels.teams import main, production_composition
from src.channels.teams.bootstrap import TeamsHitlBootstrap
from src.channels.teams.production_bootstrap import ProductionTeamsHitlBootstrap
from src.channels.teams.production_runtime import run_production_teams_host
from src.channels.teams.recovery_composition import attach_continuation_recovery
from src.runtime.incident_continuation_recovery_runner import ContinuationRecoveryPolicy as Policy
from tests.config.test_continuation_recovery import ENABLED, environment
from tests.runtime.test_incident_continuation_recovery_runner import Store, runner


def bootstrap(cls=TeamsHitlBootstrap, **overrides):
    values = {f.name: object() for f in fields(cls) if f.name != "continuation_recovery_runner"}
    return cls(**(values | overrides))


@pytest.mark.parametrize("productive", [False, True])
def test_attachment_uses_existing_persistence_and_preserves_subclass(productive):
    store = Store()
    host = bootstrap(ProductionTeamsHitlBootstrap if productive else TeamsHitlBootstrap,
                     continuation_store=store)
    assert attach_continuation_recovery(host, None) is host
    attached = attach_continuation_recovery(host, Policy(300, 60, 10, 2))
    assert type(attached) is type(host)
    for f in fields(host):
        if f.name != "continuation_recovery_runner":
            assert getattr(attached, f.name) is getattr(host, f.name)
    service = attached.continuation_recovery_runner._recovery
    assert service._store is host.continuation_store and service._approval_store is host.store
    assert not store.selections and not store.transitions
    with pytest.raises(ValueError):
        attach_continuation_recovery(attached, Policy(300, 60, 10, 2))


def test_opt_in_rejects_unsupported_adapter_and_wrong_bootstrap():
    for host in (object(), bootstrap()):
        with pytest.raises(TypeError):
            attach_continuation_recovery(host, Policy(300, 60, 10, 2))


def test_productive_sql_pair_is_attached_without_opening_a_connection():
    from src.channels.teams.continuation_payload import TEAMS_CONTINUATION_CODEC
    from src.persistence.azure_sql.incident_continuation_store import AzureSqlIncidentContinuationStore
    from src.persistence.azure_sql.pending_approval_store import AzureSqlPendingApprovalStore
    def factory():
        pytest.fail("SQL connection opened during composition")
    queue = AzureSqlIncidentContinuationStore(connection_factory=factory, payload_codec=TEAMS_CONTINUATION_CODEC)
    approval = AzureSqlPendingApprovalStore(connection_factory=factory)
    host = bootstrap(ProductionTeamsHitlBootstrap, continuation_store=queue, store=approval)
    attached = attach_continuation_recovery(host, Policy(300, 60, 10, 2))
    assert attached.continuation_recovery_runner._recovery._store is queue
    assert attached.continuation_recovery_runner._recovery._approval_store is approval


def test_composed_sqlite_host_uses_the_workers_exact_pair(monkeypatch, tmp_path):
    import src.channels.teams.bootstrap as module
    from tests.channels.teams.test_bootstrap_full_incident_composition import (
        create_settings, install_future_component_fakes, FakeMembershipChecker,
    )
    install_future_component_fakes(monkeypatch=monkeypatch)
    host = module.build_teams_hitl_app(create_settings(tmp_path), membership_checker=FakeMembershipChecker())
    attached = attach_continuation_recovery(host, Policy(300, 60, 10, 2))
    service = attached.continuation_recovery_runner._recovery
    dependencies = host.continuation_worker._dependencies
    assert service._store is dependencies.continuation_store
    assert service._approval_store is dependencies.approval_store


FACTORIES = [
    ("build_production_teams_host", "build_production_teams_hitl_app", {}),
    ("build_production_teams_host_with_communication", "build_production_teams_hitl_app_with_communication",
     dict(communication_runner=lambda: None)),
    ("build_production_teams_host_with_communication_and_incident_agents",
     "build_production_teams_hitl_app_with_communication_and_incident_agents",
     dict(communication_runner=lambda: None, incident_agents=object())),
]


@pytest.mark.parametrize("factory,builder,kwargs", FACTORIES)
@pytest.mark.parametrize("mapped", [False, True])
def test_all_productive_roots_attach_after_composition_without_connecting(monkeypatch, factory, builder, kwargs, mapped):
    module = production_composition
    settings = SimpleNamespace(app_settings=SimpleNamespace(managed_identity_client_id="system"),
                               azure_sql_settings=object(), authorization_identity_mappings=(object(),) if mapped else ())
    host = bootstrap(ProductionTeamsHitlBootstrap, continuation_store=Store())
    monkeypatch.setattr(module, "build_production_teams_host_settings", lambda env: settings)
    monkeypatch.setattr(module, "build_managed_identity_graph_membership_client", lambda **kw: object())
    monkeypatch.setattr(module, "build_azure_vm_observation_settings", lambda env: object())
    monkeypatch.setattr(module, "build_azure_vm_observation_reader", lambda config: object())
    monkeypatch.setattr(module, "build_exact_teams_authorization_object_id_resolver", lambda **kw: object())
    calls = []
    def build(*args, **options):
        calls.append(options)
        return host
    monkeypatch.setattr(module, builder, build)
    attached = getattr(module, factory)(environment(ENABLED), **kwargs)
    assert attached.continuation_recovery_runner is not None
    assert attached.session_store is host.session_store
    assert bool("operator_identity_resolver" in calls[0]) == mapped
    assert getattr(module, factory)({}, **kwargs) is host
    assert not host.continuation_store.selections


@pytest.mark.parametrize("factory,builder,kwargs", FACTORIES)
def test_bad_policy_fails_before_productive_provider_construction(monkeypatch, factory, builder, kwargs):
    monkeypatch.setattr(production_composition, "build_production_teams_host_settings",
                        lambda env: pytest.fail("provider configuration reached"))
    with pytest.raises(ValueError):
        getattr(production_composition, factory)({"CONTINUATION_RECOVERY_JSON": "bad"}, **kwargs)


def test_bad_policy_fails_before_foundry_construction(monkeypatch):
    import src.production_composition as root
    monkeypatch.setattr(root, "build_foundry_deployment_configuration",
                        lambda env: pytest.fail("Foundry construction reached"))
    with pytest.raises(ValueError):
        root.build_production_application({"CONTINUATION_RECOVERY_JSON": "bad"})


@pytest.mark.asyncio
async def test_bad_policy_fails_before_local_provider_construction(monkeypatch):
    monkeypatch.setenv("CONTINUATION_RECOVERY_JSON", "bad")
    monkeypatch.setattr(main.TeamsHitlSettings, "from_environment",
                        lambda: pytest.fail("local configuration reached"))
    with pytest.raises(ValueError):
        await main.run_teams_hitl_app()


def wire_local(monkeypatch, host):
    monkeypatch.setattr(main.TeamsHitlSettings, "from_environment",
                        lambda: SimpleNamespace(teams_channel_tenant_id="channel"))
    monkeypatch.setattr(main, "build_local_teams_membership_checker", lambda **kw: object())
    monkeypatch.setattr(main, "build_local_azure_vm_power_state_reader", lambda: object())
    monkeypatch.setattr(main, "build_teams_hitl_app", lambda *a, **kw: host)


@pytest.mark.asyncio
@pytest.mark.parametrize("local", [False, True])
async def test_host_schedules_recovery_and_worker_with_same_stop_event(monkeypatch, local):
    observed = []
    ready = asyncio.Event()
    class Participant:
        async def run(self, *, stop_event):
            observed.append(stop_event)
            if len(observed) == 2:
                ready.set()
            await stop_event.wait()
    class App:
        async def start(self):
            await ready.wait()
    host = bootstrap(app=App(), continuation_worker=Participant(), continuation_recovery_runner=Participant())
    if local:
        monkeypatch.delenv("CONTINUATION_RECOVERY_JSON", raising=False)
        wire_local(monkeypatch, host)
        await asyncio.wait_for(main.run_teams_hitl_app(), 3)
    else:
        await asyncio.wait_for(run_production_teams_host(host), 3)
    assert len(observed) == 2 and observed[0] is observed[1] and observed[0].is_set()


@pytest.mark.asyncio
async def test_local_opt_in_is_attached_to_real_bootstrap(monkeypatch):
    policy = environment(ENABLED)["CONTINUATION_RECOVERY_JSON"]
    monkeypatch.setenv("CONTINUATION_RECOVERY_JSON", policy)
    store = Store()
    selected = asyncio.Event()
    loop = asyncio.get_running_loop()
    def select(**kw):
        loop.call_soon_threadsafe(selected.set)
        return ()
    store.select = select
    class App:
        async def start(self):
            await selected.wait()
    class Worker:
        async def run(self, *, stop_event):
            await stop_event.wait()
    wire_local(monkeypatch, bootstrap(app=App(), continuation_worker=Worker(), continuation_store=store))
    await asyncio.wait_for(main.run_teams_hitl_app(), 3)
    assert len(store.selections) == 1 and store.selections[0]["limit"] == 25


@pytest.mark.asyncio
async def test_uncertain_recovery_halts_itself_without_restarting_or_killing_host():
    store = Store()
    def fail(**kw):
        raise OSError("provider failed")
    store.select = fail
    recovery = runner(store)
    working = asyncio.Event()
    class App:
        async def start(self):
            await working.wait()
            while recovery.last_cycle is None:
                await asyncio.sleep(0)
            assert recovery.halted and len(store.selections) == 1
    class Worker:
        async def run(self, *, stop_event):
            working.set()
            await stop_event.wait()
    await asyncio.wait_for(run_production_teams_host(bootstrap(
        app=App(), continuation_worker=Worker(), continuation_recovery_runner=recovery)), 3)
    assert len(store.selections) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["app", "worker", "external"])
async def test_host_failure_or_cancellation_drains_recovery_before_exit(failure):
    store, release, started = Store(), Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    finished = Event()
    def select(**kw):
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        finished.set()
        return ()
    store.select = select
    task = runner(store)
    class App:
        async def start(self):
            await started.wait()
            if failure == "app":
                raise ValueError("app failed")
            await asyncio.Event().wait()
    class Worker:
        async def run(self, *, stop_event):
            await started.wait()
            if failure == "worker":
                raise ValueError("worker failed")
            await stop_event.wait()
    host = bootstrap(app=App(), continuation_worker=Worker(), continuation_recovery_runner=task)
    running = asyncio.create_task(run_production_teams_host(host))
    try:
        await asyncio.wait_for(started.wait(), 3)
        if failure == "external":
            running.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not running.done() and not finished.is_set()
        release.set()
        if failure == "external":
            with pytest.raises(asyncio.CancelledError):
                await running
        else:
            with pytest.raises(ExceptionGroup) as error:
                await running
            assert any(str(e) == failure + " failed" for e in error.value.exceptions)
        assert finished.is_set() and len(store.selections) == 1
    finally:
        release.set()
        if not running.done():
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
