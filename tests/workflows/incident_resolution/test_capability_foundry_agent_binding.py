"""F27.3-R7: contrato TDD RED, exclusivamente no-LIVE.

Esta suite especifica un binding Python de capability READ hacia un agente
Foundry de nombre/version pinned. NO invoca agentes, Azure ni MCP reales.
El archivo se crea una sola vez tras las comprobaciones del script R7.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agents.catalog import (
    AgentKey,
    FoundryAgentDefinition,
    build_agent_catalog,
)
from src.agents.foundry_agents import FoundryAgents
from src.runtime.procedure.models import OperationAction
from src.workflows.incident_resolution.azure_read_tool_authority import (
    build_default_azure_read_tool_authority_registry,
)
from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)
from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

MODULE = "src.workflows.incident_resolution.capability_foundry_agent_binding"
EXPECTED_RED = "F27_3_R7_EXPECTED_RED_CAPABILITY_AGENT_BINDING_CONTRACT_ABSENT"
CAPABILITY_ID = "azure.resource_group.list"
SYNTHETIC_AGENT = "agent-synthetic-rg-read-safe"


def contract():
    """Sin ImportError: la ausencia intencionada produce RED funcional marcado."""
    if importlib.util.find_spec(MODULE) is None:
        pytest.fail(EXPECTED_RED, pytrace=False)
    module = importlib.import_module(MODULE)
    names = (
        "CapabilityFoundryAgentBinding",
        "CapabilityFoundryAgentBindingError",
        "CapabilityFoundryAgentBindingRegistry",
        "CapabilityFoundryAgentBindingRegistryError",
    )
    if any(not hasattr(module, name) for name in names):
        pytest.fail("F27_3_BINDING_CONTRACT_SYMBOLS_INCOMPLETE", pytrace=False)
    return tuple(getattr(module, name) for name in names)


def authorities():
    capability = build_default_capability_registry().get(CAPABILITY_ID)
    read_authority = (
        build_default_azure_read_tool_authority_registry().get(CAPABILITY_ID)
    )
    return capability, read_authority


def synthetic_agent(*, version="2", name=SYNTHETIC_AGENT,
                    key=AgentKey.AZURE_OPERATIONS):
    return FoundryAgentDefinition(key=key, name=name, version=version)


def binding_args(**overrides):
    capability, read_authority = authorities()
    values = {
        "capability": capability,
        "read_tool_authority": read_authority,
        "agent_definition": synthetic_agent(),
        "require_approval": "always",
    }
    values.update(overrides)
    return values


# ---- Los guardas siguientes DEBEN SER GREEN incluso durante el TDD RED. ----

def test_guard_existing_vmstart_agent_version_remains_13(monkeypatch):
    monkeypatch.delenv("FOUNDRY_AGENT_AZURE_OPERATIONS_VERSION", raising=False)
    definition = build_agent_catalog()[AgentKey.AZURE_OPERATIONS]
    assert definition.name == "agent-azure-operations-sbx"
    assert definition.version == "13"


def test_guard_probe_agent_not_added_to_product_catalog():
    assert all(
        item.name != "agent-f27-rg-list-pause-probe-sbx"
        for item in build_agent_catalog().values()
    )


def test_guard_two_capabilities_and_existing_exact_read_authority():
    registry = build_default_capability_registry()
    capability, authority = authorities()
    assert registry.count() == 2
    assert capability.capability_id == CAPABILITY_ID
    assert capability.operation_action is OperationAction.RESOURCE_GROUP_LIST
    assert authority.tool_name == "group_list"
    assert authority.server_label == "azure-mcp-operations-sbx"
    assert authority.argument_bindings == (("subscription", "subscription_id"),)


def test_guard_no_default_rg_list_procedure_binding():
    root = Path(__file__).resolve().parents[3]
    path = root / "src/workflows/incident_resolution/procedure_capability_bindings.v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert len(manifest["bindings"]) == 3
    assert all(
        record["capability_id"] == "azure.vm.start"
        for record in manifest["bindings"]
    )


# ---- RED: el contrato aún no existe en el producto publicado. ----

def test_red_binding_resolves_exact_explicit_pinned_agent():
    Binding, _, _, _ = contract()
    args = binding_args()
    binding = Binding(**args)
    result = binding.resolve(
        capability=args["capability"],
        read_tool_authority=args["read_tool_authority"],
    )
    assert result is args["agent_definition"]
    assert result.version == "2"
    assert result.name == SYNTHETIC_AGENT


def test_red_binding_metadata_is_frozen():
    Binding, _, _, _ = contract()
    binding = Binding(**binding_args())
    with pytest.raises(FrozenInstanceError):
        binding.agent_definition = synthetic_agent(version="3")


@pytest.mark.parametrize("version", ["latest", "@latest", " 2", "2 "])
def test_red_unpinned_or_ambiguous_agent_version_rejected(version):
    Binding, Error, _, _ = contract()
    with pytest.raises(Error):
        Binding(**binding_args(agent_definition=synthetic_agent(version=version)))


@pytest.mark.parametrize("name", ["*", "agent-synthetic-rg-read-safe "])
def test_red_invalid_or_fuzzy_agent_name_rejected(name):
    Binding, Error, _, _ = contract()
    with pytest.raises(Error):
        Binding(**binding_args(agent_definition=synthetic_agent(name=name)))


def test_red_nonazure_agent_role_rejected():
    Binding, Error, _, _ = contract()
    with pytest.raises(Error):
        Binding(**binding_args(
            agent_definition=synthetic_agent(key=AgentKey.ITSM)
        ))


@pytest.mark.parametrize("policy", ["never", "ALWAYS", None])
def test_red_only_always_mcp_approval_policy_accepted(policy):
    Binding, Error, _, _ = contract()
    with pytest.raises(Error):
        Binding(**binding_args(require_approval=policy))


@pytest.mark.parametrize("field,value", [
    ("capability_id", "azure.other.list"),
    ("operation_action", OperationAction.VM_START),
])
def test_red_mismatched_capability_and_binding_fail_closed(field, value):
    Binding, Error, _, _ = contract()
    args = binding_args()
    binding = Binding(**args)
    invalid_capability = replace(args["capability"], **{field: value})
    with pytest.raises(Error):
        binding.resolve(
            capability=invalid_capability,
            read_tool_authority=args["read_tool_authority"],
        )


@pytest.mark.parametrize("field,value", [
    ("tool_name", "subscription_list"),
    ("server_label", "other-mcp-server"),
])
def test_red_substituted_mcp_authority_fails_closed(field, value):
    Binding, Error, _, _ = contract()
    args = binding_args()
    binding = Binding(**args)
    changed_authority = replace(args["read_tool_authority"], **{field: value})
    with pytest.raises(Error):
        binding.resolve(
            capability=args["capability"],
            read_tool_authority=changed_authority,
        )


def test_red_duplicate_capability_bindings_rejected():
    Binding, _, Registry, RegistryError = contract()
    binding = Binding(**binding_args())
    with pytest.raises(RegistryError):
        Registry(bindings=(binding, binding))


def test_red_absent_binding_fails_closed_without_default():
    _, _, Registry, RegistryError = contract()
    registry = Registry(bindings=())
    with pytest.raises(RegistryError):
        registry.get(CAPABILITY_ID)


def test_red_capability_lookup_is_exact_without_case_or_fuzzy_fallback():
    Binding, _, Registry, RegistryError = contract()
    binding = Binding(**binding_args())
    registry = Registry(bindings=(binding,))
    assert registry.get(CAPABILITY_ID) is binding
    with pytest.raises(RegistryError):
        registry.get("Azure.Resource_Group.List")
    with pytest.raises(RegistryError):
        registry.get(CAPABILITY_ID + " ")


def test_red_binding_constructor_cannot_accept_llm_authority():
    Binding, _, _, _ = contract()
    with pytest.raises(TypeError):
        Binding(**binding_args(), agent_name_from_llm="other-agent")


def test_red_foundry_start_has_explicit_pinned_agent_parameter():
    contract()
    parameters = inspect.signature(FoundryAgents.begin_azure_operations).parameters
    assert "agent_definition" in parameters
    assert parameters["agent_definition"].kind == inspect.Parameter.KEYWORD_ONLY


def test_red_executor_has_explicit_binding_registry_injection():
    contract()
    parameters = inspect.signature(AzureOperationsExecutor.__init__).parameters
    assert "capability_foundry_agent_binding_registry" in parameters
    assert (parameters["capability_foundry_agent_binding_registry"].kind
            == inspect.Parameter.KEYWORD_ONLY)


def test_red_foundry_start_uses_exact_selected_agent_and_session(monkeypatch):
    Binding, _, _, _ = contract()
    args = binding_args()
    selected = Binding(**args).resolve(
        capability=args["capability"],
        read_tool_authority=args["read_tool_authority"],
    )
    client = FoundryAgents(
        project_endpoint="https://example.invalid/api/projects/synthetic",
        credential=object(),
    )
    selected_by_sdk = []
    fake_response = SimpleNamespace(messages=[], text=None)
    fake_session = object()

    class FakeAgent:
        def create_session(self):
            return fake_session

        async def run(self, message, *, session, options):
            assert session is fake_session
            return fake_response

    def fake_create_agent(definition):
        selected_by_sdk.append(definition)
        return FakeAgent()

    monkeypatch.setattr(client, "_create_agent", fake_create_agent)
    invocation = asyncio.run(client.begin_azure_operations(
        "Synthetic governed READ; NO MCP",
        agent_definition=selected,
    ))
    assert selected_by_sdk == [selected]
    assert invocation.session is fake_session
    assert invocation.response is fake_response
