from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from importlib import import_module
from inspect import Parameter, signature
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_framework import Executor, Workflow, WorkflowBuilder

from src.workflows.incident_resolution.domain_execution_binding import (
    DomainExecutionBinding,
)
from src.workflows.incident_resolution.domain_execution_bindings import (
    DomainExecutionBindings,
    DomainExecutionBindingError,
)
from src.workflows.incident_resolution.domain_execution_path import (
    DomainExecutionPath,
    DomainExecutionPathError,
)
from src.workflows.incident_resolution.routing_post_hitl import (
    SUPPORTED_OPERATION_DOMAINS,
)
from tests.workflows.incident_resolution.test_domain_execution_binding import (
    OfflineExecutor,
    capability,
)

MODULE = "src.workflows.incident_resolution.domain_execution_registry"
MISSING = "F26_9_EXPECTED_RED_DOMAIN_EXECUTION_REGISTRY_ABSENT"


def contract():
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE:
            raise
        raise AssertionError(MISSING) from None
    return (
        module.DomainExecutionRegistration,
        module.DomainExecutionRegistrationError,
        module.DomainExecutionRegistry,
        module.DomainExecutionRegistryError,
    )


def local_path(domain="fixture.one", suffix="one"):
    entry = OfflineExecutor(f"{suffix}_pre_call")
    middle = OfflineExecutor(f"{suffix}_lifecycle")
    operation = OfflineExecutor(f"{suffix}_operations")
    binding = DomainExecutionBinding(
        operation_domain=domain,
        executor_id=operation.id,
        executor=operation,
    )
    path = DomainExecutionPath(
        execution_binding=binding,
        executors=(entry, middle, operation),
    )
    return path


def registration(domain="fixture.one", suffix="one"):
    Registration, _, _, _ = contract()
    return Registration(
        operation_domain=domain,
        execution_path=local_path(domain=domain, suffix=suffix),
    )


def test_registration_is_small_frozen_value_not_executor_or_workflow():
    Registration, _, _, _ = contract()
    reg = registration()
    assert type(reg) is Registration
    assert is_dataclass(reg)
    assert tuple(f.name for f in fields(reg)) == ("operation_domain", "execution_path")
    assert not isinstance(reg, (Executor, Workflow))


@pytest.mark.parametrize(
    "bad",
    (None, True, 17, "", " ", " fixture.one", "fixture.one "),
    ids=("none", "boolean", "integer", "empty", "space", "leading_space", "trailing_space"),
)
def test_registration_requires_exact_nonempty_operation_domain(bad):
    Registration, Error, _, _ = contract()
    with pytest.raises(Error):
        Registration(
            operation_domain=bad,
            execution_path=local_path(),
        )


def test_registration_preserves_case_without_aliases_or_normalization():
    Registration, _, _, _ = contract()
    path = local_path(domain="Fixture.Domain")
    reg = Registration(
        operation_domain="Fixture.Domain",
        execution_path=path,
    )
    assert reg.operation_domain == "Fixture.Domain"
    assert reg.execution_path is path


@pytest.mark.parametrize("kind", ("none", "mapping", "duck", "executor"))
def test_registration_rejects_non_path_without_coercion(kind):
    Registration, Error, _, _ = contract()
    value = {
        "none": None,
        "mapping": {"execution_binding": object()},
        "duck": SimpleNamespace(execution_binding=object(), entry=object(), edges=()),
        "executor": OfflineExecutor("not_a_path"),
    }[kind]
    with pytest.raises(Error):
        Registration(operation_domain="fixture.one", execution_path=value)


@pytest.mark.parametrize(
    "declared,bound",
    (("fixture.one", "Fixture.One"), ("fixture.one", "fixture.two")),
    ids=("case_mismatch", "different_domain"),
)
def test_registration_requires_exact_domain_to_match_path_binding(declared, bound):
    Registration, Error, _, _ = contract()
    with pytest.raises(Error):
        Registration(
            operation_domain=declared,
            execution_path=local_path(domain=bound),
        )


def test_registration_preserves_exact_path_and_binding_instances():
    Registration, _, _, _ = contract()
    path = local_path()
    reg = Registration(
        operation_domain=path.execution_binding.operation_domain,
        execution_path=path,
    )
    assert reg.execution_path is path
    assert reg.execution_path.execution_binding is path.execution_binding
    assert reg.execution_path.entry is path.executors[0]
    assert reg.execution_path.edges == (
        (path.executors[0], path.executors[1]),
        (path.executors[1], path.executors[2]),
    )


@pytest.mark.parametrize(
    "field",
    ("approved", "capability_id", "target_resource", "resolved_parameters"),
)
def test_registration_constructor_does_not_accept_operational_authority(field):
    Registration, _, _, _ = contract()
    kwargs = dict(
        operation_domain="fixture.one",
        execution_path=local_path(),
    )
    kwargs[field] = object()
    with pytest.raises(TypeError):
        Registration(**kwargs)


def test_unlisted_future_domain_is_valid_registration_metadata():
    Registration, _, _, _ = contract()
    assert "storage" not in SUPPORTED_OPERATION_DOMAINS
    path = local_path(domain="storage", suffix="storage")
    reg = Registration(
        operation_domain="storage",
        execution_path=path,
    )
    assert reg.operation_domain == "storage"
    assert reg.execution_path is path


def test_registry_constructor_is_keyword_only_and_requires_registrations():
    _, _, Registry, _ = contract()
    params = signature(Registry).parameters
    assert set(params) == {"registrations"}
    param = params["registrations"]
    assert param.kind is Parameter.KEYWORD_ONLY
    assert param.default is Parameter.empty


def test_registry_snapshots_one_shot_iterable_without_cloning():
    _, _, Registry, _ = contract()
    regs = [
        registration("fixture.one", "one"),
        registration("fixture.two", "two"),
    ]
    visits = []

    class Once:
        def __iter__(self):
            assert not visits
            visits.append("iterated")
            yield from regs

    registry = Registry(registrations=Once())
    assert registry.registrations == tuple(regs)
    assert all(a is b for a, b in zip(registry.registrations, regs))
    assert visits == ["iterated"]


@pytest.mark.parametrize("kind", ("none", "mapping", "duck", "path"))
def test_registry_rejects_non_registration_members_without_coercion(kind):
    _, _, Registry, Error = contract()
    value = {
        "none": None,
        "mapping": {"operation_domain": "fixture.one"},
        "duck": SimpleNamespace(
            operation_domain="fixture.one",
            execution_path=local_path(),
        ),
        "path": local_path(),
    }[kind]
    with pytest.raises(Error):
        Registry(registrations=(value,))


@pytest.mark.parametrize("kind", ("same_instance", "different_instance"))
def test_registry_rejects_duplicate_exact_operation_domains(kind):
    _, _, Registry, Error = contract()
    first = registration("fixture.one", "one")
    second = (
        first
        if kind == "same_instance"
        else registration("fixture.one", "two")
    )
    with pytest.raises(Error):
        Registry(registrations=(first, second))


@pytest.mark.parametrize("order", tuple(permutations((0, 1, 2))))
def test_registry_exact_get_is_independent_of_registration_order(order):
    _, _, Registry, _ = contract()
    regs = (
        registration("fixture.one", "one"),
        registration("Fixture.Two", "two"),
        registration("storage", "storage"),
    )
    ordered = tuple(regs[index] for index in order)
    registry = Registry(registrations=ordered)
    for reg in regs:
        assert registry.get(reg.operation_domain) is reg


@pytest.mark.parametrize(
    "key",
    ("FIXTURE.ONE", "fixture.one ", " fixture.one", "fixture", "unknown"),
)
def test_registry_unknown_or_nonexact_domain_fails_closed(key):
    _, _, Registry, Error = contract()
    registry = Registry(
        registrations=(registration("fixture.one", "one"),)
    )
    with pytest.raises(Error):
        registry.get(key)


def test_registry_public_membership_is_frozen():
    _, _, Registry, _ = contract()
    regs = (
        registration("fixture.one", "one"),
        registration("fixture.two", "two"),
    )
    registry = Registry(registrations=regs)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        registry.registrations = ()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        del registry.registrations
    assert registry.registrations == regs


def test_registry_execution_paths_are_exact_tuple_same_instances():
    _, _, Registry, _ = contract()
    regs = (
        registration("fixture.one", "one"),
        registration("fixture.two", "two"),
    )
    registry = Registry(registrations=regs)
    paths = registry.execution_paths
    assert isinstance(paths, tuple)
    assert paths == tuple(reg.execution_path for reg in regs)
    assert all(path is reg.execution_path for path, reg in zip(paths, regs))


def test_registry_exposes_one_persistent_execution_bindings_selector():
    _, _, Registry, _ = contract()
    regs = (
        registration("fixture.one", "one"),
        registration("fixture.two", "two"),
    )
    registry = Registry(registrations=regs)
    first = registry.execution_bindings
    second = registry.execution_bindings
    assert first is second
    assert isinstance(first, DomainExecutionBindings)
    assert first.bindings == tuple(
        reg.execution_path.execution_binding
        for reg in regs
    )
    assert all(
        binding is reg.execution_path.execution_binding
        for binding, reg in zip(first.bindings, regs)
    )


@pytest.mark.parametrize("source", ([], ()), ids=("list", "tuple"))
def test_empty_registry_is_valid_but_grants_no_execution_authority(source):
    _, _, Registry, _ = contract()
    registry = Registry(registrations=source)
    assert registry.registrations == ()
    assert registry.execution_paths == ()
    assert registry.execution_bindings.bindings == ()
    with pytest.raises(DomainExecutionBindingError):
        registry.execution_bindings.resolve(
            capability=capability()
        )


@pytest.mark.parametrize("access", ("get", "execution_paths"))
def test_registry_revalidates_path_identity_before_exposure(access):
    _, _, Registry, _ = contract()
    reg = registration("fixture.one", "one")
    registry = Registry(registrations=(reg,))
    original = reg.execution_path.executors[0].id
    reg.execution_path.executors[0].id = original + "_changed"
    with pytest.raises(DomainExecutionPathError):
        (
            registry.get("fixture.one")
            if access == "get"
            else registry.execution_paths
        )
    reg.execution_path.executors[0].id = original
    assert registry.get("fixture.one") is reg


@pytest.mark.parametrize(
    "field",
    ("approved", "capability_id", "target_resource", "resolved_parameters"),
)
def test_registry_constructor_does_not_accept_operational_authority(field):
    _, _, Registry, _ = contract()
    kwargs = dict(
        registrations=(registration("fixture.one", "one"),)
    )
    kwargs[field] = object()
    with pytest.raises(TypeError):
        Registry(**kwargs)


def test_registry_does_not_build_route_resolve_dispatch_clone_or_execute(monkeypatch):
    Registration, _, Registry, _ = contract()
    path = local_path()
    reg = Registration(
        operation_domain="fixture.one",
        execution_path=path,
    )
    probes = []
    for owner, name in (
        (Executor, "execute"),
        (Executor, "clone"),
        (Workflow, "run"),
        (WorkflowBuilder, "__init__"),
        (WorkflowBuilder, "build"),
        (DomainExecutionBinding, "resolve"),
        (DomainExecutionBindings, "resolve"),
    ):
        probe = Mock(side_effect=AssertionError("F26_9_FORBIDDEN_OPERATION"))
        monkeypatch.setattr(owner, name, probe)
        probes.append(probe)

    registry = Registry(registrations=(reg,))
    assert registry.get("fixture.one") is reg
    assert registry.execution_paths == (path,)
    assert registry.execution_bindings.bindings == (path.execution_binding,)
    for probe in probes:
        probe.assert_not_called()
