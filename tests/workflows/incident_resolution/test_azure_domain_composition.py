from dataclasses import FrozenInstanceError, fields, is_dataclass
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_framework import Executor, WorkflowBuilder
from src.agents.foundry_agents import FoundryAgents
from src.runtime.procedure.models import ApprovedProcedureStep
from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult, VerifiedAzureOperationRequest,
)
from src.workflows.incident_resolution.azure_vm_instance_view import AzureVmPowerStateReader
from src.workflows.incident_resolution.capability_registry import build_default_capability_registry
from src.workflows.incident_resolution.domain_execution_binding import DomainExecutionBinding
from src.workflows.incident_resolution.executors.azure_operations import AzureOperationsExecutor
from src.workflows.incident_resolution.executors.azure_pre_call import AzurePreCallSecurityExecutor
from src.workflows.incident_resolution.executors.azure_vm_post_operation_observation import (
    AzureVmPostOperationObservationExecutor,
)
from src.workflows.incident_resolution.executors.operation_lifecycle import OperationStartExecutor
from src.workflows.incident_resolution.operation_dispatch_ledger import OperationDispatchLedger
from src.workflows.incident_resolution.procedure_validation_models import ProcedureValidationRequest
from src.workflows.incident_resolution.wait_recheck_consumption_ledger import WaitRecheckConsumptionLedger

MODULE = "src.workflows.incident_resolution.azure_domain_composition"
MISSING = "F26_2_EXPECTED_RED_COMPOSITION_ABSENT"
FIELDS = ("pre_call", "operation_start", "execution_binding", "post_operation_observation")
REQUIRED = ("agents", "operation_dispatch_ledger", "wait_recheck_consumption_ledger")
MATRIX = (
    ("pre_call", AzurePreCallSecurityExecutor, "azure_pre_call_security",
     ApprovedProcedureStep, VerifiedAzureOperationRequest),
    ("operation_start", OperationStartExecutor, "operation_start",
     VerifiedAzureOperationRequest, VerifiedAzureOperationRequest),
    ("operations", AzureOperationsExecutor, "azure_operations",
     VerifiedAzureOperationRequest, AzureOperationResult),
    ("post_operation_observation", AzureVmPostOperationObservationExecutor,
     "azure_vm_post_operation_observation", ProcedureValidationRequest, ProcedureValidationRequest),
)


def contract():
    try:
        return import_module(MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE:
            raise
        raise AssertionError(MISSING) from None


def dependencies():
    # Test doubles, not production authorities; no credentials or clients.
    return dict(
        agents=Mock(spec=FoundryAgents),
        operation_dispatch_ledger=Mock(spec=OperationDispatchLedger),
        wait_recheck_consumption_ledger=Mock(spec=WaitRecheckConsumptionLedger),
        azure_vm_power_state_reader=Mock(spec=AzureVmPowerStateReader),
    )


def nodes(composition):
    return dict(
        pre_call=composition.pre_call,
        operation_start=composition.operation_start,
        operations=composition.execution_binding.executor,
        post_operation_observation=composition.post_operation_observation,
    )


def assert_dependencies(composition, deps):
    operation = composition.execution_binding.executor
    observation = composition.post_operation_observation
    # Deliberate white-box extraction checks against the existing executors.
    assert operation._agents is deps["agents"]
    assert operation._operation_dispatch_ledger is deps["operation_dispatch_ledger"]
    assert observation._reader is deps.get("azure_vm_power_state_reader")
    assert observation._wait_recheck_consumption_ledger is deps["wait_recheck_consumption_ledger"]


def assert_no_dependency_calls(deps):
    for dep in deps.values():
        if dep is not None:
            assert dep.mock_calls == []


def smoke_existing_components():
    # Exercise real fixture assumptions BEFORE creating the new RED file.
    deps = dependencies()
    operation = AzureOperationsExecutor(
        agents=deps["agents"], operation_dispatch_ledger=deps["operation_dispatch_ledger"],
    )
    composition = SimpleNamespace(
        pre_call=AzurePreCallSecurityExecutor(), operation_start=OperationStartExecutor(),
        execution_binding=DomainExecutionBinding(
            operation_domain="azure", executor_id="azure_operations", executor=operation,
        ),
        post_operation_observation=AzureVmPostOperationObservationExecutor(
            reader=deps["azure_vm_power_state_reader"],
            wait_recheck_consumption_ledger=deps["wait_recheck_consumption_ledger"],
        ),
    )
    actual = nodes(composition)
    for name, cls, executor_id, input_type, output_type in MATRIX:
        assert type(actual[name]) is cls
        assert actual[name].id == executor_id
        assert input_type in actual[name].input_types
        assert output_type in actual[name].output_types
    assert_dependencies(composition, deps)
    assert_no_dependency_calls(deps)
    cap = build_default_capability_registry().get("azure.vm.start")
    assert composition.execution_binding.resolve(capability=cap) is operation
    assert len({id(n) for n in actual.values()}) == 4


def test_factory_returns_small_frozen_composition_not_an_executor():
    module = contract()
    composition = module.build_azure_domain_composition(**dependencies())
    assert type(composition) is module.AzureDomainComposition
    assert is_dataclass(composition)
    assert tuple(f.name for f in fields(composition)) == FIELDS
    assert not isinstance(composition, Executor)


@pytest.mark.parametrize("name,cls,executor_id,input_type,output_type", MATRIX)
def test_factory_preserves_native_executors_ids_and_message_contracts(
    name, cls, executor_id, input_type, output_type,
):
    module = contract()
    node = nodes(module.build_azure_domain_composition(**dependencies()))[name]
    assert type(node) is cls
    assert node.id == executor_id
    assert input_type in node.input_types
    assert output_type in node.output_types


def test_existing_binding_resolves_operational_executor_not_pre_call_or_wait_entry():
    module = contract()
    composition = module.build_azure_domain_composition(**dependencies())
    binding = composition.execution_binding
    assert type(binding) is DomainExecutionBinding
    assert binding.operation_domain == "azure"
    assert binding.executor_id == "azure_operations"
    resolved = binding.resolve(capability=build_default_capability_registry().get("azure.vm.start"))
    assert resolved is binding.executor
    assert type(resolved) is AzureOperationsExecutor
    assert all(resolved is not getattr(composition, key) for key in (
        "pre_call", "operation_start", "post_operation_observation",
    ))


def test_factory_preserves_all_injected_dependency_instances_without_using_them():
    module = contract()
    deps = dependencies()
    composition = module.build_azure_domain_composition(**deps)
    assert_dependencies(composition, deps)
    assert_no_dependency_calls(deps)


def test_repeated_composition_creates_fresh_nodes_but_keeps_shared_authorities():
    module = contract()
    deps = dependencies()
    first = module.build_azure_domain_composition(**deps)
    second = module.build_azure_domain_composition(**deps)
    assert first is not second
    assert first.execution_binding is not second.execution_binding
    first_nodes, second_nodes = nodes(first), nodes(second)
    assert len({id(n) for n in first_nodes.values()}) == 4
    for name in first_nodes:
        assert first_nodes[name] is not second_nodes[name]
        assert first_nodes[name].id == second_nodes[name].id
    assert_dependencies(first, deps)
    assert_dependencies(second, deps)
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("field", FIELDS)
def test_composition_references_are_frozen(field):
    module = contract()
    composition = module.build_azure_domain_composition(**dependencies())
    with pytest.raises(FrozenInstanceError):
        setattr(composition, field, object())


@pytest.mark.parametrize("field", REQUIRED)
def test_factory_requires_dependencies_explicitly(field):
    module = contract()
    deps = dependencies()
    deps.pop(field)
    with pytest.raises(TypeError):
        module.build_azure_domain_composition(**deps)
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("field", REQUIRED)
def test_none_authority_dependency_is_rejected_before_any_executor_creation(field, monkeypatch):
    module = contract()
    deps = dependencies()
    deps[field] = None
    attempts = []
    def forbidden_constructor(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("EXECUTOR_CREATED_BEFORE_DEPENDENCY_VALIDATION")
    for _, cls, _, _, _ in MATRIX:
        monkeypatch.setattr(cls, "__init__", forbidden_constructor)
    with pytest.raises(ValueError):
        module.build_azure_domain_composition(**deps)
    assert attempts == []
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("omit_reader", [False, True])
def test_optional_reader_none_remains_none_without_implicit_client_creation(omit_reader):
    module = contract()
    deps = dependencies()
    deps["azure_vm_power_state_reader"] = None
    if omit_reader:
        deps.pop("azure_vm_power_state_reader")
    composition = module.build_azure_domain_composition(**deps)
    assert_dependencies(composition, deps)
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("field", [
    "operation_domain", "capability_id", "approved_step", "target_resource", "resolved_parameters",
])
def test_factory_does_not_accept_operational_requests_or_authorization_fields(field):
    module = contract()
    deps = dependencies()
    with pytest.raises(TypeError):
        module.build_azure_domain_composition(**deps, **{field: object()})
    assert_no_dependency_calls(deps)


def test_composition_does_not_dispatch_clone_build_workflow_or_create_foundry_client(monkeypatch):
    module = contract()
    deps = dependencies()
    attempts = []
    def forbidden_call(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("COMPOSITION_SIDE_EFFECT_FORBIDDEN")
    for owner, name in (
        (Executor, "execute"), (Executor, "clone"),
        (WorkflowBuilder, "build"), (FoundryAgents, "__init__"),
    ):
        # Plain functions avoid Mock-generated pseudo handler attributes.
        monkeypatch.setattr(owner, name, forbidden_call)
    composition = module.build_azure_domain_composition(**deps)
    composition.execution_binding.resolve(
        capability=build_default_capability_registry().get("azure.vm.start"),
    )
    assert_no_dependency_calls(deps)
    assert attempts == []
