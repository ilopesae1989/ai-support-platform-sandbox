from __future__ import annotations

import importlib
import inspect
import textwrap
from types import SimpleNamespace

import pytest


MISSING = "F24_REVIEW_PRODUCTION_WIRING_NOT_IMPLEMENTED"


def _modules():
    base = importlib.import_module("src.channels.teams.bootstrap")
    prod_boot = importlib.import_module("src.channels.teams.production_bootstrap")
    prod_host = importlib.import_module("src.channels.teams.production_composition")
    root = importlib.import_module("src.production_composition")

    boot_factory = getattr(
        prod_boot,
        "build_production_teams_hitl_app_with_communication_and_incident_agents",
        None,
    )
    host_factory = getattr(
        prod_host,
        "build_production_teams_host_with_communication_and_incident_agents",
        None,
    )

    ready = (
        "review_runner" in inspect.signature(base.build_teams_hitl_app).parameters
        and callable(boot_factory)
        and "review_runner" in inspect.signature(boot_factory).parameters
        and callable(host_factory)
        and "review_runner" in inspect.signature(host_factory).parameters
        and "run_review" in inspect.getsource(root.build_production_application)
        and "review_runner" in inspect.getsource(root.build_production_application)
    )

    if not ready:
        pytest.fail(MISSING, pytrace=False)

    return base, prod_boot, prod_host, root


async def _communication_runner(request):
    raise AssertionError("communication runner must not execute during composition")


async def _review_runner(request):
    raise AssertionError("review runner must not execute during composition")


class _Membership:
    async def is_transitive_member(self, *, user_object_id, group_object_id):
        raise AssertionError("membership must not execute during composition")


def _managed_settings():
    from src.channels.teams.bootstrap import TeamsManagedIdentityAppSettings
    return TeamsManagedIdentityAppSettings(
        client_id="teams-app-client-id",
        managed_identity_client_id="system",
        bot_tenant_id="bot-tenant-id",
        teams_channel_tenant_id="channel-tenant-id",
        authorized_technicians_group_object_id="55555555-5555-4555-8555-555555555555",
    )


class _ConversationStore:
    def get_exact(self, **kwargs):
        raise AssertionError(
            "get_exact no debe ejecutarse durante bootstrap"
        )

    def upsert(self, *args, **kwargs):
        raise AssertionError(
            "upsert no debe ejecutarse durante bootstrap"
        )


def _persistence():
    from src.channels.teams.bootstrap import TeamsHitlPersistence
    return TeamsHitlPersistence(
        store=object(),
        checkpoint_storage=object(),
        operation_dispatch_ledger=object(),
        wait_recheck_consumption_ledger=object(),
        continuation_store=object(),
        conversation_store=_ConversationStore(),
    )


def test_base_bootstrap_exposes_optional_keyword_only_review_runner():
    base, _, _, _ = _modules()
    p = inspect.signature(base.build_teams_hitl_app).parameters["review_runner"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is None


@pytest.mark.asyncio
async def test_base_bootstrap_forwards_exact_review_runner_to_terminal_presenter(monkeypatch):
    base, _, _, _ = _modules()
    captured = {}

    class FakeApp:
        def __init__(self, **kwargs):
            captured["app"] = kwargs

        async def send(self, *args, **kwargs):
            raise AssertionError(
                "send no debe ejecutarse durante bootstrap"
            )

    async def fake_presenter(
        *,
        invocation,
        processed,
        outbound,
        communication_runner,
        review_runner,
    ):
        captured["presenter"] = (
            invocation,
            processed,
            outbound,
            communication_runner,
            review_runner,
        )
        return "presented"

    monkeypatch.setattr(base, "App", FakeApp)
    monkeypatch.setattr(base, "register_teams_approval_handler", lambda **kwargs: None)
    monkeypatch.setattr(base, "register_teams_conversation_handler", lambda **kwargs: None)
    monkeypatch.setattr(base, "notify_teams_incident_terminal_result", fake_presenter)

    bootstrap = base.build_teams_hitl_app(
        _managed_settings(),
        membership_checker=_Membership(),
        persistence=_persistence(),
        communication_runner=_communication_runner,
        review_runner=_review_runner,
    )

    notifier = bootstrap.continuation_worker._dependencies.terminal_notifier
    invocation = object()
    processed = object()
    result = await notifier(invocation=invocation, processed=processed)

    assert result == "presented"
    assert captured["presenter"][0] is invocation
    assert captured["presenter"][1] is processed
    assert captured["presenter"][3] is _communication_runner
    assert captured["presenter"][4] is _review_runner


def test_production_bootstrap_forwards_review_runner_without_invoking(monkeypatch):
    _, prod_boot, _, _ = _modules()
    sql = prod_boot.AzureSqlManagedIdentitySettings(
        server="example.database.windows.net",
        database="example",
    )

    class Reader:
        async def read_power_state(self, **kwargs):
            raise AssertionError("reader must not execute during composition")

    captured = {}
    monkeypatch.setattr(prod_boot, "build_azure_sql_teams_hitl_persistence", lambda settings: object())

    def fake_base(app_settings, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(prod_boot, "build_teams_hitl_app", fake_base)

    result = prod_boot.build_production_teams_hitl_app_with_communication_and_incident_agents(
        _managed_settings(),
        sql,
        membership_checker=object(),
        azure_vm_power_state_reader=Reader(),
        communication_runner=_communication_runner,
        review_runner=_review_runner,
        incident_agents=object(),
    )

    assert result is not None
    assert captured["communication_runner"] is _communication_runner
    assert captured["review_runner"] is _review_runner


def test_production_host_forwards_review_runner_without_invoking(monkeypatch):
    _, _, prod_host, _ = _modules()

    host_settings = SimpleNamespace(
        app_settings=SimpleNamespace(managed_identity_client_id="system"),
        azure_sql_settings=object(),
        authorization_identity_mappings=(),
    )

    monkeypatch.setattr(prod_host, "build_production_teams_host_settings", lambda env: host_settings)
    monkeypatch.setattr(prod_host, "build_managed_identity_graph_membership_client", lambda **kwargs: object())
    monkeypatch.setattr(prod_host, "build_azure_vm_observation_settings", lambda env: object())
    monkeypatch.setattr(prod_host, "build_azure_vm_observation_reader", lambda settings: object())

    captured = {}

    def fake_bootstrap(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        prod_host,
        "build_production_teams_hitl_app_with_communication_and_incident_agents",
        fake_bootstrap,
    )

    result = prod_host.build_production_teams_host_with_communication_and_incident_agents(
        {"EXPLICIT": "mapping"},
        communication_runner=_communication_runner,
        review_runner=_review_runner,
        incident_agents=object(),
    )

    assert result is not None
    assert captured["communication_runner"] is _communication_runner
    assert captured["review_runner"] is _review_runner


def test_application_root_uses_single_agents_bundle_for_both_runners(monkeypatch):
    _, _, _, root = _modules()

    class Agents:
        run_communication = staticmethod(_communication_runner)
        run_review = staticmethod(_review_runner)

    agents = Agents()
    settings = object()
    bootstrap = object()
    calls = []

    monkeypatch.setattr(
        root,
        "build_foundry_production_settings",
        lambda env: calls.append(("settings", env)) or settings,
    )
    monkeypatch.setattr(
        root,
        "build_foundry_production_agents",
        lambda actual: calls.append(("agents", actual)) or agents,
    )

    def fake_teams(env, *, communication_runner, review_runner, incident_agents):
        calls.append(("teams", env, communication_runner, review_runner, incident_agents))
        return bootstrap

    monkeypatch.setattr(
        root,
        "build_production_teams_host_with_communication_and_incident_agents",
        fake_teams,
    )

    result = root.build_production_application({"EXPLICIT": "mapping"})
    assert result is bootstrap
    assert calls == [
        ("settings", {"EXPLICIT": "mapping"}),
        ("agents", settings),
        ("teams", {"EXPLICIT": "mapping"}, agents.run_communication, agents.run_review, agents),
    ]


@pytest.mark.parametrize("missing", ["run_communication", "run_review"])
def test_application_root_fails_closed_if_required_runner_missing(monkeypatch, missing):
    _, _, _, root = _modules()

    class Agents:
        pass

    agents = Agents()
    if missing != "run_communication":
        agents.run_communication = _communication_runner
    if missing != "run_review":
        agents.run_review = _review_runner

    monkeypatch.setattr(root, "build_foundry_production_settings", lambda env: object())
    monkeypatch.setattr(root, "build_foundry_production_agents", lambda settings: agents)

    calls = []
    monkeypatch.setattr(
        root,
        "build_production_teams_host_with_communication_and_incident_agents",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(TypeError):
        root.build_production_application({})

    assert calls == []


def test_application_root_does_not_invoke_cognitive_runners_during_composition(monkeypatch):
    _, _, _, root = _modules()

    class Agents:
        run_communication = staticmethod(_communication_runner)
        run_review = staticmethod(_review_runner)

    monkeypatch.setattr(root, "build_foundry_production_settings", lambda env: object())
    monkeypatch.setattr(root, "build_foundry_production_agents", lambda settings: Agents())
    monkeypatch.setattr(
        root,
        "build_production_teams_host_with_communication_and_incident_agents",
        lambda *args, **kwargs: object(),
    )

    assert root.build_production_application({}) is not None


def test_layers_below_application_root_remain_foundry_agnostic():
    base, prod_boot, prod_host, _ = _modules()

    for module in (base, prod_boot, prod_host):
        source = textwrap.dedent(inspect.getsource(module)).casefold()
        for fragment in (
            "foundryagents",
            "production_communication_runner",
            "build_foundry_production",
            "managedidentitycredential",
            "azureclicredential",
            "defaultazurecredential",
            "get_token(",
            "run_review(",
            "review_runner(",
        ):
            assert fragment not in source
