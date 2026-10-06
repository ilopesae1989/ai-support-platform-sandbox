from collections import Counter
from functools import wraps
from types import SimpleNamespace

import pytest
from agent_framework import Case, Default, Workflow, WorkflowBuilder
import src.workflows.incident_resolution.workflow as workflow_module
import src.workflows.incident_resolution.azure_domain_composition as composition_module
from tests.workflows.incident_resolution.test_azure_domain_composition import (
    MATRIX, assert_dependencies, assert_no_dependency_calls, dependencies, nodes,
)

MISSING = "F26_3_EXPECTED_RED_FACTORY_NOT_USED"


def install_probe(monkeypatch, *, failure=None):
    """Record native construction; never run the workflow or any handler."""
    probe = SimpleNamespace(calls=[], compositions=[], builders=[], constructors=[], inside=False)
    factory = composition_module.build_azure_domain_composition

    def factory_spy(**kwargs):
        probe.calls.append(dict(kwargs))
        if failure is not None:
            raise failure
        probe.inside = True
        try:
            result = factory(**kwargs)
        finally:
            probe.inside = False
        probe.compositions.append(result)
        return result

    def instrument(cls, original):
        @wraps(original)
        def tracked(self, *args, **kwargs):
            probe.constructors.append((cls, self, probe.inside))
            return original(self, *args, **kwargs)
        return tracked

    for _, cls, _, _, _ in MATRIX:
        monkeypatch.setattr(cls, "__init__", instrument(cls, cls.__init__))

    class RecordingBuilder:
        def __init__(self, *args, **kwargs):
            self.options = dict(kwargs)
            self.edges, self.switches = [], []
            self.builds = 0
            self.native = WorkflowBuilder(*args, **kwargs)
            probe.builders.append(self)

        def add_edge(self, source, target, condition=None):
            self.edges.append((source, target, condition))
            self.native.add_edge(source, target, condition=condition)
            return self

        def add_switch_case_edge_group(self, source, cases):
            self.switches.append((source, tuple(cases)))
            self.native.add_switch_case_edge_group(source, cases)
            return self

        def build(self):
            self.builds += 1
            self.result = self.native.build()
            return self.result

    monkeypatch.setattr(workflow_module, "WorkflowBuilder", RecordingBuilder)
    monkeypatch.setattr(composition_module, "build_azure_domain_composition", factory_spy)
    # Supports a module-qualified import or a local import alias; not product authority.
    monkeypatch.setattr(workflow_module, "build_azure_domain_composition", factory_spy, raising=False)
    return probe


def require_factory(probe, expected=1):
    if not probe.calls:
        raise AssertionError(MISSING)
    assert len(probe.calls) == expected


def build(probe, deps):
    result = workflow_module.build_incident_resolution_workflow(**deps)
    require_factory(probe)
    assert len(probe.builders) == len(probe.compositions) == 1
    assert isinstance(result, Workflow)
    assert probe.builders[0].result is result
    assert probe.builders[0].builds == 1
    return probe.compositions[0], probe.builders[0]


def members(builder):
    values = [builder.options["start_executor"], *builder.options["output_from"]]
    for source, target, _ in builder.edges:
        values.extend((source, target))
    for source, cases in builder.switches:
        values.append(source)
        values.extend(case.target for case in cases)
    result, ids = {}, {}
    for node in values:
        name = type(node).__name__
        assert name not in result or result[name] is node
        assert node.id not in ids or ids[node.id] is node
        result[name], ids[node.id] = node, node
    return result


def assert_graph(builder):
    # Construction contract: exact existing edges/conditions, not source formatting.
    expected = [
        ("ClassificationExecutor", "KnowledgeExecutor", None),
        ("KnowledgeExecutor", "AlertTriageExecutor", None),
        ("AlertTriageExecutor", "ProcedureRequestExecutor", workflow_module.route_to_procedure_execution),
        ("AlertTriageExecutor", "KnowledgeReviewExecutor", workflow_module.route_to_knowledge_review),
        ("AlertTriageExecutor", "ManualAnalysisExecutor", workflow_module.route_to_manual_analysis),
        ("ProcedureRequestExecutor", "ProcedureExecutionExecutor", None),
        ("ProcedureExecutionExecutor", "ProcedureRuntimeExecutor", None),
        ("ProcedureRuntimeExecutor", "ProcedureApprovalExecutor", None),
        ("AzurePreCallSecurityExecutor", "OperationStartExecutor", None),
        ("OperationStartExecutor", "AzureOperationsExecutor", None),
        ("AzureOperationsExecutor", "OperationResultRegistrationExecutor", None),
        ("OperationResultRegistrationExecutor", "AzureVmPostOperationObservationExecutor", None),
        ("AzureVmPostOperationObservationExecutor", "ProcedureValidationExecutor", None),
        ("ProcedureValidationExecutor", "ProcedureTransitionExecutor", None),
        ("ProcedureTransitionExecutor", "ProcedureExecutionExecutor", None),
        ("ProcedureTransitionExecutor", "AzureVmPostOperationObservationExecutor", None),
    ]
    actual = [(type(s).__name__, type(t).__name__, c) for s, t, c in builder.edges]
    assert Counter(actual) == Counter(expected)
    assert len(builder.switches) == 1
    source, cases = builder.switches[0]
    assert type(source).__name__ == "ProcedureApprovalExecutor"
    targets = (
        ("azure", "AzurePreCallSecurityExecutor"), ("database", "DatabaseRouteExecutor"),
        ("itsm", "ItsmRouteExecutor"), ("windows", "WindowsRouteExecutor"),
        ("linux", "LinuxRouteExecutor"), ("networking", "NetworkingRouteExecutor"),
        ("microsoft365", "Microsoft365RouteExecutor"),
    )
    assert len(cases) == len(targets) + 1
    for case, (domain, target) in zip(cases, targets):
        assert type(case) is Case
        assert case.condition is getattr(workflow_module, "route_to_" + domain + "_operation")
        assert type(case.target).__name__ == target
    assert type(cases[-1]) is Default
    assert type(cases[-1].target).__name__ == "BlockedRouteExecutor"
    assert set(builder.options) == {"start_executor", "output_from", "name", "max_iterations"}
    assert builder.options["name"] == "incident-resolution"
    assert builder.options["max_iterations"] == 100
    assert type(builder.options["start_executor"]).__name__ == "ClassificationExecutor"
    assert [type(n).__name__ for n in builder.options["output_from"]] == [
        "ProcedureApprovalExecutor", "KnowledgeReviewExecutor", "ManualAnalysisExecutor",
        "ProcedureTransitionExecutor", "DatabaseRouteExecutor", "ItsmRouteExecutor",
        "WindowsRouteExecutor", "LinuxRouteExecutor", "NetworkingRouteExecutor",
        "Microsoft365RouteExecutor", "BlockedRouteExecutor",
    ]
    members(builder)


def smoke_before_wiring():
    with pytest.MonkeyPatch.context() as patch:
        probe, deps = install_probe(patch), dependencies()
        result = workflow_module.build_incident_resolution_workflow(**deps)
        assert isinstance(result, Workflow)
        assert probe.calls == []  # Current certified gap, not a future product test.
        assert len(probe.builders) == 1 and probe.builders[0].builds == 1
        assert_graph(probe.builders[0])
        assert len(probe.constructors) == 4
        assert all(not inside for _, _, inside in probe.constructors)
        assert_no_dependency_calls(deps)


def test_workflow_calls_published_factory_once_with_exact_dependencies(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    composition, _ = build(probe, deps)
    assert set(probe.calls[0]) == set(deps)
    assert all(probe.calls[0][key] is value for key, value in deps.items())
    assert_dependencies(composition, deps)
    assert_no_dependency_calls(deps)


@pytest.mark.parametrize("name,cls,executor_id,input_type,output_type", MATRIX)
def test_native_builder_receives_the_exact_nodes_returned_by_factory(
    monkeypatch, name, cls, executor_id, input_type, output_type,
):
    probe, deps = install_probe(monkeypatch), dependencies()
    composition, builder = build(probe, deps)
    node = nodes(composition)[name]
    assert members(builder)[cls.__name__] is node
    assert type(node) is cls and node.id == executor_id
    assert input_type in node.input_types and output_type in node.output_types
    assert_no_dependency_calls(deps)


def test_wiring_preserves_all_edges_switch_conditions_and_output_selection(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    _, builder = build(probe, deps)
    assert_graph(builder)
    assert_no_dependency_calls(deps)


def test_wait_observation_and_transition_share_the_same_injected_authority(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    composition, builder = build(probe, deps)
    transition = members(builder)["ProcedureTransitionExecutor"]
    ledger = deps["wait_recheck_consumption_ledger"]
    assert transition._wait_recheck_consumption_ledger is ledger
    assert composition.post_operation_observation._wait_recheck_consumption_ledger is ledger
    assert_graph(builder)  # WAIT returns to observation, not operation_start/dispatch.
    assert_no_dependency_calls(deps)


def test_optional_reader_none_is_forwarded_without_creating_a_reader(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    deps["azure_vm_power_state_reader"] = None
    composition, _ = build(probe, deps)
    assert probe.calls[0]["azure_vm_power_state_reader"] is None
    assert composition.post_operation_observation._reader is None
    assert_no_dependency_calls(deps)


def test_existing_default_ledgers_are_selected_once_and_forwarded(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    defaults = []
    def dispatch():
        defaults.append("dispatch")
        return deps["operation_dispatch_ledger"]
    def recheck():
        defaults.append("recheck")
        return deps["wait_recheck_consumption_ledger"]
    monkeypatch.setattr(workflow_module, "InMemoryOperationDispatchLedger", dispatch)
    monkeypatch.setattr(workflow_module, "InMemoryWaitRecheckConsumptionLedger", recheck)
    composition, _ = build(probe, {"agents": deps["agents"],
        "azure_vm_power_state_reader": deps["azure_vm_power_state_reader"]})
    assert defaults == ["dispatch", "recheck"]
    assert_dependencies(composition, deps)
    assert_no_dependency_calls(deps)


def test_factory_failure_propagates_without_fallback_or_building_a_graph(monkeypatch):
    failure = RuntimeError("F26_3_SIMULATED_FACTORY_FAILURE")
    probe, deps = install_probe(monkeypatch, failure=failure), dependencies()
    caught = None
    try:
        workflow_module.build_incident_resolution_workflow(**deps)
    except RuntimeError as exc:
        caught = exc
    require_factory(probe)
    assert caught is failure
    assert probe.builders == probe.constructors == probe.compositions == []
    assert_no_dependency_calls(deps)


def test_repeated_workflow_builds_use_fresh_nodes_and_keep_shared_dependencies(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    first = workflow_module.build_incident_resolution_workflow(**deps)
    second = workflow_module.build_incident_resolution_workflow(**deps)
    require_factory(probe, expected=2)
    assert first is not second
    assert len(probe.compositions) == len(probe.builders) == 2
    a, b = [nodes(c) for c in probe.compositions]
    assert all(a[key] is not b[key] for key in a)
    for composition, builder in zip(probe.compositions, probe.builders):
        assert_dependencies(composition, deps)
        for node in nodes(composition).values():
            assert members(builder)[type(node).__name__] is node
    assert_no_dependency_calls(deps)


def test_four_domain_nodes_are_constructed_only_inside_the_factory(monkeypatch):
    probe, deps = install_probe(monkeypatch), dependencies()
    composition, _ = build(probe, deps)
    assert len(probe.constructors) == 4
    expected = {id(n) for n in nodes(composition).values()}
    assert {id(n) for _, n, _ in probe.constructors} == expected
    assert all(inside for _, _, inside in probe.constructors)
    assert_no_dependency_calls(deps)
