"""F46: two explicit synthetic deployments through real configuration/composition."""
import copy
import json
from dataclasses import replace
from types import MappingProxyType, SimpleNamespace

import pytest

from src.agents.catalog import AgentKey
from src.config.foundry_deployment import DEPLOYMENT_KEY, build_foundry_deployment_configuration
from tests.test_production_capability_foundry_agent_wiring import rig, _never


def deployment_document(customer="a"):
    agents = {key.value: {"name": f"agent-{customer}-{key.value.replace('_', '-')}",
                          "version": "3" if customer == "a" else "7"} for key in AgentKey}
    return {
        "schema_version": "1.0",
        "project_endpoint": f"https://foundry-{customer}.invalid/api/projects/support-{customer}",
        "agents": agents,
        "read": {"agent_name": f"agent-{customer}-rg-list", "agent_version": "1",
                 "connection_reference": f"mcp-{customer}-read", "server_label": f"mcp-{customer}-read",
                 "server_url": f"https://mcp-{customer}-read.invalid/"},
        "write": {"agent_name": agents["azure_operations"]["name"],
                  "agent_version": agents["azure_operations"]["version"],
                  "connection_reference": f"mcp-{customer}-write", "server_label": f"mcp-{customer}-write",
                  "server_url": f"https://mcp-{customer}-write.invalid/"},
    }


def environment(document):
    return {DEPLOYMENT_KEY: json.dumps(document), "FOUNDRY_PROJECT_ENDPOINT": document["project_endpoint"]}


def test_two_customers_resolve_independently_without_process_environment(monkeypatch):
    monkeypatch.setenv("FOUNDRY_AGENT_CLASSIFICATION_VERSION", "999")
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "untrusted-process-fallback")
    configs = []
    for customer in ("a", "b"):
        document = deployment_document(customer)
        values = MappingProxyType(environment(document))
        before = dict(values)
        cfg = build_foundry_deployment_configuration(values)
        assert dict(values) == before
        assert cfg.project_endpoint == document["project_endpoint"]
        assert set(cfg.catalog) == set(AgentKey)
        for key, definition in cfg.catalog.items():
            assert definition.name == document["agents"][key.value]["name"]
            assert definition.version == document["agents"][key.value]["version"]
        with pytest.raises(TypeError):
            cfg.catalog[AgentKey.CLASSIFICATION] = None
        read = cfg.read_bindings.get("azure.resource_group.list")
        assert read.agent_definition.name == document["read"]["agent_name"]
        assert read.read_tool_authority.server_label == document["read"]["server_label"]
        assert read.read_tool_authority.tool_name == "group_list"
        assert read.require_approval == "always"
        assert cfg.write_binding.agent_definition == cfg.catalog[AgentKey.AZURE_OPERATIONS]
        configs.append(cfg)
    assert configs[0].catalog != configs[1].catalog
    assert configs[0].write_binding.fingerprint != configs[1].write_binding.fingerprint
    with pytest.raises(ValueError):
        a, b = [cfg.read_bindings.get("azure.resource_group.list") for cfg in configs]
        a.resolve(capability=a.capability, read_tool_authority=b.read_tool_authority)


def test_absence_preserves_historical_configuration():
    assert build_foundry_deployment_configuration({}) is None


@pytest.mark.parametrize("raw", [None, 1, "", "{}", "[]", "null", "{",
                                     pytest.param("x" * 100_001, id="oversized-payload"),
                                     '{"schema_version":"1.0","schema_version":"1.0"}'])
def test_malformed_input_rejected_before_dependencies(raw, rig):
    rig.environment[DEPLOYMENT_KEY] = raw
    with pytest.raises(ValueError):
        rig.invoke("application")
    assert rig.effects == []


@pytest.mark.parametrize("mutation", [
    lambda d: d.pop("agents"),
    lambda d: d.update(customer_id="untrusted-extension"),
    lambda d: d.update(schema_version="2.0"),
    lambda d: d["agents"].pop("reviewer"),
    lambda d: d["agents"].update(other={"name": "agent-other", "version": "1"}),
    lambda d: d["agents"]["classification"].update(version="latest"),
    lambda d: d["agents"]["classification"].update(version=1),
    lambda d: d["agents"]["classification"].update(version="01"),
    lambda d: d["agents"]["classification"].update(name="agent-poc-classifier"),
    lambda d: d["agents"]["classification"].update(name="agent-probe-classifier"),
    lambda d: d["agents"]["azure_operations"].update(name="agent-azure-operations-sbx"),
    lambda d: d["agents"].update(knowledge=copy.deepcopy(d["agents"]["classification"])),
    lambda d: d["read"].update(agent_name=d["write"]["agent_name"]),
    lambda d: d["read"].update(server_label=d["write"]["server_label"]),
    lambda d: d["read"].update(server_url=d["write"]["server_url"]),
    lambda d: d["read"].update(connection_reference=d["write"]["connection_reference"]),
    lambda d: d["read"].update(server_label="azure-mcp-operations-sbx"),
    lambda d: d["read"].update(server_url="https://mcp-poc-read.invalid/"),
    lambda d: d["read"].update(server_url="https://user:secret@mcp-read.invalid/"),
    lambda d: d["read"].update(server_url="https://mcp-read.invalid/unverified-path"),
    lambda d: d["read"].update(server_url="http://mcp-read.invalid/"),
    lambda d: d["read"].update(tool_name="compute_vm_start"),
    lambda d: d["write"].update(agent_version="9"),
    lambda d: d.update(project_endpoint="https://foundry.invalid/other"),
])
def test_incomplete_or_contradictory_deployment_stops_before_providers(mutation, rig):
    document = deployment_document()
    mutation(document)
    rig.environment.update(environment(document))
    with pytest.raises(ValueError):
        rig.invoke("application")
    assert rig.effects == []


@pytest.mark.parametrize("key", ["FOUNDRY_AGENT_CLASSIFICATION_VERSION",
                                "FOUNDRY_CAPABILITY_BINDING_PROFILE",
                                "FOUNDRY_RG_LIST_AGENT_VERSION", "FOUNDRY_VM_START_AGENT_VERSION"])
def test_multiple_selection_sources_rejected(key):
    values = environment(deployment_document())
    values[key] = "3"
    with pytest.raises(ValueError, match="mixed"):
        build_foundry_deployment_configuration(values)


def test_endpoint_mismatch_rejected():
    values = environment(deployment_document("a"))
    values["FOUNDRY_PROJECT_ENDPOINT"] = deployment_document("b")["project_endpoint"]
    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT"):
        build_foundry_deployment_configuration(values)


def test_old_rejected_sandbox_read_versions_cannot_be_reenabled():
    from src.config.foundry_capability_bindings import SANDBOX_PROJECT_ENDPOINT
    for version in ("1", "2"):
        document = deployment_document()
        document["project_endpoint"] = SANDBOX_PROJECT_ENDPOINT
        document["read"].update(agent_name="agent-azure-operations-rg-list-sbx", agent_version=version)
        with pytest.raises(ValueError, match="excluded"):
            build_foundry_deployment_configuration(environment(document))


@pytest.mark.parametrize("customer", ["a", "b"])
def test_real_application_reaches_human_worker_and_transition(customer, rig, monkeypatch):
    from src.agents.production_settings import build_foundry_production_settings
    from src.agents import vm_start_production_agents as factory
    from src.workflows.incident_resolution import workflow as graph
    document = deployment_document(customer)
    rig.environment.clear()
    rig.environment.update(environment(document))
    monkeypatch.setattr(rig.app, "build_foundry_production_settings", build_foundry_production_settings)
    monkeypatch.setattr(rig.app, "build_vm_start_production_agents", factory.build_vm_start_production_agents)
    monkeypatch.setattr(factory, "build_foundry_production_credential", lambda settings: object())
    monkeypatch.setattr(factory.FoundryAgents, "_create_agent", _never)
    persistence = replace(rig.persistence,
        store=SimpleNamespace(get_by_approval_id=_never, get_by_request_id=_never, get_consumption_record=_never),
        checkpoint_storage=SimpleNamespace(load=_never))
    monkeypatch.setattr(rig.prod, "build_azure_sql_teams_hitl_persistence", lambda settings: persistence)
    monkeypatch.setattr(rig.base, "build_incident_resolution_workflow", graph.build_incident_resolution_workflow)
    compositions, transitions = [], []
    real_factory = graph.build_azure_domain_composition
    real_init = graph.ProcedureTransitionExecutor.__init__
    def capture_factory(**kwargs):
        composition = real_factory(**kwargs)
        compositions.append(composition)
        return composition
    def capture_transition(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        transitions.append(self)
    monkeypatch.setattr(graph, "build_azure_domain_composition", capture_factory)
    monkeypatch.setattr(graph.ProcedureTransitionExecutor, "__init__", capture_transition)
    boot = rig.invoke("application")
    assert boot.dependencies.workflow_factory is boot.continuation_worker.dependencies.workflow_factory
    for build in (boot.dependencies.workflow_factory, boot.continuation_worker.dependencies.workflow_factory):
        build()
    assert len(compositions) == len(transitions) == 2
    for composition, transition in zip(compositions, transitions):
        executor = composition.execution_binding.executor
        assert executor._azure_read_tool_authority_registry is transition._azure_read_tool_authority_registry
        read = executor._capability_foundry_agent_binding_registry.get("azure.resource_group.list")
        assert executor._azure_read_tool_authority_registry.get("azure.resource_group.list") is read.read_tool_authority
        assert read.agent_definition.name == document["read"]["agent_name"]
        for key in AgentKey:
            assert executor._agents.get_definition(key).name == document["agents"][key.value]["name"]
        assert executor._agents.project_endpoint == document["project_endpoint"]
        assert executor._agents.deployment_fingerprint == build_foundry_deployment_configuration(environment(document)).fingerprint
        assert executor._vm_start_route.binding.agent_definition == executor._agents.get_definition(AgentKey.AZURE_OPERATIONS)
    assert compositions[0].execution_binding.executor._agents is compositions[1].execution_binding.executor._agents
    assert compositions[0].execution_binding.executor._capability_foundry_agent_binding_registry is compositions[1].execution_binding.executor._capability_foundry_agent_binding_registry


def test_explicit_selector_cannot_replace_deployment_authority(rig):
    from src.workflows.incident_resolution.capability_foundry_agent_binding import CapabilityFoundryAgentBindingRegistry
    rig.environment.update(environment(deployment_document()))
    with pytest.raises(ValueError, match="owns"):
        rig.invoke("application", CapabilityFoundryAgentBindingRegistry(bindings=()))
    assert rig.effects == []


def test_fingerprint_is_stable_across_json_formatting_and_binds_identity():
    document = deployment_document()
    values = environment(document)
    first = build_foundry_deployment_configuration(values).fingerprint
    values[DEPLOYMENT_KEY] = json.dumps(document, indent=2, sort_keys=True)
    assert build_foundry_deployment_configuration(values).fingerprint == first
    values["FOUNDRY_MANAGED_IDENTITY_CLIENT_ID"] = "11111111-1111-4111-8111-111111111111"
    assert build_foundry_deployment_configuration(values).fingerprint != first
