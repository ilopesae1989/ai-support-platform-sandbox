from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from agent_framework import Case, Default, Executor, WorkflowContext, handler

import src.workflows.incident_resolution.workflow as workflow_module
from src.runtime.procedure.models import ApprovedProcedureStep, NextAction, OperationKind
from src.workflows.incident_resolution.domain_execution_binding import (
    DomainExecutionBinding,
)
from src.workflows.incident_resolution.domain_execution_path import (
    DomainExecutionPath,
    DomainExecutionPathError,
)
from src.workflows.incident_resolution.domain_execution_registry import (
    DomainExecutionRegistration,
    DomainExecutionRegistry,
    DomainExecutionRegistryError,
)
from src.workflows.incident_resolution.executors.post_hitl import (
    DatabaseRouteExecutor,
)
from tests.workflows.incident_resolution.test_azure_domain_composition import (
    assert_no_dependency_calls,
    dependencies,
)
from tests.workflows.incident_resolution.test_post_hitl_routing import (
    create_step,
)
from tests.workflows.incident_resolution.test_workflow_azure_composition_wiring import (
    assert_graph,
    install_probe,
    members,
)

MISSING = "F26_10_EXPECTED_RED_WORKFLOW_NOT_CONSUMING_DOMAIN_EXECUTION_REGISTRY"
PARAMETER = "domain_execution_registrations"


class SyntheticEntryExecutor(Executor):
    def __init__(self, executor_id: str) -> None:
        super().__init__(id=executor_id)

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[ApprovedProcedureStep],
    ) -> None:
        await ctx.send_message(step)


class SyntheticLifecycleExecutor(Executor):
    def __init__(self, executor_id: str) -> None:
        super().__init__(id=executor_id)

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[ApprovedProcedureStep],
    ) -> None:
        await ctx.send_message(step)


class SyntheticOperationExecutor(Executor):
    def __init__(self, executor_id: str) -> None:
        super().__init__(id=executor_id)

    @handler
    async def handle(
        self,
        step: ApprovedProcedureStep,
        ctx: WorkflowContext[ApprovedProcedureStep],
    ) -> None:
        await ctx.send_message(step)


def require_extension_contract() -> None:
    signature = inspect.signature(
        workflow_module.build_incident_resolution_workflow
    )
    parameter = signature.parameters.get(PARAMETER)
    if parameter is None:
        raise AssertionError(MISSING)
    if parameter.default is not None:
        raise AssertionError(MISSING)
    if not hasattr(workflow_module, "DomainExecutionRegistry"):
        raise AssertionError(MISSING)


def synthetic_registration(
    domain: str = "storage",
    prefix: str = "storage_fixture",
) -> DomainExecutionRegistration:
    entry = SyntheticEntryExecutor(f"{prefix}_entry")
    lifecycle = SyntheticLifecycleExecutor(f"{prefix}_lifecycle")
    operation = SyntheticOperationExecutor(f"{prefix}_operations")
    binding = DomainExecutionBinding(
        operation_domain=domain,
        executor_id=operation.id,
        executor=operation,
    )
    path = DomainExecutionPath(
        execution_binding=binding,
        executors=(entry, lifecycle, operation),
    )
    return DomainExecutionRegistration(
        operation_domain=domain,
        execution_path=path,
    )


def build_with_probe(
    monkeypatch,
    *,
    registrations=(),
):
    require_extension_contract()
    probe = install_probe(monkeypatch)
    captured = []
    real_registry = DomainExecutionRegistry

    def registry_spy(*, registrations):
        result = real_registry(registrations=registrations)
        captured.append(result)
        return result

    monkeypatch.setattr(
        workflow_module,
        "DomainExecutionRegistry",
        registry_spy,
    )

    deps = dependencies()
    result = workflow_module.build_incident_resolution_workflow(
        **deps,
        domain_execution_registrations=registrations,
    )

    assert len(probe.builders) == 1
    assert len(probe.compositions) == 1
    assert len(captured) == 1
    return SimpleNamespace(
        probe=probe,
        builder=probe.builders[0],
        composition=probe.compositions[0],
        registry=captured[0],
        deps=deps,
        workflow=result,
    )


def switch_cases(builder):
    assert len(builder.switches) == 1
    source, cases = builder.switches[0]
    assert source.id == "procedure_approval"
    return cases


def case_for_target(cases, target):
    matches = [
        case
        for case in cases
        if isinstance(case, Case) and case.target is target
    ]
    assert len(matches) == 1
    return matches[0]


def test_workflow_signature_exposes_optional_domain_execution_registrations():
    require_extension_contract()
    signature = inspect.signature(
        workflow_module.build_incident_resolution_workflow
    )
    parameter = signature.parameters[PARAMETER]
    assert parameter.default is None


def test_default_composition_builds_one_registry_with_exact_azure_path(monkeypatch):
    built = build_with_probe(monkeypatch)
    registry = built.registry
    composition = built.composition
    assert len(registry.registrations) == 1
    azure = registry.get("azure")
    assert azure.execution_path is composition.execution_path
    assert azure.execution_path.execution_binding is composition.execution_binding
    assert_no_dependency_calls(built.deps)


def test_runtime_consumes_same_persistent_registry_execution_bindings(monkeypatch):
    built = build_with_probe(monkeypatch)
    runtime = members(built.builder)["ProcedureRuntimeExecutor"]
    assert runtime._execution_bindings is built.registry.execution_bindings
    assert runtime._execution_bindings.bindings == (
        built.composition.execution_binding,
    )
    assert_no_dependency_calls(built.deps)


def test_default_configuration_preserves_exact_existing_graph(monkeypatch):
    built = build_with_probe(monkeypatch)
    assert_graph(built.builder)
    assert_no_dependency_calls(built.deps)


def test_synthetic_second_domain_registration_is_preserved_by_identity(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    assert len(built.registry.registrations) == 2
    assert built.registry.get("storage") is registration
    assert built.registry.execution_paths[1] is registration.execution_path
    assert_no_dependency_calls(built.deps)


def test_synthetic_second_domain_adds_exact_switch_target_to_path_entry(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    cases = switch_cases(built.builder)
    registered_case = case_for_target(
        cases,
        registration.execution_path.entry,
    )
    assert registered_case.target is registration.execution_path.entry
    assert_no_dependency_calls(built.deps)


def test_registered_domain_condition_is_exact_deterministic_and_fail_closed(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    condition = case_for_target(
        switch_cases(built.builder),
        registration.execution_path.entry,
    ).condition

    assert condition(create_step(domain="storage")) is True
    assert condition(create_step(domain="Storage")) is False
    assert condition(create_step(domain="storage ")) is False
    assert condition(create_step(domain="storage", approved=False)) is False
    assert condition(create_step(domain="storage", kind=OperationKind.WAIT)) is False
    assert condition(
        create_step(
            domain="storage",
            next_action=NextAction.CONTINUE,
        )
    ) is False
    assert_no_dependency_calls(built.deps)


def test_synthetic_second_domain_adds_all_declared_path_edges_exactly(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    actual = {
        (id(source), id(target))
        for source, target, _ in built.builder.edges
    }
    for source, target in registration.execution_path.edges:
        assert (id(source), id(target)) in actual
    assert_no_dependency_calls(built.deps)


def test_runtime_selector_contains_azure_and_synthetic_bindings_same_instances(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    runtime = members(built.builder)["ProcedureRuntimeExecutor"]
    assert runtime._execution_bindings is built.registry.execution_bindings
    assert runtime._execution_bindings.bindings == (
        built.composition.execution_binding,
        registration.execution_path.execution_binding,
    )
    assert_no_dependency_calls(built.deps)


def test_unlisted_registered_domain_does_not_remove_legacy_placeholders(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    cases = switch_cases(built.builder)
    target_names = [
        type(case.target).__name__
        for case in cases
        if isinstance(case, Case)
    ]
    for expected in (
        "DatabaseRouteExecutor",
        "ItsmRouteExecutor",
        "WindowsRouteExecutor",
        "LinuxRouteExecutor",
        "NetworkingRouteExecutor",
        "Microsoft365RouteExecutor",
    ):
        assert expected in target_names
    assert_no_dependency_calls(built.deps)


def test_registered_legacy_domain_replaces_placeholder_case_without_duplicate(monkeypatch):
    registration = synthetic_registration(
        domain="database",
        prefix="database_fixture",
    )
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    cases = switch_cases(built.builder)
    assert case_for_target(
        cases,
        registration.execution_path.entry,
    ).target is registration.execution_path.entry
    assert not any(
        isinstance(case, Case)
        and isinstance(case.target, DatabaseRouteExecutor)
        for case in cases
    )
    assert_no_dependency_calls(built.deps)


def test_registered_legacy_domain_removes_disconnected_placeholder_from_outputs(monkeypatch):
    registration = synthetic_registration(
        domain="database",
        prefix="database_fixture",
    )
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    assert not any(
        isinstance(node, DatabaseRouteExecutor)
        for node in built.builder.options["output_from"]
    )
    assert_no_dependency_calls(built.deps)


def test_other_legacy_placeholders_remain_when_database_is_registered(monkeypatch):
    registration = synthetic_registration(
        domain="database",
        prefix="database_fixture",
    )
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    cases = switch_cases(built.builder)
    target_names = {
        type(case.target).__name__
        for case in cases
        if isinstance(case, Case)
    }
    assert {
        "ItsmRouteExecutor",
        "WindowsRouteExecutor",
        "LinuxRouteExecutor",
        "NetworkingRouteExecutor",
        "Microsoft365RouteExecutor",
    }.issubset(target_names)
    assert_no_dependency_calls(built.deps)


def test_fail_closed_default_is_preserved_with_registered_domain(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    cases = switch_cases(built.builder)
    defaults = [case for case in cases if isinstance(case, Default)]
    assert len(defaults) == 1
    assert type(defaults[0].target).__name__ == "BlockedRouteExecutor"

    unknown = create_step(domain="quantum")
    assert all(
        case.condition(unknown) is False
        for case in cases
        if isinstance(case, Case)
    )
    assert_no_dependency_calls(built.deps)


def test_duplicate_azure_registration_fails_before_builder(monkeypatch):
    require_extension_contract()
    registration = synthetic_registration(
        domain="azure",
        prefix="duplicate_azure",
    )
    probe = install_probe(monkeypatch)
    with pytest.raises(DomainExecutionRegistryError):
        workflow_module.build_incident_resolution_workflow(
            **dependencies(),
            domain_execution_registrations=(registration,),
        )
    assert probe.builders == []


def test_mutated_synthetic_path_fails_before_builder(monkeypatch):
    require_extension_contract()
    registration = synthetic_registration()
    entry = registration.execution_path.executors[0]
    entry.id = entry.id + "_changed"
    probe = install_probe(monkeypatch)
    with pytest.raises(DomainExecutionPathError):
        workflow_module.build_incident_resolution_workflow(
            **dependencies(),
            domain_execution_registrations=(registration,),
        )
    assert probe.builders == []


def test_synthetic_endpoint_is_not_wired_into_azure_post_operation_chain(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    endpoint = registration.execution_path.execution_binding.executor
    pairs = [
        (source, target)
        for source, target, _ in built.builder.edges
    ]
    azure_registration = members(built.builder)["OperationResultRegistrationExecutor"]
    azure_observation = members(built.builder)["AzureVmPostOperationObservationExecutor"]
    assert (endpoint, azure_registration) not in pairs
    assert (endpoint, azure_observation) not in pairs
    assert_no_dependency_calls(built.deps)


def test_azure_post_operation_and_wait_edges_remain_exact_with_second_domain(monkeypatch):
    registration = synthetic_registration()
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    graph = members(built.builder)
    pairs = [
        (source, target)
        for source, target, _ in built.builder.edges
    ]
    azure_endpoint = built.composition.execution_binding.executor
    operation_registration = graph["OperationResultRegistrationExecutor"]
    observation = graph["AzureVmPostOperationObservationExecutor"]
    validation = graph["ProcedureValidationExecutor"]
    transition = graph["ProcedureTransitionExecutor"]

    assert (azure_endpoint, operation_registration) in pairs
    assert (operation_registration, observation) in pairs
    assert (observation, validation) in pairs
    assert (transition, observation) in pairs
    assert_no_dependency_calls(built.deps)


def test_synthetic_domain_name_is_absent_from_workflow_source(monkeypatch):
    registration = synthetic_registration(
        domain="storage",
        prefix="storage_fixture",
    )
    built = build_with_probe(
        monkeypatch,
        registrations=(registration,),
    )
    source = inspect.getsource(
        workflow_module.build_incident_resolution_workflow
    )
    assert '"storage"' not in source
    assert "'storage'" not in source
    assert "storage_fixture" not in source
    assert built.registry.get("storage") is registration
    assert_no_dependency_calls(built.deps)
