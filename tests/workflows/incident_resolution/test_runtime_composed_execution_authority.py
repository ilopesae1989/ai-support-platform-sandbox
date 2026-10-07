from dataclasses import replace
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
from src.workflows.incident_resolution.procedure_capability_registry import ProcedureCapabilityRegistry
from tests.workflows.incident_resolution.test_runtime_capability_binding import (
    create_execution_context, create_procedure_capability_registry,
)
from tests.workflows.incident_resolution.test_workflow_azure_composition_wiring import (
    install_probe, members, assert_graph, dependencies, assert_no_dependency_calls,
)

MISSING = "F26_4_EXPECTED_RED_COMPOSED_BINDING_NOT_CHECKED"
CONTROL = "test_unbound_read_does_not_acquire_capability_or_execution_authority"
BAD_IDS = (
    "unknown_executor", "Azure_Operations", "azure_operations.other", "*",
    "azure_pre_call_security", "azure_vm_post_operation_observation",
)


def prepare(monkeypatch, *, executor_id="azure_operations", bound=True, forced_error=None):
    context = create_execution_context()
    cap = replace(build_default_capability_registry().get("azure.vm.start"), executor_id=executor_id)
    existing = create_procedure_capability_registry().get_binding(
        procedure_id=context.result.procedure.id,
        procedure_version=context.result.procedure.version,
        step_id=context.result.step.id,
    )
    registry = ProcedureCapabilityRegistry(
        capability_registry=CapabilityRegistry(capabilities=[cap]),
        bindings=[existing] if bound else [],
    )
    events, attempts, resolved = [], [], []
    resolve_policy = registry.resolve_applicable_capability
    resolve_binding = DomainExecutionBinding.resolve

    def policy_spy(**kwargs):
        value = resolve_policy(**kwargs)
        resolved.append(value)
        events.append("policy")
        return value

    def binding_spy(self, *, capability):
        attempts.append((self, capability))
        events.append("binding")
        if forced_error is not None:
            raise forced_error
        return resolve_binding(self, capability=capability)

    monkeypatch.setattr(registry, "resolve_applicable_capability", policy_spy)
    monkeypatch.setattr(DomainExecutionBinding, "resolve", binding_spy)
    probe, deps = install_probe(monkeypatch), dependencies()
    workflow = workflow_module.build_incident_resolution_workflow(
        **deps, procedure_capability_registry=registry,
    )
    assert isinstance(workflow, Workflow)
    assert len(probe.compositions) == len(probe.builders) == 1
    builder, composition = probe.builders[0], probe.compositions[0]
    assert builder.result is workflow
    assert_graph(builder)
    runtime = members(builder)["ProcedureRuntimeExecutor"]
    binding = composition.execution_binding
    assert members(builder)["AzureOperationsExecutor"] is binding.executor
    # The requirement concerns each resolved step, not an eager default lookup.
    assert events == attempts == resolved == []

    state_type = runtime_module.ProcedureRuntimeState
    def record_state(*args, **kwargs):
        events.append("state")
        return state_type(*args, **kwargs)
    monkeypatch.setattr(runtime_module, "ProcedureRuntimeState", record_state)

    def forbidden(*args, **kwargs):
        raise AssertionError("F26_4_OPERATIONAL_DISPATCH_FORBIDDEN")
    for owner, name in ((Executor, "execute"), (Executor, "clone"), (Workflow, "run")):
        monkeypatch.setattr(owner, name, forbidden)
    return SimpleNamespace(runtime=runtime, context=context, capability=cap, binding=binding,
        events=events, attempts=attempts, resolved=resolved, dependencies=deps)


def evaluate(case):
    state, error = None, None
    try:
        state = case.runtime._build_runtime_state(case.context)
    except DomainExecutionBindingError as exc:
        error = exc
    assert_no_dependency_calls(case.dependencies)
    if not case.attempts:
        raise AssertionError(MISSING)
    assert all(binding is case.binding and cap is case.capability
               for binding, cap in case.attempts)
    assert all(cap is case.capability for cap in case.resolved)
    return state, error


def assert_rejected(case):
    state, error = evaluate(case)
    assert state is None and isinstance(error, DomainExecutionBindingError)
    assert case.events == ["policy", "binding"]
    return error


def smoke_current_gap():
    # Check actual fixtures and the known gap before creating the new file.
    for executor_id in ("azure_operations", *BAD_IDS):
        with pytest.MonkeyPatch.context() as patch:
            case = prepare(patch, executor_id=executor_id)
            state = case.runtime._build_runtime_state(case.context)
            assert state.step.capability_id == "azure.vm.start"
            assert case.events == ["policy", "state"] and case.attempts == []
            assert case.resolved == [case.capability]
            if executor_id == "azure_operations":
                assert case.binding.resolve(capability=case.capability) is case.binding.executor
            else:
                with pytest.raises(DomainExecutionBindingError):
                    case.binding.resolve(capability=case.capability)
            assert_no_dependency_calls(case.dependencies)
    with pytest.MonkeyPatch.context() as patch:
        test_unbound_read_does_not_acquire_capability_or_execution_authority(patch)


def test_runtime_checks_the_resolved_capability_against_the_actual_composed_binding(monkeypatch):
    case = prepare(monkeypatch)
    before = case.context.model_dump(mode="python")
    state, error = evaluate(case)
    assert error is None
    assert case.events == ["policy", "binding", "state"]
    assert state.step.capability_id == case.capability.capability_id
    assert state.step.operation_action == case.capability.operation_action
    assert state.step.hitl_required is True and state.approval_id is None
    assert case.context.model_dump(mode="python") == before


@pytest.mark.parametrize("executor_id", BAD_IDS)
def test_incompatible_capability_executor_is_rejected_before_runtime_state(monkeypatch, executor_id):
    # F26.6: observe the explicitly injected boundary, never infer it from failure.
    # Unknown keys reject at the collection; a legacy single binding rejects itself.
    from functools import wraps
    from src.workflows.incident_resolution.domain_execution_bindings import DomainExecutionBindings

    inputs, selections = [], []
    runtime_init = runtime_module.ProcedureRuntimeExecutor.__init__
    selector_resolve = DomainExecutionBindings.resolve
    case = None

    @wraps(runtime_init)
    def record_input(self, *args, **kwargs):
        result = runtime_init(self, *args, **kwargs)
        inputs.append((self, args, dict(kwargs)))
        return result

    def record_selection(self, *, capability):
        assert case is not None, "No eager capability selection during construction."
        selections.append((self, capability))
        case.events.append("selector")
        return selector_resolve(self, capability=capability)

    monkeypatch.setattr(runtime_module.ProcedureRuntimeExecutor, "__init__", record_input)
    monkeypatch.setattr(DomainExecutionBindings, "resolve", record_selection)
    case = prepare(monkeypatch, executor_id=executor_id)
    before = case.context.model_dump(mode="python")
    assert len(inputs) == 1 and inputs[0][0] is case.runtime and inputs[0][1] == ()
    configured = inputs[0][2]
    selector = configured.get("execution_bindings")
    single = configured.get("execution_binding")
    assert selections == []
    assert case.capability.executor_id == executor_id
    assert (case.capability.operation_domain, case.capability.executor_id) != (
        case.binding.operation_domain, case.binding.executor_id
    )

    if selector is None:
        # Preserve the existing, explicit singular route until wiring is migrated.
        assert single is case.binding
        assert_rejected(case)
        assert selections == []
        assert len(case.attempts) == 1
        assert case.attempts[0][0] is case.binding
        assert case.attempts[0][1] is case.capability
    else:
        # A collection must contain the real composed member, not a substitute.
        assert single is None
        assert isinstance(selector, DomainExecutionBindings)
        assert len(selector.bindings) == 1 and selector.bindings[0] is case.binding
        with pytest.raises(DomainExecutionBindingError):
            case.runtime._build_runtime_state(case.context)
        assert len(selections) == 1
        assert selections[0][0] is selector and selections[0][1] is case.capability
        assert case.attempts == []
        assert case.events == ["policy", "selector"]
        assert_no_dependency_calls(case.dependencies)

    assert len(case.resolved) == 1 and case.resolved[0] is case.capability
    assert case.context.model_dump(mode="python") == before


@pytest.mark.parametrize("changed_id", ("renamed_executor", "Azure_Operations"))
def test_actual_executor_identity_is_rechecked_after_workflow_construction(monkeypatch, changed_id):
    case = prepare(monkeypatch)
    case.binding.executor.id = changed_id
    assert_rejected(case)


def test_binding_failure_propagates_without_fallback_or_runtime_state(monkeypatch):
    failure = DomainExecutionBindingError("F26_4_SIMULATED_BINDING_REJECTION")
    case = prepare(monkeypatch, forced_error=failure)
    assert assert_rejected(case) is failure


def test_each_runtime_state_construction_rechecks_the_same_composed_binding(monkeypatch):
    case = prepare(monkeypatch)
    first, error = evaluate(case)
    assert error is None and first is not None
    case.binding.executor.id = "changed_after_first_check"
    second, error = evaluate(case)
    assert second is None and isinstance(error, DomainExecutionBindingError)
    assert len(case.attempts) == len(case.resolved) == 2
    assert case.events == ["policy", "binding", "state", "policy", "binding"]


def test_unbound_read_does_not_acquire_capability_or_execution_authority(monkeypatch):
    # Preserve the existing transitional READ contract; this grants no execution.
    case = prepare(monkeypatch, bound=False)
    result = case.context.result
    step = result.step.model_copy(update={"operation_kind": "read"})
    case.context = case.context.model_copy(update={"result": result.model_copy(update={"step": step})})
    state = case.runtime._build_runtime_state(case.context)
    assert state.step.capability_id is None and state.step.operation_action is None
    assert case.attempts == case.resolved == []
    assert case.events == ["state"]
    assert_no_dependency_calls(case.dependencies)
