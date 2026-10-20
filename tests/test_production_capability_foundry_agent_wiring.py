"""R22A: production composition must carry an explicit Foundry READ selector.

Only composition is exercised. Azure, SQL, credential factories, Teams App and
workers are replaced at their dependency boundaries. No workflow/agent is run.
Raising a named AssertionError describes a missing contract, never an import
error converted into a RED. This file must also remain useful after the GREEN.
"""
from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest

PARAM = "capability_foundry_agent_binding_registry"
CAPABILITY = "azure.resource_group.list"
MISSING = object()
LAYERS = ("application", "teams_host", "production_bootstrap", "teams_bootstrap")


def _contract(condition, reason):
    if not condition:
        raise AssertionError(reason)


def _require_port(factory, layer):
    parameter = inspect.signature(factory).parameters.get(PARAM)
    _contract(parameter is not None, "R22A_MISSING_SELECTOR_PORT:" + layer)
    _contract(parameter.kind is inspect.Parameter.KEYWORD_ONLY,
              "R22A_SELECTOR_PORT_NOT_KEYWORD_ONLY:" + layer)


def _never(*args, **kwargs):
    raise AssertionError("R22A_FORBIDDEN_PROVIDER_OR_OPERATION_INVOCATION")


def _registry(populated=False):
    from src.agents.catalog import AgentKey, FoundryAgentDefinition
    from src.workflows.incident_resolution.capability_foundry_agent_binding import (
        CapabilityFoundryAgentBinding, CapabilityFoundryAgentBindingRegistry,
    )
    from src.workflows.incident_resolution.capability_registry import build_default_capability_registry
    from src.workflows.incident_resolution.azure_read_tool_authority import (
        build_default_azure_read_tool_authority_registry,
    )
    if not populated:
        return CapabilityFoundryAgentBindingRegistry(bindings=())
    binding = CapabilityFoundryAgentBinding(
        capability=build_default_capability_registry().get(CAPABILITY),
        read_tool_authority=build_default_azure_read_tool_authority_registry().get(CAPABILITY),
        agent_definition=FoundryAgentDefinition(
            key=AgentKey.AZURE_OPERATIONS,
            name="agent-synthetic-r22a-rg-read", version="1",
        ),
        require_approval="always",
    )
    return CapabilityFoundryAgentBindingRegistry(bindings=(binding,))


@pytest.fixture
def rig(monkeypatch):
    # Real modules, not extracted/recompiled functions or replacement modules.
    app = importlib.import_module("src.production_composition")
    host = importlib.import_module("src.channels.teams.production_composition")
    prod = importlib.import_module("src.channels.teams.production_bootstrap")
    base = importlib.import_module("src.channels.teams.bootstrap")
    sql = importlib.import_module("src.channels.teams.azure_sql_persistence")
    effects, workflow_calls = [], []
    environment = {"R22A_SYNTHETIC_CONFIG": "explicit-mapping"}
    settings = base.TeamsManagedIdentityAppSettings(
        client_id="11111111-1111-4111-8111-111111111111",
        managed_identity_client_id="system",
        bot_tenant_id="22222222-2222-4222-8222-222222222222",
        teams_channel_tenant_id="33333333-3333-4333-8333-333333333333",
        authorized_technicians_group_object_id="44444444-4444-4444-8444-444444444444",
    )
    sql_settings = prod.AzureSqlManagedIdentitySettings(
        server="synthetic-r22a.database.windows.net", database="synthetic_r22a",
    )
    persistence = sql.AzureSqlTeamsHitlPersistence(**{
        item.name: object() for item in fields(sql.AzureSqlTeamsHitlPersistence)
    })
    agents = SimpleNamespace(run_communication=_never, run_review=_never)
    reader = SimpleNamespace(read_power_state=_never)
    member = SimpleNamespace(is_transitive_member=_never)
    host_settings = SimpleNamespace(
        app_settings=settings, azure_sql_settings=sql_settings,
        authorization_identity_mappings=(),
    )

    def returns(name, value):
        def fake(*args, **kwargs):
            effects.append(name)
            return value
        return fake

    monkeypatch.setattr(app, "build_foundry_production_settings", returns("foundry_settings", object()))
    monkeypatch.setattr(app, "build_foundry_production_agents", returns("agents", agents))
    monkeypatch.setattr(app, "build_foundry_production_communication_runner", _never)
    monkeypatch.setattr(app, "build_production_teams_host_with_communication", _never)
    monkeypatch.setattr(host, "build_production_teams_host_settings", returns("host_settings", host_settings))
    monkeypatch.setattr(host, "build_managed_identity_graph_membership_client", returns("membership", member))
    monkeypatch.setattr(host, "build_azure_vm_observation_settings", returns("observation_settings", object()))
    monkeypatch.setattr(host, "build_azure_vm_observation_reader", returns("reader", reader))
    monkeypatch.setattr(host, "build_exact_teams_authorization_object_id_resolver", _never)
    monkeypatch.setattr(prod, "build_azure_sql_teams_hitl_persistence", returns("persistence", persistence))
    monkeypatch.setattr(base, "build_local_teams_hitl_persistence", _never)
    # Transport/worker objects are inert. The composition functions and their
    # workflow_factory closure are real; no registration starts a server.
    monkeypatch.setattr(base, "App", returns("app", SimpleNamespace(start=_never)))
    for name in ("TeamsApprovalHandlerDependencies", "TeamsConversationHandlerDependencies",
                 "TeamsOutboundDependencies", "IncidentContinuationWorkerDependencies"):
        monkeypatch.setattr(base, name, lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(base, "IncidentContinuationWorker",
                        lambda dependencies: SimpleNamespace(dependencies=dependencies, run=_never))
    monkeypatch.setattr(base, "register_teams_approval_handler", returns("approval_registration", None))
    monkeypatch.setattr(base, "register_teams_conversation_handler", returns("conversation_registration", None))
    monkeypatch.setattr(base, "process_authorized_teams_incident_approval", _never)
    monkeypatch.setattr(base, "notify_teams_incident_terminal_result", _never)

    def workflow_leaf(*, operation_dispatch_ledger, wait_recheck_consumption_ledger,
                      azure_vm_power_state_reader, agents=None,
                      capability_foundry_agent_binding_registry=MISSING):
        row = {PARAM: capability_foundry_agent_binding_registry,
               "dispatch": operation_dispatch_ledger,
               "wait": wait_recheck_consumption_ledger,
               "reader": azure_vm_power_state_reader, "agents": agents}
        workflow_calls.append(row)
        return object()

    monkeypatch.setattr(base, "build_incident_resolution_workflow", workflow_leaf)
    factories = {
        "application": app.build_production_application,
        "teams_host": host.build_production_teams_host_with_communication_and_incident_agents,
        "production_bootstrap": prod.build_production_teams_hitl_app_with_communication_and_incident_agents,
        "teams_bootstrap": base.build_teams_hitl_app,
    }

    def invoke(layer, registry=MISSING):
        kwargs = {} if registry is MISSING else {PARAM: registry}
        if layer == "application":
            return factories[layer](environment, **kwargs)
        if layer == "teams_host":
            return factories[layer](environment, communication_runner=_never,
                                    review_runner=_never, incident_agents=agents, **kwargs)
        if layer == "production_bootstrap":
            return factories[layer](settings, sql_settings, membership_checker=member,
                                    azure_vm_power_state_reader=reader,
                                    communication_runner=_never, review_runner=_never,
                                    incident_agents=agents, **kwargs)
        return factories[layer](settings, membership_checker=member, persistence=persistence,
                                azure_vm_power_state_reader=reader,
                                communication_runner=_never, review_runner=_never,
                                incident_agents=agents, **kwargs)

    # These spies have explicit known interfaces, not a **kwargs catch-all for
    # the selector's downstream port. Missing values remain MISSING, not None.
    def isolate_next_layer(layer):
        captures = []
        result = base.TeamsHitlBootstrap(**{
            item.name: object() for item in fields(base.TeamsHitlBootstrap)
        })

        def app_leaf(actual_environment, *, communication_runner, incident_agents,
                     review_runner=None, capability_foundry_agent_binding_registry=MISSING):
            captures.append(capability_foundry_agent_binding_registry)
            assert actual_environment is environment
            assert incident_agents is agents
            assert communication_runner is _never and review_runner is _never
            return result

        def host_leaf(app_settings, azure_sql_settings, *, membership_checker,
                      azure_vm_power_state_reader, communication_runner, incident_agents,
                      review_runner=None, operator_identity_resolver=None,
                      capability_foundry_agent_binding_registry=MISSING):
            captures.append(capability_foundry_agent_binding_registry)
            assert app_settings is settings and azure_sql_settings is sql_settings
            assert membership_checker is member and azure_vm_power_state_reader is reader
            assert incident_agents is agents
            return result

        def prod_leaf(actual_settings, *, membership_checker, persistence,
                      azure_vm_power_state_reader, communication_runner=None,
                      review_runner=None, incident_agents=None, operator_identity_resolver=None,
                      capability_foundry_agent_binding_registry=MISSING):
            captures.append(capability_foundry_agent_binding_registry)
            assert actual_settings is settings
            assert membership_checker is member and azure_vm_power_state_reader is reader
            assert incident_agents is agents
            return result

        if layer == "application":
            monkeypatch.setattr(app, "build_production_teams_host_with_communication_and_incident_agents", app_leaf)
        elif layer == "teams_host":
            monkeypatch.setattr(host, "build_production_teams_hitl_app_with_communication_and_incident_agents", host_leaf)
        elif layer == "production_bootstrap":
            monkeypatch.setattr(prod, "build_teams_hitl_app", prod_leaf)
        else:
            raise AssertionError("R22A_INVALID_SPY_LAYER")
        return captures

    return SimpleNamespace(
        app=app, host=host, prod=prod, base=base, effects=effects,
        workflow_calls=workflow_calls, environment=environment,
        persistence=persistence, agents=agents, reader=reader,
        factories=factories, invoke=invoke, isolate_next_layer=isolate_next_layer,
    )


def _both_factories(bootstrap, rig):
    human = bootstrap.dependencies.workflow_factory
    worker = bootstrap.continuation_worker.dependencies.workflow_factory
    assert human is worker  # existing invariant; not a new authority path
    assert rig.workflow_calls == []
    first, second = human(), worker()  # build only, never workflow.run()
    assert first is not second
    assert len(rig.workflow_calls) == 2
    for row in rig.workflow_calls:
        assert row["dispatch"] is rig.persistence.operation_dispatch_ledger
        assert row["wait"] is rig.persistence.wait_recheck_consumption_ledger
        assert row["reader"] is rig.reader
        assert row["agents"] is rig.agents
    return [row[PARAM] for row in rig.workflow_calls]


@pytest.mark.parametrize("layer", LAYERS, ids=LAYERS)
@pytest.mark.parametrize("populated", (False, True), ids=("empty", "populated"))
def test_explicit_registry_crosses_one_layer(rig, layer, populated):
    registry = _registry(populated)
    _require_port(rig.factories[layer], layer)
    if layer == "teams_bootstrap":
        captures = _both_factories(rig.invoke(layer, registry), rig)
    else:
        captures = rig.isolate_next_layer(layer)
        rig.invoke(layer, registry)
    _contract(bool(captures) and all(item is registry for item in captures),
              "R22A_REGISTRY_IDENTITY_NOT_PROPAGATED:" + layer)
    assert registry.count() == int(populated)


@pytest.mark.parametrize("layer", LAYERS, ids=LAYERS)
def test_invalid_registry_rejected_before_dependencies(rig, layer):
    _require_port(rig.factories[layer], layer)
    with pytest.raises(TypeError, match=PARAM):
        rig.invoke(layer, object())
    assert rig.effects == []
    assert rig.workflow_calls == []


def test_application_default_is_explicit_empty(rig):
    from src.workflows.incident_resolution.capability_foundry_agent_binding import (
        CapabilityFoundryAgentBindingRegistry, CapabilityFoundryAgentBindingRegistryError,
    )
    captures = rig.isolate_next_layer("application")
    before = dict(rig.environment)
    rig.invoke("application")
    rig.invoke("application")
    assert rig.environment == before
    assert len(captures) == 2
    _contract(all(isinstance(item, CapabilityFoundryAgentBindingRegistry) for item in captures),
              "R22A_ROOT_DEFAULT_REGISTRY_ABSENT")
    assert captures[0] is not captures[1]  # no shared default instance
    for registry in captures:
        assert registry.count() == 0
        with pytest.raises(CapabilityFoundryAgentBindingRegistryError):
            registry.get(CAPABILITY)


def test_end_to_end_default_reaches_both_factories(rig):
    from src.workflows.incident_resolution.capability_foundry_agent_binding import (
        CapabilityFoundryAgentBindingRegistry,
    )
    bootstrap = rig.invoke("application")
    captures = _both_factories(bootstrap, rig)
    _contract(all(isinstance(item, CapabilityFoundryAgentBindingRegistry) for item in captures),
              "R22A_DEFAULT_SELECTOR_LOST_BEFORE_WORKFLOW")
    assert captures[0] is captures[1] and captures[0].count() == 0
    assert bootstrap.session_store is rig.persistence.session_store


def test_end_to_end_explicit_reaches_both_factories(rig):
    _require_port(rig.factories["application"], "application")
    registry = _registry(True)
    captures = _both_factories(rig.invoke("application", registry), rig)
    _contract(all(item is registry for item in captures), "R22A_EXPLICIT_SELECTOR_LOST_BEFORE_WORKFLOW")
    assert registry.count() == 1


def test_guard_default_procedures_remain_vm_start_only():
    manifest = Path(__file__).resolve().parents[1] / (
        "src/workflows/incident_resolution/procedure_capability_bindings.v1.json"
    )
    records = json.loads(manifest.read_text(encoding="utf-8"))["bindings"]
    assert len(records) == 3
    assert all(row["capability_id"] == "azure.vm.start" for row in records)
    assert all(row["procedure_version"] == "1.0" for row in records)


def test_guard_vm_start_catalog_is_unchanged(monkeypatch):
    from src.agents.catalog import AgentKey, build_agent_catalog
    monkeypatch.delenv("FOUNDRY_AGENT_AZURE_OPERATIONS_VERSION", raising=False)
    selected = build_agent_catalog()[AgentKey.AZURE_OPERATIONS]
    assert selected.name == "agent-azure-operations-sbx"
    assert selected.version == "13"


def test_guard_explicit_registry_resolution_is_exact():
    from src.workflows.incident_resolution.capability_foundry_agent_binding import (
        CapabilityFoundryAgentBindingRegistryError,
    )
    registry = _registry(True)
    binding = registry.get(CAPABILITY)
    assert binding.require_approval == "always"
    assert binding.agent_definition.name == "agent-synthetic-r22a-rg-read"
    for invalid in ("Azure.Resource_Group.List", CAPABILITY + " ", "azure.vm.start"):
        with pytest.raises(CapabilityFoundryAgentBindingRegistryError):
            registry.get(invalid)
