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

        partial
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
            │ AzureOperationsExecutor
            │     ↓
            │ agent-azure-operations-sbx v11
            │     ↓
            │ futuro MCP verification
            │
            ├─ database
            ├─ itsm
            ├─ windows
            ├─ linux
            ├─ networking
            ├─ microsoft365
            └─ Default → blocked

    Ningún LLM decide:

    - el routing;
    - la aprobación;
    - el resource scope autorizado;
    - los parámetros autorizados;
    - la verificación pre-call.
    """

    foundry_agents = (
        agents
        or FoundryAgents()
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
        ProcedureRuntimeExecutor()
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
                # IMPORTANTE:
                #
                # La ruta Azure ya NO entra
                # directamente en Azure Operations.
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
        # Pre-call verificado
        #     ↓
        # lifecycle determinista
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
        # registro autoritativo
        #     ↓
        # Procedure Validation v6
        #     ↓
        # Transition Gate determinista
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