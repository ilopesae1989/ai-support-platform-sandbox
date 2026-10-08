from dataclasses import FrozenInstanceError, asdict, replace
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_framework import Executor, WorkflowContext, handler
from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)

MODULE = "src.workflows.incident_resolution.domain_execution_binding"
MISSING = "F26_1_EXPECTED_RED_CONTRACT_ABSENT"


def contract():
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE:
            raise
        raise AssertionError(MISSING) from None
    return module.DomainExecutionBinding, module.DomainExecutionBindingError


class OfflineExecutor(Executor):
    def __init__(self, executor_id="azure_operations"):
        super().__init__(id=executor_id)

    @handler
    async def handle(self, message: str, ctx: WorkflowContext) -> None:
        raise AssertionError("F26_BINDING_MUST_NOT_DISPATCH")


def capability():
    return build_default_capability_registry().get("azure.vm.start")


def test_resolves_existing_capability_to_exact_executor_instance():
    Binding, _ = contract()
    executor = OfflineExecutor()
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=executor
    )
    assert binding.operation_domain == "azure"
    assert binding.executor_id == "azure_operations"
    assert binding.executor is executor
    assert binding.resolve(capability=capability()) is executor


def test_resolution_never_dispatches_clones_or_mutates_authority(monkeypatch):
    Binding, _ = contract()
    registry = build_default_capability_registry()
    cap = registry.get("azure.vm.start")
    baseline_registry_count = registry.count()
    before = asdict(cap)
    executor = OfflineExecutor()
    probes = []
    for name in ("handle", "execute", "clone"):
        probe = Mock(side_effect=AssertionError("F26_UNEXPECTED_EXECUTOR_CALL"))
        monkeypatch.setattr(executor, name, probe)
        probes.append(probe)
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=executor
    )
    assert binding.resolve(capability=cap) is executor
    assert binding.resolve(capability=cap) is executor
    assert asdict(cap) == before
    assert registry.count() == baseline_registry_count
    assert registry.get("azure.vm.start") is cap
    for probe in probes:
        probe.assert_not_called()


@pytest.mark.parametrize("field,bad", [
    (field, bad)
    for field, valid in (
        ("operation_domain", "azure"), ("executor_id", "azure_operations")
    )
    for bad in (None, True, 17, "", " ", " " + valid, valid + " ")
])
def test_binding_rejects_invalid_exact_identifiers(field, bad):
    Binding, Error = contract()
    args = dict(
        operation_domain="azure", executor_id="azure_operations", executor=OfflineExecutor()
    )
    args[field] = bad
    with pytest.raises(Error):
        Binding(**args)


@pytest.mark.parametrize("bad", [
    None, OfflineExecutor, {"id": "azure_operations"},
    SimpleNamespace(id="azure_operations"),
])
def test_binding_rejects_non_executor_instances(bad):
    Binding, Error = contract()
    with pytest.raises(Error):
        Binding(operation_domain="azure", executor_id="azure_operations", executor=bad)


def test_binding_rejects_declared_and_actual_executor_id_mismatch():
    Binding, Error = contract()
    with pytest.raises(Error):
        Binding(
            operation_domain="azure", executor_id="azure_operations",
            executor=OfflineExecutor("different_executor"),
        )


@pytest.mark.parametrize("field,bad", [
    ("operation_domain", "Azure"),
    ("operation_domain", "database"),
    ("operation_domain", "*"),
    ("executor_id", "Azure_Operations"),
    ("executor_id", "azure_operations.other"),
    ("executor_id", "*"),
])
def test_resolution_requires_exact_capability_domain_and_executor(field, bad):
    Binding, Error = contract()
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=OfflineExecutor()
    )
    # Adversarial fixture only: never registered as an installed capability.
    mismatched = replace(capability(), **{field: bad})
    with pytest.raises(Error):
        binding.resolve(capability=mismatched)


@pytest.mark.parametrize("bad", [
    None, {}, "azure.vm.start",
    SimpleNamespace(
        capability_id="azure.vm.start", operation_domain="azure",
        executor_id="azure_operations",
    ),
])
def test_resolution_rejects_non_capability_inputs(bad):
    Binding, Error = contract()
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=OfflineExecutor()
    )
    with pytest.raises(Error):
        binding.resolve(capability=bad)


@pytest.mark.parametrize("field", ["operation_domain", "executor_id", "executor"])
def test_binding_metadata_and_executor_reference_are_frozen(field):
    Binding, _ = contract()
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=OfflineExecutor()
    )
    replacement = OfflineExecutor() if field == "executor" else "different"
    with pytest.raises(FrozenInstanceError):
        setattr(binding, field, replacement)


def test_resolution_rechecks_actual_executor_identity_after_binding():
    Binding, Error = contract()
    executor = OfflineExecutor()
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=executor
    )
    executor.id = "different_executor"
    with pytest.raises(Error):
        binding.resolve(capability=capability())


def test_failed_resolution_does_not_rebind_or_poison_valid_resolution():
    Binding, Error = contract()
    executor = OfflineExecutor()
    binding = Binding(
        operation_domain="azure", executor_id="azure_operations", executor=executor
    )
    cap = capability()
    with pytest.raises(Error):
        binding.resolve(capability=replace(cap, executor_id="different_executor"))
    assert binding.executor is executor
    assert binding.executor_id == "azure_operations"
    assert binding.resolve(capability=cap) is executor


@pytest.mark.parametrize("field", [
    "capability_id", "approved", "target_resource", "resolved_parameters",
])
def test_binding_constructor_does_not_accept_operational_authority(field):
    Binding, _ = contract()
    args = dict(
        operation_domain="azure", executor_id="azure_operations", executor=OfflineExecutor()
    )
    args[field] = True
    with pytest.raises(TypeError):
        Binding(**args)


@pytest.mark.parametrize("field,mixed_case", [
    ("operation_domain", "Azure"), ("executor_id", "Azure_Operations"),
])
def test_binding_preserves_case_without_creating_aliases(field, mixed_case):
    Binding, Error = contract()
    args = dict(operation_domain="azure", executor_id="azure_operations")
    args[field] = mixed_case
    binding = Binding(**args, executor=OfflineExecutor(args["executor_id"]))
    assert getattr(binding, field) == mixed_case
    with pytest.raises(Error):
        binding.resolve(capability=capability())
