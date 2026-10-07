from dataclasses import asdict, replace
from functools import wraps
from inspect import Parameter, signature
from types import SimpleNamespace

import pytest
from agent_framework import Executor, Workflow
import src.workflows.incident_resolution.workflow as workflow_module
import src.workflows.incident_resolution.executors.runtime as runtime_module
from src.workflows.incident_resolution.capability_registry import (
    CapabilityRegistry, build_default_capability_registry,
)
from src.workflows.incident_resolution.domain_execution_binding import (
    DomainExecutionBinding, DomainExecutionBindingError,
)
from src.workflows.incident_resolution.domain_execution_bindings import DomainExecutionBindings
from src.workflows.incident_resolution.procedure_capability_registry import ProcedureCapabilityRegistry
from tests.workflows.incident_resolution.test_domain_execution_binding import OfflineExecutor
from tests.workflows.incident_resolution.test_runtime_capability_binding import (
    create_execution_context, create_procedure_capability_registry,
)
from tests.workflows.incident_resolution.test_workflow_azure_composition_wiring import (
    install_probe, members, assert_graph, dependencies, assert_no_dependency_calls,
)

MISSING_WIRING = "F26_6_EXPECTED_RED_SELECTOR_NOT_INJECTED"
MISSING_INPUT = "F26_6_EXPECTED_RED_RUNTIME_COLLECTION_INPUT_ABSENT"
BAD_IDS = (
    "unknown_executor", "Azure_Operations", "azure_operations.other", "*",
    "azure_pre_call_security", "azure_vm_post_operation_observation",
)


def instrument(monkeypatch, *, executor_id="azure_operations", bound=True):
    context = create_execution_context()
    capability = replace(build_default_capability_registry().get("azure.vm.start"),
                         executor_id=executor_id)
    binding = create_procedure_capability_registry().get_binding(
        procedure_id=context.result.procedure.id,
        procedure_version=context.result.procedure.version, step_id=context.result.step.id,
    )
    registry = ProcedureCapabilityRegistry(
        capability_registry=CapabilityRegistry(capabilities=[capability]),
        bindings=[binding] if bound else [],
    )
    case = SimpleNamespace(context=context, capability=capability, registry=registry,
        events=[], resolved=[], selections=[], members=[], collections=[], inputs=[],
        state_calls=[], dependencies=dependencies(), policy_failure=None,
        selector_failure=None, member_failure=None, constructor_failure=None)
    policy = registry.resolve_applicable_capability
    collection_init = DomainExecutionBindings.__init__
    collection_resolve = DomainExecutionBindings.resolve
    member_resolve = DomainExecutionBinding.resolve
    runtime_init = runtime_module.ProcedureRuntimeExecutor.__init__
    state_type = runtime_module.ProcedureRuntimeState

    def policy_spy(**kwargs):
        case.events.append("policy")
        if case.policy_failure is not None:
            raise case.policy_failure
        result = policy(**kwargs)
        case.resolved.append(result)
        return result

    @wraps(collection_init)
    def init_spy(self, *args, **kwargs):
        case.collections.append(self)
        if case.constructor_failure is not None:
            raise case.constructor_failure
        return collection_init(self, *args, **kwargs)

    def selector_spy(self, *, capability):
        case.events.append("selector")
        case.selections.append((self, capability))
        if case.selector_failure is not None:
            raise case.selector_failure
        return collection_resolve(self, capability=capability)

    def member_spy(self, *, capability):
        case.events.append("binding")
        case.members.append((self, capability))
        if case.member_failure is not None:
            raise case.member_failure
        return member_resolve(self, capability=capability)

    @wraps(runtime_init)
    def runtime_spy(self, *args, **kwargs):
        result = runtime_init(self, *args, **kwargs)
        case.inputs.append((self, args, dict(kwargs)))
        return result

    def state_spy(*args, **kwargs):
        case.events.append("state")
        case.state_calls.append((args, kwargs))
        return state_type(*args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("F26_6_OPERATIONAL_EXECUTION_FORBIDDEN")

    monkeypatch.setattr(registry, "resolve_applicable_capability", policy_spy)
    monkeypatch.setattr(DomainExecutionBindings, "__init__", init_spy)
    monkeypatch.setattr(DomainExecutionBindings, "resolve", selector_spy)
    monkeypatch.setattr(DomainExecutionBinding, "resolve", member_spy)
    monkeypatch.setattr(runtime_module.ProcedureRuntimeExecutor, "__init__", runtime_spy)
    monkeypatch.setattr(runtime_module, "ProcedureRuntimeState", state_spy)
    for owner, name in ((Executor, "execute"), (Executor, "clone"), (Workflow, "run")):
        monkeypatch.setattr(owner, name, forbidden)
    case.probe = install_probe(monkeypatch)
    return case


def build_workflow(case):
    result = workflow_module.build_incident_resolution_workflow(
        **case.dependencies, procedure_capability_registry=case.registry,
    )
    builder = case.probe.builders[-1]
    assert isinstance(result, Workflow) and builder.result is result and builder.builds == 1
    assert_graph(builder)
    runtime = members(builder)["ProcedureRuntimeExecutor"]
    binding = case.probe.compositions[-1].execution_binding
    assert members(builder)["AzureOperationsExecutor"] is binding.executor
    assert case.inputs[-1][0] is runtime
    assert_no_dependency_calls(case.dependencies)
    return runtime, binding, builder


def require_workflow_selector(case):
    runtime, binding, builder = build_workflow(case)
    _, positional, kwargs = case.inputs[-1]
    if "execution_bindings" not in kwargs:
        raise AssertionError(MISSING_WIRING)
    selector = kwargs["execution_bindings"]
    assert isinstance(selector, DomainExecutionBindings)
    assert kwargs.get("execution_binding") is None
    assert positional == ()
    assert len(case.collections) == len(case.probe.compositions) == len(case.probe.builders)
    assert case.collections[-1] is selector
    assert len(selector.bindings) == 1 and selector.bindings[0] is binding
    assert kwargs["procedure_capability_registry"] is case.registry
    assert case.events == case.selections == case.members == case.resolved == []
    return runtime, selector, binding, builder


def require_collection_input():
    parameter = signature(runtime_module.ProcedureRuntimeExecutor.__init__).parameters.get("execution_bindings")
    if parameter is None:
        raise AssertionError(MISSING_INPUT)
    assert parameter.kind is Parameter.KEYWORD_ONLY and parameter.default is None


def local_binding(executor_id="azure_operations"):
    return DomainExecutionBinding(operation_domain="azure", executor_id=executor_id,
                                  executor=OfflineExecutor(executor_id))


def direct_runtime(case, **kwargs):
    return runtime_module.ProcedureRuntimeExecutor(procedure_capability_registry=case.registry, **kwargs)


def construct(case, runtime):
    try:
        return runtime._build_runtime_state(case.context), None
    except DomainExecutionBindingError as error:
        return None, error
    finally:
        assert_no_dependency_calls(case.dependencies)


def assert_same_selection(case, selector):
    assert case.selections and all(s is selector and c is case.capability for s, c in case.selections)
    assert case.resolved and all(c is case.capability for c in case.resolved)


def make_read(case):
    result = case.context.result
    case.context = case.context.model_copy(update={"result": result.model_copy(update={
        "step": result.step.model_copy(update={"operation_kind": "read"}),
    })})


def test_workflow_injects_one_collection_with_the_actual_composed_binding(monkeypatch):
    case = instrument(monkeypatch)
    require_workflow_selector(case)
    assert case.state_calls == []


def test_repeated_workflow_builds_have_separate_collections_and_executors(monkeypatch):
    case = instrument(monkeypatch)
    first = require_workflow_selector(case)
    second = require_workflow_selector(case)
    assert first[0] is not second[0] and first[1] is not second[1]
    assert first[2] is not second[2] and first[2].executor is not second[2].executor
    assert_no_dependency_calls(case.dependencies)


def test_selector_constructor_failure_propagates_before_runtime_or_graph(monkeypatch):
    case = instrument(monkeypatch)
    failure = DomainExecutionBindingError("F26_6_CONSTRUCTOR_REJECTION")
    case.constructor_failure = failure
    caught = None
    try:
        workflow_module.build_incident_resolution_workflow(
            **case.dependencies, procedure_capability_registry=case.registry,
        )
    except DomainExecutionBindingError as error:
        caught = error
    if not case.collections:
        raise AssertionError(MISSING_WIRING)
    assert caught is failure and len(case.collections) == 1
    assert case.probe.builders == case.inputs == case.events == []
    assert_no_dependency_calls(case.dependencies)


def test_governed_capability_reaches_same_selector_and_member_before_state(monkeypatch):
    case = instrument(monkeypatch)
    before, cap_before = case.context.model_dump(mode="python"), asdict(case.capability)
    runtime, selector, binding, _ = require_workflow_selector(case)
    state, error = construct(case, runtime)
    assert error is None and state is not None
    assert_same_selection(case, selector)
    assert len(case.selections) == len(case.members) == len(case.resolved) == 1
    assert case.members[0][0] is binding and case.members[0][1] is case.capability
    assert case.events == ["policy", "selector", "binding", "state"]
    assert state.step.capability_id == case.capability.capability_id
    assert state.step.operation_action == case.capability.operation_action
    assert state.step.hitl_required is True and state.approval_id is None
    assert case.context.model_dump(mode="python") == before and asdict(case.capability) == cap_before


@pytest.mark.parametrize("executor_id", BAD_IDS)
def test_unknown_pair_rejects_before_state_without_any_member_attempt(monkeypatch, executor_id):
    case = instrument(monkeypatch, executor_id=executor_id)
    runtime, selector, _, _ = require_workflow_selector(case)
    state, error = construct(case, runtime)
    assert state is None and isinstance(error, DomainExecutionBindingError)
    assert_same_selection(case, selector)
    assert len(case.selections) == 1 and case.members == case.state_calls == []
    assert case.events == ["policy", "selector"]


@pytest.mark.parametrize("changed_id", ["changed", "Azure_Operations"])
def test_member_identity_is_rechecked_after_workflow_construction(monkeypatch, changed_id):
    case = instrument(monkeypatch)
    runtime, selector, binding, _ = require_workflow_selector(case)
    binding.executor.id = changed_id
    state, error = construct(case, runtime)
    assert state is None and isinstance(error, DomainExecutionBindingError)
    assert_same_selection(case, selector)
    assert len(case.members) == 1 and case.members[0][0] is binding and case.state_calls == []
    assert case.events == ["policy", "selector", "binding"]


@pytest.mark.parametrize("boundary", ["selector", "member"])
def test_selected_boundary_error_propagates_without_fallback(monkeypatch, boundary):
    case = instrument(monkeypatch)
    runtime, selector, binding, _ = require_workflow_selector(case)
    failure = DomainExecutionBindingError("F26_6_SELECTED_REJECTION")
    setattr(case, boundary + "_failure", failure)
    state, error = construct(case, runtime)
    assert state is None and error is failure and case.state_calls == []
    assert_same_selection(case, selector)
    expected = ["policy", "selector"] + (["binding"] if boundary == "member" else [])
    assert case.events == expected
    assert len(case.members) == int(boundary == "member")
    if case.members:
        assert case.members[0][0] is binding


def test_each_state_construction_rechecks_the_same_selector(monkeypatch):
    case = instrument(monkeypatch)
    runtime, selector, binding, _ = require_workflow_selector(case)
    first, error = construct(case, runtime)
    assert first is not None and error is None
    binding.executor.id = "changed_after_first_state"
    second, error = construct(case, runtime)
    assert second is None and isinstance(error, DomainExecutionBindingError)
    assert_same_selection(case, selector)
    assert len(case.selections) == len(case.members) == 2 and len(case.state_calls) == 1
    assert case.events == ["policy", "selector", "binding", "state", "policy", "selector", "binding"]


def test_governance_rejection_does_not_reach_selector_or_state(monkeypatch):
    case = instrument(monkeypatch)
    runtime, _, _, _ = require_workflow_selector(case)
    failure = ValueError("F26_6_GOVERNANCE_REJECTION")
    case.policy_failure = failure
    with pytest.raises(ValueError) as caught:
        runtime._build_runtime_state(case.context)
    assert caught.value is failure and case.events == ["policy"]
    assert case.selections == case.members == case.state_calls == []
    assert_no_dependency_calls(case.dependencies)


def test_composed_unbound_read_does_not_resolve_selector_or_member(monkeypatch):
    case = instrument(monkeypatch, bound=False)
    runtime, _, _, _ = require_workflow_selector(case)
    make_read(case)
    state, error = construct(case, runtime)
    assert error is None and state.step.capability_id is None and state.step.operation_action is None
    assert case.events == ["state"] and case.resolved == case.selections == case.members == []


def test_runtime_exposes_explicit_keyword_only_collection_input():
    require_collection_input()


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
def test_explicit_multi_binding_input_selects_governed_id_not_first_member(monkeypatch, reverse):
    require_collection_input()
    case = instrument(monkeypatch, executor_id="azure_secondary")
    first, selected = local_binding(), local_binding("azure_secondary")
    values = [first, selected]
    if reverse:
        values.reverse()
    selector = DomainExecutionBindings(bindings=values)
    runtime = direct_runtime(case, execution_bindings=selector)
    state, error = construct(case, runtime)
    assert error is None and state.step.capability_id == case.capability.capability_id
    assert_same_selection(case, selector)
    assert len(case.collections) == len(case.selections) == len(case.members) == 1
    assert case.members[0][0] is selected
    assert case.events == ["policy", "selector", "binding", "state"]
    # Local selection fixture only: these nodes are not claimed to belong to a graph.


@pytest.mark.parametrize("falsey", [False, True], ids=["ordinary", "falsey"])
def test_explicit_empty_collection_is_not_absent_composition(monkeypatch, falsey):
    require_collection_input()
    case = instrument(monkeypatch)
    class FalseyBindings(DomainExecutionBindings):
        def __bool__(self):
            return False
    cls = FalseyBindings if falsey else DomainExecutionBindings
    selector = cls(bindings=[])
    runtime = direct_runtime(case, execution_bindings=selector)
    state, error = construct(case, runtime)
    assert state is None and isinstance(error, DomainExecutionBindingError)
    assert_same_selection(case, selector)
    assert case.events == ["policy", "selector"] and case.members == case.state_calls == []


@pytest.mark.parametrize("kind", ["list", "tuple", "mapping", "duck", "single", "boolean"])
def test_collection_input_rejects_wrong_types_without_coercion(monkeypatch, kind):
    require_collection_input()
    case = instrument(monkeypatch)
    bad = {"list": [], "tuple": (), "mapping": {}, "duck": SimpleNamespace(resolve=lambda **k: None),
           "single": local_binding(), "boolean": False}[kind]
    with pytest.raises(DomainExecutionBindingError):
        direct_runtime(case, execution_bindings=bad)
    assert case.collections == case.inputs == case.events == []


@pytest.mark.parametrize("empty", [False, True], ids=["nonempty", "empty"])
def test_simultaneous_single_and_collection_inputs_are_rejected(monkeypatch, empty):
    require_collection_input()
    case = instrument(monkeypatch)
    binding = local_binding()
    selector = DomainExecutionBindings(bindings=[] if empty else [binding])
    with pytest.raises(DomainExecutionBindingError):
        direct_runtime(case, execution_binding=binding, execution_bindings=selector)
    assert len(case.collections) == 1 and case.inputs == case.events == []


@pytest.mark.parametrize("wrong", [False, True], ids=["exact", "incompatible"])
def test_legacy_single_binding_control_preserves_its_own_rejection_boundary(monkeypatch, wrong):
    case = instrument(monkeypatch, executor_id="unknown_executor" if wrong else "azure_operations")
    binding = local_binding()
    runtime = direct_runtime(case, execution_binding=binding)
    state, error = construct(case, runtime)
    assert case.selections == [] and len(case.members) == 1 and case.members[0][0] is binding
    if wrong:
        assert state is None and isinstance(error, DomainExecutionBindingError) and case.state_calls == []
        assert case.events == ["policy", "binding"]
    else:
        assert state is not None and error is None
        assert case.events == ["policy", "binding", "state"]


def test_standalone_absent_composition_control_keeps_only_state_compatibility(monkeypatch):
    case = instrument(monkeypatch)
    runtime = direct_runtime(case)
    state, error = construct(case, runtime)
    assert error is None and state.step.capability_id == case.capability.capability_id
    assert case.events == ["policy", "state"] and case.collections == case.selections == case.members == []
    # No composed-executor/graph-membership guarantee is asserted for this mode.


def test_standalone_unbound_read_control_does_not_acquire_authority(monkeypatch):
    case = instrument(monkeypatch, bound=False)
    runtime = direct_runtime(case)
    make_read(case)
    state, error = construct(case, runtime)
    assert error is None and state.step.capability_id is None and state.step.operation_action is None
    assert case.events == ["state"] and case.resolved == case.selections == case.members == []


def smoke_existing_integration():
    # Current fixtures and current gap only; not a persisted test of future behavior.
    assert "execution_bindings" not in signature(runtime_module.ProcedureRuntimeExecutor.__init__).parameters
    with pytest.MonkeyPatch.context() as patch:
        case = instrument(patch)
        runtime, binding, _ = build_workflow(case)
        assert case.inputs[-1][2]["execution_binding"] is binding and case.collections == []
        state, error = construct(case, runtime)
        assert error is None and state is not None
        assert case.events == ["policy", "binding", "state"]
    with pytest.MonkeyPatch.context() as patch:
        case = instrument(patch, executor_id="unknown_executor")
        runtime, binding, _ = build_workflow(case)
        state, error = construct(case, runtime)
        assert state is None and isinstance(error, DomainExecutionBindingError)
        assert case.events == ["policy", "binding"]
        selector = DomainExecutionBindings(bindings=[binding])
        case.events.clear()
        case.members.clear()
        with pytest.raises(DomainExecutionBindingError):
            selector.resolve(capability=case.capability)
        assert case.events == ["selector"] and case.members == []
    for wrong in (False, True):
        with pytest.MonkeyPatch.context() as patch:
            test_legacy_single_binding_control_preserves_its_own_rejection_boundary(patch, wrong)
    for control in (test_standalone_absent_composition_control_keeps_only_state_compatibility,
                    test_standalone_unbound_read_control_does_not_acquire_authority):
        with pytest.MonkeyPatch.context() as patch:
            control(patch)
