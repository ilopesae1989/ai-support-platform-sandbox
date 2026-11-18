from __future__ import annotations

from src.workflows.incident_resolution.vm_start_foundry_binding import GovernedVmStartRoute

from collections.abc import Iterable

from agent_framework import (
    Case,
    Default,
    WorkflowBuilder,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
)

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureVmPowerStateReader,
)

from src.workflows.incident_resolution.azure_domain_composition import (
    build_azure_domain_composition,
)

from src.workflows.incident_resolution.capability_foundry_agent_binding import (
    CapabilityFoundryAgentBindingRegistry,
)

from src.workflows.incident_resolution.domain_execution_registry import (
    DomainExecutionRegistration,
    DomainExecutionRegistry,
)

from src.workflows.incident_resolution.executors.operation_result_registration import (
    OperationResultRegistrationExecutor,
)

from src.workflows.incident_resolution.executors.classification import (
    ClassificationExecutor,
)

from src.workflows.incident_resolution.executors.knowledge import (
    KnowledgeExecutor,
)

from src.workflows.incident_resolution.executors.post_hitl import (
    BlockedRouteExecutor,
    DatabaseRouteExecutor,
    ItsmRouteExecutor,
    LinuxRouteExecutor,
    Microsoft365RouteExecutor,
    NetworkingRouteExecutor,
    WindowsRouteExecutor,
)

from src.workflows.incident_resolution.executors.procedure import (
    ProcedureExecutionExecutor,
)

from src.workflows.incident_resolution.executors.procedure_validation import (
    ProcedureValidationExecutor,
)

from src.workflows.incident_resolution.executors.procedure_transition import (
    ProcedureTransitionExecutor,
)

from src.workflows.incident_resolution.executors.routing import (
    KnowledgeReviewExecutor,
    ManualAnalysisExecutor,
    ProcedureRequestExecutor,
)

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)

from src.workflows.incident_resolution.executors.triage import (
    AlertTriageExecutor,
)

from src.workflows.incident_resolution.operation_dispatch_ledger import (
    InMemoryOperationDispatchLedger,
    OperationDispatchLedger,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    InMemoryWaitRecheckConsumptionLedger,
    WaitRecheckConsumptionLedger,
)

from src.workflows.incident_resolution.resource_identity_registry import (
    ResourceIdentityRegistry,
    build_default_resource_identity_registry,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    ProcedureCapabilityRegistry,
    build_default_procedure_capability_registry,
)

from src.workflows.incident_resolution.governed_procedure_admission import (
    GovernedProcedureAdmissionPolicy,
    build_default_governed_procedure_admission_policy,
)

from src.workflows.incident_resolution.routing import (
    route_to_knowledge_review,
    route_to_manual_analysis,
    route_to_procedure_execution,
)

from src.workflows.incident_resolution.routing_post_hitl import (
    build_registered_operation_route,
    route_to_azure_operation,
    route_to_database_operation,
    route_to_itsm_operation,
    route_to_linux_operation,
    route_to_microsoft365_operation,
    route_to_networking_operation,
    route_to_windows_operation,
)


def _add_registered_execution_paths(
    builder: WorkflowBuilder,
    registrations: tuple[DomainExecutionRegistration, ...],
) -> WorkflowBuilder:
    """Añade únicamente los edges declarados por registrations adicionales."""
    for registration in registrations:
        for source, target in registration.execution_path.edges:
            builder.add_edge(
                source,
                target,
            )
    return builder


def build_incident_resolution_workflow(
    agents: FoundryAgents | None = None,

    operation_dispatch_ledger: (
        OperationDispatchLedger | None
    ) = None,

    wait_recheck_consumption_ledger: (
        WaitRecheckConsumptionLedger | None
    ) = None,

    azure_vm_power_state_reader: (
        AzureVmPowerStateReader | None
    ) = None,

    resource_identity_registry: (
        ResourceIdentityRegistry | None
    ) = None,

    procedure_capability_registry: (
        ProcedureCapabilityRegistry | None
    ) = None,

    governed_procedure_admission_policy: (
        GovernedProcedureAdmissionPolicy | None
    ) = None,

    domain_execution_registrations: (
        Iterable[DomainExecutionRegistration] | None
    ) = None,

    capability_foundry_agent_binding_registry: (
        CapabilityFoundryAgentBindingRegistry | None
    ) = None,
    vm_start_route: GovernedVmStartRoute | None = None,
    attestation_publisher=None,
    execution_affinity=None,
    affinity_procedures=None,
    execution_store=None,
):
    """
    IncidentResolutionWorkflow.

    Pipeline cognitivo:

        NormalizedAlert
            ↓
        Classification
            ↓
        Knowledge
            ↓
        Alert Triage

    Routing determinista pre-HITL:

        exact + eligible
            ↓
        Procedure Request
            ↓
        Procedure Execution
            ↓
        Procedure Runtime
            ↓
        Approval / HITL

        partial / exact non-eligible
            ↓
        Knowledge Review

        none / human escalation
            ↓
        Manual Analysis

    Routing determinista post-HITL:

        ApprovedProcedureStep
            ↓
        switch Python
            │
            ├─ azure
            │     ↓
            │ AzurePreCallSecurityExecutor
            │     ↓
            │ PreCallSecurityVerifier
            │     ↓
            │ VerifiedAzureOperationRequest
            │     ↓
            │ OperationStartExecutor
            │     ↓
            │ AzureOperationsExecutor
            │     ↓
            │ OperationDispatchLedger
            │     ↓
            │ agent-azure-operations
            │     ↓
            │ Azure MCP
            │
            ├─ database
            ├─ itsm
            ├─ windows
            ├─ linux
            ├─ networking
            ├─ microsoft365
            └─ Default → blocked

    OperationDispatchLedger constituye una autoridad
    monotónica externa al checkpoint del workflow.

    Restaurar un checkpoint histórico no puede devolver
    al estado "no consumido" un operation_id que ya fue
    reclamado.

    En ausencia de implementación inyectada se utiliza
    InMemoryOperationDispatchLedger.

    Esa implementación sirve para tests y sandbox de
    proceso único. Producción deberá inyectar una
    implementación durable y atómica.

    Ningún LLM decide:

    - el routing;
    - la aprobación;
    - el resource scope autorizado;
    - los parámetros autorizados;
    - la verificación pre-call;
    - el consumo de operation_id.
    """

    # Strict candidate path: configuration identity is supplied by the trusted
    # factory, never taken from an alert, channel action or restored state.
    if execution_affinity is not None:
        from src.runtime.execution_affinity import ExecutionAffinity
        from src.config.procedure_configuration import ProcedureConfiguration
        if type(execution_affinity) is not ExecutionAffinity:
            raise TypeError("execution_affinity must be ExecutionAffinity.")
        if (type(affinity_procedures) is not ProcedureConfiguration
                or affinity_procedures.fingerprint != execution_affinity.procedures_sha256):
            raise ValueError("Execution affinity requires its exact procedure snapshot.")
        if getattr(agents, "deployment_fingerprint", None) != execution_affinity.foundry_sha256:
            raise ValueError("Execution affinity requires its exact Foundry configuration.")
        if any(value is not None for value in (
            procedure_capability_registry, governed_procedure_admission_policy,
            domain_execution_registrations, resource_identity_registry,
        )):
            raise ValueError("Affinity cannot be combined with unversioned procedure/domain overrides.")
        verified = affinity_procedures.verified_workflow_options()
        procedure_capability_registry = verified["procedure_capability_registry"]
        governed_procedure_admission_policy = verified["governed_procedure_admission_policy"]
    elif affinity_procedures is not None:
        raise ValueError("affinity_procedures requires an explicit execution affinity.")
    if execution_store is not None:
        from src.runtime.incident_execution import IncidentExecutionStore
        if (execution_affinity is None or not isinstance(execution_store, IncidentExecutionStore)
                or execution_store.execution_affinity != execution_affinity):
            raise ValueError("Execution admission requires the matching affinity store.")

    foundry_agents = (
        agents if agents is not None else FoundryAgents()
    )

    dispatch_ledger = (
        operation_dispatch_ledger
        if operation_dispatch_ledger is not None
        else InMemoryOperationDispatchLedger()
    )

    if (
        wait_recheck_consumption_ledger
        is None
    ):
        wait_recheck_ledger = (
            InMemoryWaitRecheckConsumptionLedger()
        )
    else:
        wait_recheck_ledger = (
            wait_recheck_consumption_ledger
        )

    identity_registry = (
        resource_identity_registry
        or build_default_resource_identity_registry()
    )

    procedure_registry = (
        procedure_capability_registry
        or (
            build_default_procedure_capability_registry()
        )
    )

    if governed_procedure_admission_policy is None:
        governed_admission = (
            build_default_governed_procedure_admission_policy()
        )
    else:
        governed_admission = (
            governed_procedure_admission_policy
        )

    #
    # --------------------------------------------------
    # Cognitive pipeline
    # --------------------------------------------------
    #

    # The SDK graph signature contains executor IDs. Bind the start node to
    # trusted deployment configuration so restore rejects changed publications
    # before any handler runs. Legacy graph IDs remain unchanged. This is a
    # compatibility barrier, not a migration or remote-session recovery mechanism.
    classification_options = {}
    deployment_fingerprint = getattr(foundry_agents, "deployment_fingerprint", None)
    if isinstance(deployment_fingerprint, str):
        import re
        if not re.fullmatch(r"[0-9a-f]{64}", deployment_fingerprint):
            raise ValueError("Invalid deployment fingerprint.")
        classification_options["id"] = "classification-" + deployment_fingerprint
    if execution_affinity is not None:
        classification_options["id"] = "classification-affinity-" + execution_affinity.fingerprint
        classification_options["execution_affinity"] = execution_affinity
    if execution_store is not None:
        classification_options["id"] += "-admitted-v1"
        classification_options["execution_store"] = execution_store
    classification = (
        ClassificationExecutor(
            agents=foundry_agents,
            **classification_options,
        )
    )

    knowledge = (
        KnowledgeExecutor(
            agents=foundry_agents,
        )
    )

    triage = (
        AlertTriageExecutor(
            agents=foundry_agents,
        )
    )

    #
    # --------------------------------------------------
    # Pre-HITL deterministic routing
    # --------------------------------------------------
    #

    procedure_request = (
        ProcedureRequestExecutor(
            admission_policy=(
                governed_admission
            ),
        )
    )

    knowledge_review = (
        KnowledgeReviewExecutor()
    )

    manual_analysis = (
        ManualAnalysisExecutor()
    )

    #
    # --------------------------------------------------
    # Procedure pipeline
    # --------------------------------------------------
    #

    procedure = (
        ProcedureExecutionExecutor(
            agents=foundry_agents,
        )
    )

    # Preserve the F26/F27.1 default factory kwargs exactly when disabled.
    selector_options = {}
    transition_options = {}
    if attestation_publisher is not None:
        from src.attestation.governor_outbox import GovernorAttestationPublisher
        if type(attestation_publisher) is not GovernorAttestationPublisher:
            raise TypeError("Explicit governor attestation publisher required")
        selector_options["attestation_publisher"] = attestation_publisher
    if vm_start_route is not None:
        if not isinstance(vm_start_route, GovernedVmStartRoute):
            raise TypeError("vm_start_route must be GovernedVmStartRoute.")
        selector_options["vm_start_route"] = vm_start_route
    if capability_foundry_agent_binding_registry is not None:
        if not isinstance(
            capability_foundry_agent_binding_registry,
            CapabilityFoundryAgentBindingRegistry,
        ):
            raise TypeError("Invalid capability Foundry agent binding registry.")
        selector_options["capability_foundry_agent_binding_registry"] = (
            capability_foundry_agent_binding_registry
        )
        # Resolve once from trusted composition. Even an explicitly empty
        # registry stays empty; result acceptance cannot fall back to legacy.
        read_authorities = capability_foundry_agent_binding_registry.read_authority_registry()
        selector_options["azure_read_tool_authority_registry"] = read_authorities
        transition_options["azure_read_tool_authority_registry"] = read_authorities

    azure_composition = build_azure_domain_composition(
        agents=foundry_agents,
        operation_dispatch_ledger=dispatch_ledger,
        wait_recheck_consumption_ledger=wait_recheck_ledger,
        azure_vm_power_state_reader=azure_vm_power_state_reader,
        **selector_options,
    )

    azure_execution_path = (
        azure_composition.execution_path
    )

    azure_path_edges = (
        azure_execution_path.edges
    )

    azure_registration = (
        DomainExecutionRegistration(
            operation_domain="azure",
            execution_path=azure_execution_path,
        )
    )

    if domain_execution_registrations is None:
        additional_domain_registrations = ()
    else:
        additional_domain_registrations = tuple(
            domain_execution_registrations
        )

    domain_execution_registry = DomainExecutionRegistry(
        registrations=(
            azure_registration,
            *additional_domain_registrations,
        ),
    )

    execution_bindings = (
        domain_execution_registry.execution_bindings
    )

    registered_additional_domains = frozenset(
        registration.operation_domain
        for registration
        in additional_domain_registrations
    )

    runtime = (
        ProcedureRuntimeExecutor(
            resource_identity_registry=(identity_registry),
            procedure_capability_registry=(procedure_registry),
            execution_bindings=(execution_bindings),
        )
    )

    approval_options = {}
    if vm_start_route is not None:
        approval_options["vm_start_binding_fingerprint"] = vm_start_route.binding.fingerprint
    approval = (
        ProcedureApprovalExecutor(**approval_options)
    )

    #
    # --------------------------------------------------
    # Azure pre-call security
    # --------------------------------------------------
    #


    azure_pre_call = (
        azure_execution_path.entry
    )

    operation_start = (
        azure_path_edges[0][1]
    )

    #
    # --------------------------------------------------
    # Azure Operations
    # --------------------------------------------------
    #

    azure_route = (
        azure_path_edges[-1][1]
    )

    operation_result_registration = (
        OperationResultRegistrationExecutor()
    )

    azure_vm_post_operation_observation = (
        azure_composition.post_operation_observation
    )

    procedure_validation = (
        ProcedureValidationExecutor(
            agents=foundry_agents,
        )
    )

    procedure_transition = (
        ProcedureTransitionExecutor(
            wait_recheck_consumption_ledger=(
                wait_recheck_ledger
            ),
            **transition_options,
        )
    )

    #
    # --------------------------------------------------
    # Remaining post-HITL placeholders
    # --------------------------------------------------
    #

    database_route = (
        DatabaseRouteExecutor()
    )

    itsm_route = (
        ItsmRouteExecutor()
    )

    windows_route = (
        WindowsRouteExecutor()
    )

    linux_route = (
        LinuxRouteExecutor()
    )

    networking_route = (
        NetworkingRouteExecutor()
    )

    microsoft365_route = (
        Microsoft365RouteExecutor()
    )

    #
    # --------------------------------------------------
    # Fail-closed
    # --------------------------------------------------
    #

    blocked_route = (
        BlockedRouteExecutor()
    )

    legacy_routes = (
        ("database", route_to_database_operation, database_route),
        ("itsm", route_to_itsm_operation, itsm_route),
        ("windows", route_to_windows_operation, windows_route),
        ("linux", route_to_linux_operation, linux_route),
        ("networking", route_to_networking_operation, networking_route),
        ("microsoft365", route_to_microsoft365_operation, microsoft365_route),
    )

    active_legacy_routes = tuple(
        route
        for route in legacy_routes
        if route[0] not in registered_additional_domains
    )

    post_hitl_cases = [
        Case(
            condition=route_to_azure_operation,
            target=azure_pre_call,
        ),
        *[
            Case(condition=condition, target=target)
            for _, condition, target in active_legacy_routes
        ],
        *[
            Case(
                condition=build_registered_operation_route(
                    registration.operation_domain
                ),
                target=registration.execution_path.entry,
            )
            for registration in additional_domain_registrations
        ],
        Default(target=blocked_route),
    ]

    legacy_outputs = [
        target
        for _, _, target in active_legacy_routes
    ]

    #
    # --------------------------------------------------
    # Build graph
    # --------------------------------------------------
    #

    return (
        _add_registered_execution_paths(
            WorkflowBuilder(
            max_iterations=100,

            start_executor=classification,

            output_from=[
                approval,
                knowledge_review,
                manual_analysis,
                procedure_transition,
                *legacy_outputs,
                blocked_route,
            ],

            name="incident-resolution",
        )

        #
        # Cognitive pipeline
        #

        .add_edge(
            classification,
            knowledge,
        )

        .add_edge(
            knowledge,
            triage,
        )

        #
        # Deterministic pre-HITL routing
        #

        .add_edge(
            triage,
            procedure_request,
            condition=(
                route_to_procedure_execution
            ),
        )

        .add_edge(
            triage,
            knowledge_review,
            condition=(
                route_to_knowledge_review
            ),
        )

        .add_edge(
            triage,
            manual_analysis,
            condition=(
                route_to_manual_analysis
            ),
        )

        #
        # Procedure pipeline
        #

        .add_edge(
            procedure_request,
            procedure,
        )

        .add_edge(
            procedure,
            runtime,
        )

        .add_edge(
            runtime,
            approval,
        )

        #
        # Deterministic POST-HITL routing
        #

        .add_switch_case_edge_group(
            approval,
            post_hitl_cases,
        )

        #
        # Verified pre-call
        #     ↓
        # deterministic lifecycle
        #     ↓
        # monotonic dispatch gate
        #     ↓
        # Azure Operations
        #

        .add_edge(
            azure_pre_call,
            operation_start,
        )

        .add_edge(
            operation_start,
            azure_route,
        ),
            additional_domain_registrations,
        )

        #
        # --------------------------------------------------
        # Post-operation validation loop
        # --------------------------------------------------
        #
        # AzureOperationResult
        #     ↓
        # authoritative registration
        #     ↓
        # deterministic VM post-operation observation
        #     ↓
        # Procedure Validation
        #     ↓
        # deterministic Transition Gate
        #

        .add_edge(
            azure_route,
            operation_result_registration,
        )

        .add_edge(
            operation_result_registration,
            azure_vm_post_operation_observation,
        )

        .add_edge(
            azure_vm_post_operation_observation,
            procedure_validation,
        )

        .add_edge(
            procedure_validation,
            procedure_transition,
        )

        #
        # Governed procedure continuation.
        #
        # CONTINUE y REPEAT vuelven al Procedure
        # executor mediante target_id explícito.
        #
        .add_edge(
            procedure_transition,
            procedure,
        )

        #
        # WAIT reanudado no repite el WRITE.
        # La señal externa sólo habilita una
        # observación read-only nueva antes de
        # Procedure Validation.
        #
        .add_edge(
            procedure_transition,
            azure_vm_post_operation_observation,
        )

        .build()
    )
