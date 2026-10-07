from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

import pytest

import src.workflows.incident_resolution.workflow as workflow_module
from src.workflows.incident_resolution.azure_domain_composition import (
    AzureDomainComposition,
    build_azure_domain_composition,
)
from src.workflows.incident_resolution.domain_execution_path import (
    DomainExecutionPath,
    DomainExecutionPathError,
)
from src.workflows.incident_resolution.domain_execution_bindings import (
    DomainExecutionBindings,
)
from tests.workflows.incident_resolution.test_azure_domain_composition import (
    dependencies,
    assert_no_dependency_calls,
)
from tests.workflows.incident_resolution.test_workflow_azure_composition_wiring import (
    install_probe,
    build,
    members,
    assert_graph,
)

MISSING_COMPOSITION = "F26_8_EXPECTED_RED_PATH_NOT_EXPOSED_BY_COMPOSITION"
MISSING_WORKFLOW = "F26_8_EXPECTED_RED_WORKFLOW_NOT_CONSUMING_PATH"


def require_composed_path(composition):
    if not hasattr(composition, "execution_path"):
        raise AssertionError(MISSING_COMPOSITION)
    path = composition.execution_path
    if not isinstance(path, DomainExecutionPath):
        raise AssertionError(MISSING_COMPOSITION)
    return path


def expected_parts(composition):
    return (
        composition.pre_call,
        composition.operation_start,
        composition.execution_binding.executor,
    )


def assert_exact_path(composition, path):
    parts = expected_parts(composition)
    assert path.execution_binding is composition.execution_binding
    assert path.executors == parts
    assert all(a is b for a, b in zip(path.executors, parts))
    assert path.entry is composition.pre_call
    assert path.edges == (
        (composition.pre_call, composition.operation_start),
        (composition.operation_start, composition.execution_binding.executor),
    )
    assert composition.post_operation_observation not in path.executors


def test_factory_exposes_one_persistent_execution_path():
    composition = build_azure_domain_composition(**dependencies())
    path = require_composed_path(composition)
    assert composition.execution_path is path
    assert composition.execution_path is path
    assert_exact_path(composition, path)


def test_factory_path_uses_the_existing_binding_and_exact_nodes():
    composition = build_azure_domain_composition(**dependencies())
    assert_exact_path(composition, require_composed_path(composition))


def test_factory_path_excludes_post_operation_observation():
    composition = build_azure_domain_composition(**dependencies())
    path = require_composed_path(composition)
    assert composition.post_operation_observation not in path.executors
    assert path.executors[-1] is composition.execution_binding.executor


def test_repeated_compositions_create_fresh_paths_with_fresh_nodes():
    deps = dependencies()
    first = build_azure_domain_composition(**deps)
    second = build_azure_domain_composition(**deps)
    first_path = require_composed_path(first)
    second_path = require_composed_path(second)
    assert first_path is not second_path
    assert first_path.execution_binding is first.execution_binding
    assert second_path.execution_binding is second.execution_binding
    assert all(a is not b for a, b in zip(first_path.executors, second_path.executors))
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("role", ("pre_call", "operation_start", "operation"))
def test_composed_path_keeps_original_identity_snapshot(role):
    composition = build_azure_domain_composition(**dependencies())
    path = require_composed_path(composition)
    node = {
        "pre_call": composition.pre_call,
        "operation_start": composition.operation_start,
        "operation": composition.execution_binding.executor,
    }[role]
    original = node.id
    node.id = original + "_changed"
    with pytest.raises(DomainExecutionPathError):
        path.validate()
    node.id = original
    assert path.validate() is None


def install_workflow_path_probe(monkeypatch):
    calls = []
    paths = {}

    def execution_path(self):
        calls.append(self)
        key = id(self)
        if key not in paths:
            paths[key] = DomainExecutionPath(
                execution_binding=self.execution_binding,
                executors=(
                    self.pre_call,
                    self.operation_start,
                    self.execution_binding.executor,
                ),
            )
        return paths[key]

    monkeypatch.setattr(
        AzureDomainComposition,
        "execution_path",
        property(execution_path),
        raising=False,
    )
    probe = install_probe(monkeypatch)
    return SimpleNamespace(probe=probe, calls=calls, paths=paths)


def require_workflow_consumption(spy):
    if not spy.calls:
        raise AssertionError(MISSING_WORKFLOW)


def consumed_path(spy, composition):
    require_workflow_consumption(spy)
    return spy.paths[id(composition)]


def test_workflow_reads_execution_path_from_composition(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    composition, builder = build(spy.probe, deps)
    path = consumed_path(spy, composition)
    assert path.execution_binding is composition.execution_binding
    assert_graph(builder)
    assert_no_dependency_calls(deps)


def test_workflow_switch_targets_the_path_entry(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    composition, builder = build(spy.probe, deps)
    path = consumed_path(spy, composition)
    source, cases = builder.switches[0]
    azure_case = cases[0]
    assert source.id == "procedure_approval"
    assert azure_case.target is path.entry
    assert_no_dependency_calls(deps)


def test_workflow_builder_receives_exact_path_edges(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    composition, builder = build(spy.probe, deps)
    path = consumed_path(spy, composition)
    declared_pairs = {(id(a), id(b)) for a, b, _ in builder.edges}
    for left, right in path.edges:
        assert (id(left), id(right)) in declared_pairs
    assert_no_dependency_calls(deps)


def test_workflow_selector_uses_same_binding_as_consumed_path(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    composition, builder = build(spy.probe, deps)
    path = consumed_path(spy, composition)
    runtime = members(builder)["ProcedureRuntimeExecutor"]
    selector = runtime._execution_bindings
    assert isinstance(selector, DomainExecutionBindings)
    assert len(selector.bindings) == 1
    assert selector.bindings[0] is path.execution_binding
    assert_no_dependency_calls(deps)


def test_workflow_post_operation_boundary_starts_from_path_endpoint(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    composition, builder = build(spy.probe, deps)
    path = consumed_path(spy, composition)
    endpoint = path.execution_binding.executor
    pairs = [(source, target) for source, target, _ in builder.edges]
    registration = members(builder)["OperationResultRegistrationExecutor"]
    assert (endpoint, registration) in pairs
    assert_no_dependency_calls(deps)


def test_repeated_workflow_builds_consume_fresh_declared_paths(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    first = workflow_module.build_incident_resolution_workflow(**deps)
    second = workflow_module.build_incident_resolution_workflow(**deps)
    assert first is not second
    require_workflow_consumption(spy)
    assert len(spy.probe.compositions) == 2
    first_comp, second_comp = spy.probe.compositions
    first_path = spy.paths[id(first_comp)]
    second_path = spy.paths[id(second_comp)]
    assert first_path is not second_path
    assert all(a is not b for a, b in zip(first_path.executors, second_path.executors))
    assert_no_dependency_calls(deps)


def test_path_accessor_failure_propagates_before_builder(monkeypatch):
    failure = RuntimeError("F26_8_SIMULATED_PATH_ACCESS_FAILURE")

    def fail_path(self):
        raise failure

    monkeypatch.setattr(
        AzureDomainComposition,
        "execution_path",
        property(fail_path),
        raising=False,
    )
    probe = install_probe(monkeypatch)
    deps = dependencies()
    caught = None
    try:
        workflow_module.build_incident_resolution_workflow(**deps)
    except RuntimeError as exc:
        caught = exc
    if caught is None:
        raise AssertionError(MISSING_WORKFLOW)
    assert caught is failure
    assert probe.builders == []
    assert_no_dependency_calls(deps)


def test_workflow_graph_remains_exact_while_consuming_path(monkeypatch):
    spy = install_workflow_path_probe(monkeypatch)
    deps = dependencies()
    composition, builder = build(spy.probe, deps)
    consumed_path(spy, composition)
    assert_graph(builder)
    assert_no_dependency_calls(deps)
