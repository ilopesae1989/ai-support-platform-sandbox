from dataclasses import asdict, replace
from importlib import import_module
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_framework import Executor, Workflow, WorkflowBuilder
from src.workflows.incident_resolution.capability_registry import build_default_capability_registry
from src.workflows.incident_resolution.domain_execution_binding import (
    DomainExecutionBinding, DomainExecutionBindingError,
)
from tests.workflows.incident_resolution.test_domain_execution_binding import OfflineExecutor, capability

MODULE = "src.workflows.incident_resolution.domain_execution_bindings"
MISSING = "F26_5_EXPECTED_RED_BINDING_SET_ABSENT"


def contract():
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE:
            raise
        raise AssertionError(MISSING) from None
    return module.DomainExecutionBindings


def pair(domain="azure", executor_id="azure_operations", *, executor=None):
    # Unregistered selection fixtures, NOT additional installed capabilities.
    cap = replace(capability(), operation_domain=domain, executor_id=executor_id)
    node = OfflineExecutor(executor_id) if executor is None else executor
    binding = DomainExecutionBinding(operation_domain=domain, executor_id=executor_id, executor=node)
    return binding, cap


def samples():
    return [pair(), pair("azure", "azure_secondary"), pair("synthetic_domain", "synthetic_operations")]


def resolver_probe(monkeypatch):
    observed = []
    original = DomainExecutionBinding.resolve

    def check(self, *, capability):
        observed.append((self, capability))
        return original(self, capability=capability)

    monkeypatch.setattr(DomainExecutionBinding, "resolve", check)
    return observed


def smoke_existing_components():
    fixtures = samples()
    for binding, cap in fixtures:
        assert binding.resolve(capability=cap) is binding.executor
        assert isinstance(binding.executor, Executor)
    with pytest.raises(DomainExecutionBindingError):
        fixtures[0][0].resolve(capability=fixtures[1][1])
    with pytest.raises(DomainExecutionBindingError):
        fixtures[0][0].resolve(capability=replace(fixtures[0][1], operation_domain="Azure"))
    node = fixtures[0][0].executor
    old_id = node.id
    node.id = "different"
    try:
        with pytest.raises(DomainExecutionBindingError):
            fixtures[0][0].resolve(capability=fixtures[0][1])
    finally:
        node.id = old_id
    assert fixtures[0][0].resolve(capability=fixtures[0][1]) is node
    assert build_default_capability_registry().count() == 1


@pytest.mark.parametrize("order", list(permutations(range(3))), ids=["".join(map(str, p)) for p in permutations(range(3))])
def test_exact_pair_selection_is_independent_of_input_order(order, monkeypatch):
    Bindings = contract()
    fixtures = samples()
    calls = resolver_probe(monkeypatch)
    collection = Bindings(bindings=[fixtures[i][0] for i in order])
    assert calls == []  # Construction must not invent a capability for validation.
    for binding, cap in fixtures:
        assert collection.resolve(capability=cap) is binding.executor
        assert calls[-1][0] is binding and calls[-1][1] is cap
    assert len(calls) == len(fixtures)


def test_domain_is_part_of_key_even_when_bindings_share_one_executor_instance(monkeypatch):
    Bindings = contract()
    a, ca = pair()
    b, cb = pair("synthetic_domain", a.executor_id, executor=a.executor)
    calls = resolver_probe(monkeypatch)
    collection = Bindings(bindings=[b, a])
    assert collection.resolve(capability=ca) is a.executor
    assert collection.resolve(capability=cb) is a.executor
    assert len(calls) == 2
    assert calls[0][0] is a and calls[0][1] is ca
    assert calls[1][0] is b and calls[1][1] is cb


@pytest.mark.parametrize("field,value", [
    ("operation_domain", "missing_domain"), ("operation_domain", "Azure"),
    ("operation_domain", "*"), ("executor_id", "missing_executor"),
    ("executor_id", "Azure_Operations"), ("executor_id", "azure_operations.other"),
    ("executor_id", "*"),
])
def test_unknown_or_nonexact_key_fails_without_trying_other_bindings(field, value, monkeypatch):
    Bindings = contract()
    fixtures = samples()
    calls = resolver_probe(monkeypatch)
    collection = Bindings(bindings=[b for b, _ in fixtures])
    candidate = replace(fixtures[0][1], **{field: value})
    with pytest.raises(DomainExecutionBindingError):
        collection.resolve(capability=candidate)
    assert calls == []


@pytest.mark.parametrize("duplicate", ["same_instance", "different_instance"])
def test_duplicate_exact_binding_keys_are_rejected(duplicate):
    Bindings = contract()
    a, _ = pair()
    b = a if duplicate == "same_instance" else pair()[0]
    with pytest.raises(DomainExecutionBindingError):
        Bindings(bindings=[a, b])


@pytest.mark.parametrize("empty", [[], ()], ids=["list", "tuple"])
def test_empty_binding_set_grants_nothing(empty, monkeypatch):
    Bindings = contract()
    calls = resolver_probe(monkeypatch)
    collection = Bindings(bindings=empty)
    assert collection.bindings == ()
    with pytest.raises(DomainExecutionBindingError):
        collection.resolve(capability=capability())
    assert calls == []


@pytest.mark.parametrize("bad", [None, {}, SimpleNamespace(operation_domain="azure", executor_id="azure_operations"), "azure_operations"], ids=["none", "mapping", "duck_type", "text"])
def test_non_binding_members_are_rejected_without_coercion(bad):
    Bindings = contract()
    with pytest.raises(DomainExecutionBindingError):
        Bindings(bindings=[pair()[0], bad])


@pytest.mark.parametrize("bad", [None, 17, True], ids=["none", "integer", "boolean"])
def test_non_iterable_input_is_rejected(bad):
    Bindings = contract()
    with pytest.raises(DomainExecutionBindingError):
        Bindings(bindings=bad)


def test_source_list_is_snapshotted_without_cloning_bindings_or_executors():
    Bindings = contract()
    a, ca = pair()
    b, cb = pair("synthetic_domain", "synthetic_operations")
    source = [a]
    collection = Bindings(bindings=source)
    source[:] = [b]
    assert type(collection.bindings) is tuple and collection.bindings[0] is a
    assert collection.resolve(capability=ca) is a.executor
    with pytest.raises(DomainExecutionBindingError):
        collection.resolve(capability=cb)


def test_one_shot_iterable_is_consumed_once_at_construction():
    Bindings = contract()
    fixtures = samples()
    observed = []
    def source():
        for binding, _ in fixtures:
            observed.append(binding)
            yield binding
    collection = Bindings(bindings=source())
    assert len(observed) == 3
    assert all(x is y for x, (y, _) in zip(observed, fixtures))
    for binding, cap in fixtures:
        assert collection.resolve(capability=cap) is binding.executor
    assert len(observed) == 3


def test_public_membership_cannot_be_replaced_or_deleted():
    Bindings = contract()
    binding, cap = pair()
    collection = Bindings(bindings=[binding])
    assert type(collection.bindings) is tuple and collection.bindings[0] is binding
    with pytest.raises((AttributeError, TypeError)):
        collection.bindings = ()
    with pytest.raises((AttributeError, TypeError)):
        del collection.bindings
    assert collection.resolve(capability=cap) is binding.executor


@pytest.mark.parametrize("bad", [None, {}, "azure.vm.start", SimpleNamespace(operation_domain="azure", executor_id="azure_operations")], ids=["none", "mapping", "text", "duck_type"])
def test_non_capability_input_is_rejected_before_member_resolution(bad, monkeypatch):
    Bindings = contract()
    calls = resolver_probe(monkeypatch)
    collection = Bindings(bindings=[pair()[0]])
    with pytest.raises(DomainExecutionBindingError):
        collection.resolve(capability=bad)
    assert calls == []


@pytest.mark.parametrize("changed_id", ["changed", "Azure_Operations"])
def test_actual_executor_id_is_rechecked_on_every_resolution(changed_id):
    Bindings = contract()
    binding, cap = pair()
    collection = Bindings(bindings=[binding])
    assert collection.resolve(capability=cap) is binding.executor
    binding.executor.id = changed_id
    with pytest.raises(DomainExecutionBindingError):
        collection.resolve(capability=cap)


def test_selected_binding_error_propagates_without_fallback(monkeypatch):
    Bindings = contract()
    fixtures = samples()
    collection = Bindings(bindings=[b for b, _ in fixtures])
    failure = DomainExecutionBindingError("F26_5_SELECTED_BINDING_REJECTED")
    calls = []
    def rejecting(self, *, capability):
        calls.append((self, capability))
        raise failure
    monkeypatch.setattr(DomainExecutionBinding, "resolve", rejecting)
    with pytest.raises(DomainExecutionBindingError) as caught:
        collection.resolve(capability=fixtures[1][1])
    assert caught.value is failure and len(calls) == 1
    assert calls[0][0] is fixtures[1][0] and calls[0][1] is fixtures[1][1]


def test_failed_lookup_does_not_change_a_later_valid_lookup():
    Bindings = contract()
    binding, cap = pair()
    collection = Bindings(bindings=[binding])
    before = asdict(cap)
    with pytest.raises(DomainExecutionBindingError):
        collection.resolve(capability=replace(cap, operation_domain="other"))
    assert collection.resolve(capability=cap) is binding.executor
    assert asdict(cap) == before and collection.bindings[0] is binding


@pytest.mark.parametrize("field", ["approved", "target_resource", "resolved_parameters", "capability_id"])
def test_constructor_does_not_accept_operational_authority_fields(field):
    Bindings = contract()
    with pytest.raises(TypeError):
        Bindings(bindings=[pair()[0]], **{field: True})


def test_selection_does_not_dispatch_clone_build_workflow_or_mutate_capability(monkeypatch):
    Bindings = contract()
    binding, cap = pair()
    before = asdict(cap)
    probes = []
    for obj, name in [(binding.executor, "handle"), (Executor, "execute"), (Executor, "clone"), (Workflow, "run"), (WorkflowBuilder, "build")]:
        probe = Mock(side_effect=AssertionError("F26_5_OPERATIONAL_EFFECT_FORBIDDEN"))
        monkeypatch.setattr(obj, name, probe)
        probes.append(probe)
    registry = build_default_capability_registry()
    count = registry.count()
    installed = registry.get("azure.vm.start")
    calls = resolver_probe(monkeypatch)
    collection = Bindings(bindings=[binding])
    for _ in range(2):
        assert collection.resolve(capability=cap) is binding.executor
    assert asdict(cap) == before and registry.count() == count
    assert registry.get("azure.vm.start") is installed
    assert len(calls) == 2 and all(b is binding and c is cap for b, c in calls)
    for probe in probes:
        probe.assert_not_called()
