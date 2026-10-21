"""F27 B02 2.6: configuracion real y seleccion en la raiz, sin proveedores."""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace

import pytest

from src.agents.catalog import AgentKey, FoundryAgentDefinition
from src.config import foundry_capability_bindings as config
from src.runtime.procedure.models import OperationAction, OperationKind
from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBindingRegistry,
    CapabilityFoundryAgentBindingRegistryError,
)
from tests.test_production_capability_foundry_agent_wiring import (
    rig as production_chain_rig,
)


PROFILE_KEY = "FOUNDRY_CAPABILITY_BINDING_PROFILE"
PROFILE = "azure-resource-group-list-sbx-v1"
CAPABILITY = "azure.resource_group.list"
ENDPOINT = (
    "https://aif-icenter-sbx-eus2.services.ai.azure.com/"
    "api/projects/aifproj-icenter-sbx"
)


def _environment():
    return {
        PROFILE_KEY: PROFILE,
        "FOUNDRY_PROJECT_ENDPOINT": ENDPOINT,
    }


def _forbidden(*args, **kwargs):
    raise AssertionError("F27_CONFIG_TEST_FORBIDDEN_PROVIDER_OR_AGENT_CALL")


def _assert_exact_binding(registry):
    assert isinstance(registry, CapabilityFoundryAgentBindingRegistry)
    assert registry.count() == 1
    binding = registry.get(CAPABILITY)
    assert binding.agent_definition == FoundryAgentDefinition(
        key=AgentKey.AZURE_OPERATIONS,
        name="agent-azure-operations-rg-list-sbx",
        version="1",
    )
    assert binding.require_approval == "always"
    capability = binding.capability
    assert capability.capability_id == CAPABILITY
    assert capability.operation_domain == "azure"
    assert capability.resource_type == "subscription"
    assert capability.operation_kind is OperationKind.READ
    assert capability.operation_action is OperationAction.RESOURCE_GROUP_LIST
    assert capability.required_parameters == ("subscription_id",)
    assert capability.hitl_required is False
    assert capability.executor_id == "azure_operations"
    authority = binding.read_tool_authority
    assert authority.capability_id == CAPABILITY
    assert authority.operation_domain == "azure"
    assert authority.resource_type == "subscription"
    assert authority.operation_action is OperationAction.RESOURCE_GROUP_LIST
    assert authority.target_resource == "subscription"
    assert authority.server_label == "azure-mcp-operations-sbx"
    assert authority.tool_name == "group_list"
    assert authority.required_parameters == ("subscription_id",)
    assert authority.argument_bindings == (("subscription", "subscription_id"),)
    assert registry.resolve(
        capability=capability, read_tool_authority=authority
    ) is binding.agent_definition


def test_profile_materializes_exact_existing_contracts_without_mutating_input():
    environment = MappingProxyType(_environment())
    before = dict(environment)
    registry = config.build_capability_foundry_agent_binding_registry(environment)
    _assert_exact_binding(registry)
    assert dict(environment) == before


def test_absence_is_fresh_empty_registry_without_resolving_authorities(monkeypatch):
    monkeypatch.setattr(config, "build_default_capability_registry", _forbidden)
    monkeypatch.setattr(
        config, "build_default_azure_read_tool_authority_registry", _forbidden
    )
    first = config.build_capability_foundry_agent_binding_registry({})
    second = config.build_capability_foundry_agent_binding_registry({})
    assert first is not second
    for registry in (first, second):
        assert registry.count() == 0
        with pytest.raises(CapabilityFoundryAgentBindingRegistryError):
            registry.get(CAPABILITY)


@pytest.mark.parametrize("environment", [None, [], "", object()])
def test_non_mapping_is_rejected(environment):
    with pytest.raises(TypeError, match="environment"):
        config.build_capability_foundry_agent_binding_registry(environment)


@pytest.mark.parametrize(
    "profile",
    [None, "", " ", True, 1, PROFILE.upper(), " " + PROFILE,
     PROFILE + " ", "azure-resource-group-list-sbx-v2", "latest"],
)
def test_present_invalid_profile_is_not_treated_as_absent(profile):
    environment = _environment()
    environment[PROFILE_KEY] = profile
    with pytest.raises(ValueError, match=PROFILE_KEY):
        config.build_capability_foundry_agent_binding_registry(environment)


@pytest.mark.parametrize(
    "endpoint", [None, "", True, ENDPOINT + "/", " " + ENDPOINT,
                 "https://unreviewed.invalid/api/projects/other"],
)
def test_selected_profile_requires_exact_reviewed_project(endpoint):
    environment = _environment()
    environment["FOUNDRY_PROJECT_ENDPOINT"] = endpoint
    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT"):
        config.build_capability_foundry_agent_binding_registry(environment)


def test_selected_profile_requires_project_to_be_present():
    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT"):
        config.build_capability_foundry_agent_binding_registry({PROFILE_KEY: PROFILE})


@pytest.fixture
def application_rig(monkeypatch):
    from src import production_composition as application

    effects = []
    captured = []
    settings = object()
    agents = SimpleNamespace(run_communication=_forbidden, run_review=_forbidden)
    bootstrap = object()

    def settings_factory(environment):
        effects.append("settings")
        return settings

    def agents_factory(actual_settings):
        assert actual_settings is settings
        effects.append("agents")
        return agents

    def host_factory(
        environment, *, communication_runner, incident_agents, review_runner,
        capability_foundry_agent_binding_registry,
    ):
        assert incident_agents is agents
        assert communication_runner is _forbidden
        assert review_runner is _forbidden
        effects.append("host")
        captured.append(capability_foundry_agent_binding_registry)
        return bootstrap

    monkeypatch.setattr(application, "build_foundry_production_settings", settings_factory)
    monkeypatch.setattr(application, "build_foundry_production_agents", agents_factory)
    monkeypatch.setattr(
        application,
        "build_production_teams_host_with_communication_and_incident_agents",
        host_factory,
    )
    return SimpleNamespace(
        application=application, effects=effects, captured=captured, bootstrap=bootstrap
    )


def test_application_root_consumes_real_configuration(application_rig):
    rig = application_rig
    environment = MappingProxyType(_environment())
    result = rig.application.build_production_application(environment)
    assert result is rig.bootstrap
    assert rig.effects == ["settings", "agents", "host"]
    assert len(rig.captured) == 1
    _assert_exact_binding(rig.captured[0])


def test_application_absence_keeps_explicit_empty_registry(application_rig):
    rig = application_rig
    rig.application.build_production_application({})
    assert len(rig.captured) == 1
    assert isinstance(rig.captured[0], CapabilityFoundryAgentBindingRegistry)
    assert rig.captured[0].count() == 0


@pytest.mark.parametrize(
    "environment", [{PROFILE_KEY: "unknown"}, {PROFILE_KEY: PROFILE}],
)
def test_application_rejects_bad_configuration_before_dependencies(
    application_rig, environment,
):
    rig = application_rig
    with pytest.raises(ValueError):
        rig.application.build_production_application(environment)
    assert rig.effects == []
    assert rig.captured == []


@pytest.mark.parametrize("populated", [False, True], ids=["empty", "populated"])
def test_injected_registry_keeps_identity_and_precedence(
    application_rig, monkeypatch, populated,
):
    rig = application_rig
    registry = config.build_capability_foundry_agent_binding_registry(
        _environment() if populated else {}
    )
    monkeypatch.setattr(
        rig.application, "build_capability_foundry_agent_binding_registry", _forbidden
    )
    rig.application.build_production_application(
        {PROFILE_KEY: "deliberately-invalid-unused-profile"},
        capability_foundry_agent_binding_registry=registry,
    )
    assert len(rig.captured) == 1
    assert rig.captured[0] is registry
    assert registry.count() == int(populated)


def test_invalid_injected_registry_fails_before_dependencies(application_rig):
    rig = application_rig
    with pytest.raises(TypeError, match="capability_foundry_agent_binding_registry"):
        rig.application.build_production_application(
            _environment(), capability_foundry_agent_binding_registry=object()
        )
    assert rig.effects == []
    assert rig.captured == []


def test_real_profile_crosses_all_roots_into_both_real_azure_compositions(
    production_chain_rig, monkeypatch,
):
    """Composicion real hasta el executor; no ejecuta handlers ni el grafo.

    La fixture historica mantiene inertes proveedores, transportes y workers.
    Se repone su leaf de workflow para atravesar el builder de producto real.
    Los ledgers son sentinels: el begin v1 se prueba por separado en T03/T04.
    """
    from src.workflows.incident_resolution import workflow as workflow_module
    from src.workflows.incident_resolution.executors.azure_operations import (
        AzureOperationsExecutor,
    )

    rig = production_chain_rig
    rig.environment.clear()
    rig.environment.update(_environment())
    created_registries = []
    azure_compositions = []
    real_azure_factory = workflow_module.build_azure_domain_composition

    def capture_configured_registry(environment):
        registry = config.build_capability_foundry_agent_binding_registry(environment)
        created_registries.append(registry)
        return registry

    def capture_real_azure_composition(**kwargs):
        composition = real_azure_factory(**kwargs)
        azure_compositions.append((kwargs, composition))
        return composition

    monkeypatch.setattr(
        rig.app, "build_capability_foundry_agent_binding_registry",
        capture_configured_registry,
    )
    monkeypatch.setattr(
        rig.base, "build_incident_resolution_workflow",
        workflow_module.build_incident_resolution_workflow,
    )
    monkeypatch.setattr(
        workflow_module, "build_azure_domain_composition",
        capture_real_azure_composition,
    )

    bootstrap = rig.invoke("application")
    assert len(created_registries) == 1
    registry = created_registries[0]
    _assert_exact_binding(registry)
    assert azure_compositions == []
    human_factory = bootstrap.dependencies.workflow_factory
    worker_factory = bootstrap.continuation_worker.dependencies.workflow_factory
    assert human_factory is worker_factory

    human_workflow = human_factory()
    worker_workflow = worker_factory()
    assert human_workflow is not None and worker_workflow is not None
    assert human_workflow is not worker_workflow
    assert len(created_registries) == 1
    assert len(azure_compositions) == 2
    assert rig.workflow_calls == []  # El leaf sintetico historico no se utilizo.
    executors = []
    for kwargs, composition in azure_compositions:
        assert kwargs["capability_foundry_agent_binding_registry"] is registry
        assert kwargs["agents"] is rig.agents
        assert kwargs["operation_dispatch_ledger"] is rig.persistence.operation_dispatch_ledger
        assert kwargs["wait_recheck_consumption_ledger"] is rig.persistence.wait_recheck_consumption_ledger
        assert kwargs["azure_vm_power_state_reader"] is rig.reader
        executor = composition.execution_binding.executor
        assert isinstance(executor, AzureOperationsExecutor)
        assert executor._capability_foundry_agent_binding_registry is registry
        assert executor._agents is rig.agents
        assert executor._operation_dispatch_ledger is rig.persistence.operation_dispatch_ledger
        _assert_exact_binding(executor._capability_foundry_agent_binding_registry)
        executors.append(executor)
    assert executors[0] is not executors[1]
