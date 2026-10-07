from dataclasses import FrozenInstanceError, asdict
from importlib import import_module
from inspect import Parameter, signature
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_framework import Executor, Workflow, WorkflowBuilder
from src.workflows.incident_resolution.domain_execution_binding import DomainExecutionBinding
from src.workflows.incident_resolution.azure_domain_composition import build_azure_domain_composition
from tests.workflows.incident_resolution.test_domain_execution_binding import OfflineExecutor, capability
from tests.workflows.incident_resolution.test_azure_domain_composition import (
    dependencies, assert_no_dependency_calls, MATRIX, nodes,
)

MODULE = "src.workflows.incident_resolution.domain_execution_path"
MISSING = "F26_7_EXPECTED_RED_EXECUTION_PATH_ABSENT"


def contract():
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE:
            raise
        raise AssertionError(MISSING) from None
    return module.DomainExecutionPath, module.DomainExecutionPathError


def local_parts(size=3, domain="azure"):
    parts = [OfflineExecutor(f"path_gate_{i}") for i in range(size - 1)]
    parts.append(OfflineExecutor("azure_operations"))
    binding = DomainExecutionBinding(
        operation_domain=domain, executor_id=parts[-1].id, executor=parts[-1],
    )
    return binding, parts


def assert_same_edges(path, parts):
    edges = path.edges
    assert isinstance(edges, tuple) and len(edges) == len(parts) - 1
    for pair, left, right in zip(edges, parts, parts[1:]):
        assert isinstance(pair, tuple) and len(pair) == 2
        assert pair[0] is left and pair[1] is right
    assert path.entry is parts[0]
    assert path.execution_binding.executor is parts[-1]


def test_constructor_has_only_explicit_composition_inputs():
    Path, _ = contract()
    params = signature(Path).parameters
    assert set(params) == {"execution_binding", "executors"}
    assert all(p.kind is Parameter.KEYWORD_ONLY and p.default is Parameter.empty
               for p in params.values())


def test_actual_azure_segment_preserves_components_ports_and_order():
    Path, _ = contract()
    deps = dependencies()
    composition = build_azure_domain_composition(**deps)
    parts = (composition.pre_call, composition.operation_start,
             composition.execution_binding.executor)
    path = Path(execution_binding=composition.execution_binding, executors=parts)
    assert path.execution_binding is composition.execution_binding
    assert isinstance(path.executors, tuple)
    assert all(a is b for a, b in zip(path.executors, parts))
    assert len(path.executors) == len(parts)
    assert path.validate() is None
    assert_same_edges(path, parts)
    for name, cls, executor_id, input_type, output_type in MATRIX:
        node = nodes(composition)[name]
        assert type(node) is cls and node.id == executor_id
        assert input_type in node.input_types and output_type in node.output_types
    assert all(node is not composition.post_operation_observation for node in path.executors)
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("size", (2, 3, 5), ids=("two", "three", "five"))
def test_linear_segment_does_not_impose_azure_role_names_or_stage_count(size):
    Path, _ = contract()
    binding, parts = local_parts(size, domain="fixture.domain")
    path = Path(execution_binding=binding, executors=parts)
    assert path.execution_binding is binding
    assert_same_edges(path, parts)
    assert not isinstance(path, (Executor, Workflow))


def test_source_list_is_snapshotted_without_cloning_nodes():
    Path, _ = contract()
    binding, parts = local_parts()
    saved = tuple(parts)
    path = Path(execution_binding=binding, executors=parts)
    parts.clear()
    assert isinstance(path.executors, tuple) and len(path.executors) == len(saved)
    assert all(a is b for a, b in zip(path.executors, saved))
    assert_same_edges(path, saved)


def test_one_shot_iterable_is_consumed_once():
    Path, _ = contract()
    binding, parts = local_parts()
    visits = []
    class Once:
        def __iter__(self):
            assert not visits
            visits.append("iterated")
            yield from parts
    path = Path(execution_binding=binding, executors=Once())
    path.validate()
    assert_same_edges(path, parts)
    assert_same_edges(path, parts)
    assert visits == ["iterated"]


@pytest.mark.parametrize("kind", ("none", "mapping", "duck"))
def test_non_binding_is_rejected_without_coercion(kind):
    Path, Error = contract()
    binding, parts = local_parts()
    bad = {"none": None, "mapping": {"executor": parts[-1]},
           "duck": SimpleNamespace(executor=parts[-1], executor_id=parts[-1].id,
                                   operation_domain=binding.operation_domain)}[kind]
    with pytest.raises(Error):
        Path(execution_binding=bad, executors=parts)


@pytest.mark.parametrize("value", (None, False, 17), ids=("none", "boolean", "integer"))
def test_non_iterable_segment_is_rejected(value):
    Path, Error = contract()
    binding, _ = local_parts()
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=value)


@pytest.mark.parametrize("length", (0, 1), ids=("empty", "operation_only"))
def test_absent_or_direct_operational_entry_is_rejected(length):
    Path, Error = contract()
    binding, parts = local_parts()
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=parts[-1:] if length else ())


@pytest.mark.parametrize("kind", ("none", "class", "mapping", "duck"))
def test_non_executor_member_is_rejected(kind):
    Path, Error = contract()
    binding, parts = local_parts()
    bad = {"none": None, "class": OfflineExecutor, "mapping": {"id": "gate"},
           "duck": SimpleNamespace(id="gate")}[kind]
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=(bad, parts[-1]))


@pytest.mark.parametrize("which", ("gate", "operation"))
def test_repeated_node_reference_is_rejected(which):
    Path, Error = contract()
    binding, parts = local_parts()
    repeated = (parts[0], parts[0], parts[-1]) if which == "gate" else (parts[0], parts[-1], parts[-1])
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=repeated)


@pytest.mark.parametrize("which", ("gate", "operation"))
def test_distinct_nodes_with_duplicate_ids_are_rejected(which):
    Path, Error = contract()
    binding, parts = local_parts()
    parts[0].id = parts[1].id if which == "gate" else parts[-1].id
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=parts)


@pytest.mark.parametrize("kind", ("missing", "not_last", "copied_same_id"))
def test_bound_executor_must_be_the_exact_last_instance(kind):
    Path, Error = contract()
    binding, parts = local_parts()
    if kind == "missing":
        parts[-1] = OfflineExecutor("other")
    elif kind == "not_last":
        parts = [parts[-1], *parts[:-1]]
    else:
        parts[-1] = OfflineExecutor(binding.executor_id)
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=parts)


@pytest.mark.parametrize("bad", (None, True, "", " gate", "gate "),
                         ids=("none", "boolean", "empty", "leading_space", "trailing_space"))
def test_node_ids_are_exact_nonempty_strings_without_normalization(bad):
    Path, Error = contract()
    binding, parts = local_parts()
    parts[0].id = bad
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=parts)


def test_bound_executor_changed_before_path_construction_is_rejected():
    Path, Error = contract()
    binding, parts = local_parts()
    parts[-1].id = "changed"
    with pytest.raises(Error):
        Path(execution_binding=binding, executors=parts)


@pytest.mark.parametrize("field", ("execution_binding", "executors"))
def test_composition_membership_is_frozen(field):
    Path, _ = contract()
    binding, parts = local_parts()
    path = Path(execution_binding=binding, executors=parts)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        setattr(path, field, None)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        delattr(path, field)
    assert_same_edges(path, parts)


@pytest.mark.parametrize("index", (0, 1, 2), ids=("entry", "middle", "operation"))
@pytest.mark.parametrize("access", ("validate", "entry", "edges"))
def test_current_node_identity_is_rechecked_before_exposing_connections(index, access):
    Path, Error = contract()
    binding, parts = local_parts()
    path = Path(execution_binding=binding, executors=parts)
    old_id = parts[index].id
    parts[index].id = old_id.upper()
    with pytest.raises(Error):
        path.validate() if access == "validate" else getattr(path, access)
    assert parts[index].id == old_id.upper()  # The contract must not repair it.
    parts[index].id = old_id
    assert path.validate() is None
    assert_same_edges(path, parts)


@pytest.mark.parametrize("field", ("approved", "capability_id", "target_resource", "resolved_parameters"))
def test_constructor_does_not_accept_operational_authority(field):
    Path, _ = contract()
    binding, parts = local_parts()
    args = dict(execution_binding=binding, executors=parts)
    args[field] = None
    with pytest.raises(TypeError):
        Path(**args)


def test_case_distinct_node_ids_remain_distinct_without_aliases():
    Path, _ = contract()
    binding, parts = local_parts()
    parts[0].id, parts[1].id = "Gate", "gate"
    path = Path(execution_binding=binding, executors=parts)
    assert [node.id for node in path.executors] == ["Gate", "gate", "azure_operations"]
    assert_same_edges(path, parts)


def test_path_does_not_resolve_capability_dispatch_clone_or_build_a_graph(monkeypatch):
    Path, _ = contract()
    binding, parts = local_parts()
    cap = capability()
    before = asdict(cap)
    probes = []
    for owner, name in ((Executor, "execute"), (Executor, "clone"), (Workflow, "run"),
                        (WorkflowBuilder, "__init__"), (WorkflowBuilder, "build"),
                        (DomainExecutionBinding, "resolve")):
        probe = Mock(side_effect=AssertionError("F26_7_FORBIDDEN_OPERATION"))
        monkeypatch.setattr(owner, name, probe)
        probes.append(probe)
    path = Path(execution_binding=binding, executors=parts)
    assert path.validate() is None
    assert path.execution_binding is binding
    assert_same_edges(path, parts)
    assert asdict(cap) == before
    for probe in probes:
        probe.assert_not_called()


def smoke_existing_components():
    # Only existing fixtures/native constructors. No proposed product imported.
    binding, parts = local_parts()
    assert binding.resolve(capability=capability()) is parts[-1]
    assert len({id(node) for node in parts}) == len(parts)
    deps = dependencies()
    composition = build_azure_domain_composition(**deps)
    actual = nodes(composition)
    for name, cls, executor_id, input_type, output_type in MATRIX:
        node = actual[name]
        assert type(node) is cls and node.id == executor_id
        assert input_type in node.input_types and output_type in node.output_types
    assert composition.execution_binding.resolve(capability=capability()) is actual["operations"]
    assert len({id(node) for node in actual.values()}) == 4
    assert_no_dependency_calls(deps)
