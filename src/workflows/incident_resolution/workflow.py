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

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.executors.azure_pre_call import (
    AzurePreCallSecurityExecutor,
)

from src.workflows.incident_resolution.executors.operation_lifecycle import (
    OperationStartExecutor,
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

from src.workflows.incident_resolution.resource_identity_registry import (
    ResourceIdentityRegistry,
    build_default_resource_identity_registry,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    ProcedureCapabilityRegistry,
    build_default_procedure_capability_registry,
)

from src.workflows.incident_resolution.routing import (
    route_to_knowledge_review,
    route_to_manual_analysis,
    route_to_procedure_execution,
)

from src.workflows.incident_resolution.routing_post_hitl import (
    route_to_azure_operation,
    route_to_database_operation,
    route_to_itsm_operation,
    route_to_linux_operation,
    route_to_microsoft365_operation,
    route_to_networking_operation,
    route_to_windows_operation,
)


def build_incident_resolution_workflow(
    agents: FoundryAgents | None = None,

    operation_dispatch_ledger: (
        OperationDispatchLedger | None
    ) = None,

    resource_identity_registry: (
        ResourceIdentityRegistry | None
    ) = None,

    procedure_capability_registry: (
        ProcedureCapabilityRegistry | None
    ) = None,
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

    foundry_agents = (
        agents
        or FoundryAgents()
    )

    dispatch_ledger = (
        operation_dispatch_ledger
        or InMemoryOperationDispatchLedger()
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

    #
    # --------------------------------------------------
    # Cognitive pipeline
    # --------------------------------------------------
    #

    classification = (
        ClassificationExecutor(
            agents=foundry_agents,
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
        ProcedureRequestExecutor()
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

    runtime = (
        ProcedureRuntimeExecutor(
            resource_identity_registry=(
                identity_registry
            ),

            procedure_capability_registry=(
                procedure_registry
            )
        )
    )

    approval = (
        ProcedureApprovalExecutor()
    )

    #
    # --------------------------------------------------
    # Azure pre-call security
    # --------------------------------------------------
    #

    azure_pre_call = (
        AzurePreCallSecurityExecutor()
    )

    operation_start = (
        OperationStartExecutor()
    )

    #
    # --------------------------------------------------
    # Azure Operations
    # --------------------------------------------------
    #

    azure_route = (
        AzureOperationsExecutor(
            agents=foundry_agents,
            operation_dispatch_ledger=(
                dispatch_ledger
            ),
        )
    )

    operation_result_registration = (
        OperationResultRegistrationExecutor()
    )

    procedure_validation = (
        ProcedureValidationExecutor(
            agents=foundry_agents,
        )
    )

    procedure_transition = (
        ProcedureTransitionExecutor()
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

    #
    # --------------------------------------------------
    # Build graph
    # --------------------------------------------------
    #

    return (
        WorkflowBuilder(
            start_executor=classification,

            output_from=[
                approval,
                knowledge_review,
                manual_analysis,
                procedure_transition,
                database_route,
                itsm_route,
                windows_route,
                linux_route,
                networking_route,
                microsoft365_route,
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
            [
                #
                # Azure
                #
                Case(
                    condition=(
                        route_to_azure_operation
                    ),
                    target=(
                        azure_pre_call
                    ),
                ),

                #
                # Database
                #
                Case(
                    condition=(
                        route_to_database_operation
                    ),
                    target=(
                        database_route
                    ),
                ),

                #
                # ITSM
                #
                Case(
                    condition=(
                        route_to_itsm_operation
                    ),
                    target=(
                        itsm_route
                    ),
                ),

                #
                # Windows
                #
                Case(
                    condition=(
                        route_to_windows_operation
                    ),
                    target=(
                        windows_route
                    ),
                ),

                #
                # Linux
                #
                Case(
                    condition=(
                        route_to_linux_operation
                    ),
                    target=(
                        linux_route
                    ),
                ),

                #
                # Networking
                #
                Case(
                    condition=(
                        route_to_networking_operation
                    ),
                    target=(
                        networking_route
                    ),
                ),

                #
                # Microsoft 365
                #
                Case(
                    condition=(
                        route_to_microsoft365_operation
                    ),
                    target=(
                        microsoft365_route
                    ),
                ),

                #
                # Fail-closed
                #
                Default(
                    target=(
                        blocked_route
                    ),
                ),
            ],
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
            procedure_validation,
        )

        .add_edge(
            procedure_validation,
            procedure_transition,
        )

        .build()
    )