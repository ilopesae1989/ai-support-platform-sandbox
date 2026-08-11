import json
import os

import pytest

from src.agents.catalog import (
    AgentKey,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.runtime.procedure.models import (
    ProcedureRuntimeState,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow import (
    ApprovalRequest,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_live_probe import (
    create_live_azure_alert,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

EXPECTED_RESOURCE_GROUPS = {
    "rg-icenter-sandbox-foundry",
    "rg-icenter-sandbox-application",
    "rg-icenter-sandbox-data",
    "rg-icenter-sandbox-integration",
    "rg-icenter-sandbox-operations",
}


def serialize_value(
    value,
):
    """
    Conversión defensiva utilizada exclusivamente
    para inspeccionar la respuesta nativa LIVE.

    No modifica la respuesta.
    No interpreta el resultado.
    No forma parte del runtime productivo.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            serialize_value(item)
            for item in value
        ]

    model_dump = getattr(
        value,
        "model_dump",
        None,
    )

    if callable(model_dump):
        try:
            return serialize_value(
                model_dump(
                    mode="python"
                )
            )
        except Exception:
            pass

    as_dict = getattr(
        value,
        "as_dict",
        None,
    )

    if callable(as_dict):
        try:
            return serialize_value(
                as_dict()
            )
        except Exception:
            pass

    data = getattr(
        value,
        "__dict__",
        None,
    )

    if isinstance(
        data,
        dict,
    ):
        return {
            str(key): serialize_value(item)
            for key, item in data.items()
            if not str(key).startswith("_")
        }

    return repr(value)


def find_mcp_calls(
    value,
) -> list[dict]:
    """
    Localiza únicamente objetos cuyo type sea:

        mcp_call

    No acepta como evidencia la mera aparición de
    group_list dentro de mcp_list_tools.
    """

    calls = []

    if isinstance(
        value,
        dict,
    ):
        if value.get("type") == "mcp_call":
            calls.append(value)

        for child in value.values():
            calls.extend(
                find_mcp_calls(child)
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            calls.extend(
                find_mcp_calls(child)
            )

    return calls


def extract_group_names_from_mcp_output(
    mcp_call: dict,
) -> set[str]:
    """
    Extrae los nombres de RG exclusivamente del
    output real devuelto por la tool MCP.
    """

    output = mcp_call.get(
        "output"
    )

    assert isinstance(
        output,
        str,
    )

    payload = json.loads(
        output
    )

    assert payload["status"] == 200

    groups = (
        payload[
            "results"
        ][
            "groups"
        ]
    )

    return {
        group["name"]
        for group in groups
    }


class LiveE2ERecordingFoundryAgents(
    FoundryAgents
):
    """
    Ejecuta los agentes REALES de Foundry.

    Sólo añade observabilidad de test.

    No:
    - sustituye respuestas;
    - fuerza routing;
    - altera prompts;
    - inventa Procedure;
    - modifica parámetros;
    - sustituye MCP.
    """

    def __init__(self) -> None:
        super().__init__()

        self.calls: list[str] = []

        self.classification_result = None
        self.knowledge_result = None
        self.triage_result = None
        self.procedure_result = None

        self.azure_native_response = None
        self.azure_operations_prompt = None

        self.procedure_validation_prompt = None
        self.procedure_validation_result = None

    async def run_classification(
        self,
        message: str,
    ):
        self.calls.append(
            "classification"
        )

        result = await super().run_classification(
            message
        )

        self.classification_result = (
            result
        )

        return result

    async def run_knowledge(
        self,
        message: str,
    ):
        self.calls.append(
            "knowledge"
        )

        result = await super().run_knowledge(
            message
        )

        self.knowledge_result = result

        return result

    async def run_alert_triage(
        self,
        message: str,
    ):
        self.calls.append(
            "alert_triage"
        )

        result = await super().run_alert_triage(
            message
        )

        self.triage_result = result

        return result

    async def run_procedure_execution(
        self,
        message: str,
    ):
        self.calls.append(
            "procedure_execution"
        )

        result = (
            await super().run_procedure_execution(
                message
            )
        )

        self.procedure_result = result

        return result

    async def run_azure_operations(
        self,
        message: str,
    ):
        """
        Esta vez SÍ permitimos la llamada LIVE.

        Es una operación de lectura sobre la
        suscripción sandbox previamente aprobada.
        """

        self.calls.append(
            "azure_operations"
        )

        self.azure_operations_prompt = (
            message
        )

        response = (
            await super().run_azure_operations(
                message
            )
        )

        self.azure_native_response = (
            response
        )

        return response

    async def run_procedure_validation(
        self,
        message: str,
    ):
        """
        Ejecuta Procedure Validation REAL v6.

        Sólo añade observabilidad de test.
        No sustituye ni modifica la respuesta.
        """

        self.calls.append(
            "procedure_validation"
        )

        self.procedure_validation_prompt = (
            message
        )

        result = (
            await super()
            .run_procedure_validation(
                message
            )
        )

        self.procedure_validation_result = (
            result
        )

        return result


@pytest.mark.asyncio
@pytest.mark.live
async def test_incident_workflow_live_hitl_to_real_azure_mcp():
    """
    FASE 16.12.8

    E2E LIVE:

        NormalizedAlert
            ↓
        Classification v7 REAL
            ↓
        Knowledge v8 REAL
            ↓
        Foundry IQ REAL
            ↓
        Triage v10 REAL
            ↓
        Procedure v6 REAL
            ↓
        ProcedureRuntime
            ↓
        HITL
            ↓
        approved=True
            ↓
        ApprovedProcedureStep
            ↓
        routing Python
            ↓
        AzurePreCallSecurityExecutor
            ↓
        PreCallSecurityVerifier
            ↓
        VerifiedAzureOperationRequest
            ↓
        Azure Operations v11 REAL
            ↓
        Azure MCP REAL
            ↓
        group_list
            ↓
        5 Resource Groups reales
            ↓
        OperationResultRegistration
            ↓
        Procedure Validation v6 REAL
            ↓
        Transition Gate Python
            ↓
        ProcedureRuntimeState

    La aprobación HITL se responde mediante el
    harness del test.

    Esto prueba el mecanismo HITL real del workflow,
    aunque todavía no representa una aprobación
    humana realizada desde Teams.
    """

    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = (
        LiveE2ERecordingFoundryAgents()
    )

    #
    # --------------------------------------------------
    # Baseline de agentes
    # --------------------------------------------------
    #

    assert (
        agents.get_definition(
            AgentKey.CLASSIFICATION
        ).version
        == "7"
    )

    assert (
        agents.get_definition(
            AgentKey.KNOWLEDGE
        ).version
        == "8"
    )

    assert (
        agents.get_definition(
            AgentKey.ALERT_TRIAGE
        ).version
        == "10"
    )

    assert (
        agents.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        ).version
        == "6"
    )

    assert (
        agents.get_definition(
            AgentKey.AZURE_OPERATIONS
        ).version
        == "11"
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    #
    # --------------------------------------------------
    # Primera ejecución:
    #
    # NormalizedAlert → HITL
    # --------------------------------------------------
    #

    pending_responses = {}

    approval_requests = []

    async for event in workflow.run(
        create_live_azure_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            approval_requests.append(
                event.data
            )

            pending_responses[
                event.request_id
            ] = True

    #
    # --------------------------------------------------
    # Debe haberse alcanzado HITL.
    # --------------------------------------------------
    #

    assert len(
        pending_responses
    ) == 1

    assert len(
        approval_requests
    ) == 1

    approval = (
        approval_requests[0]
    )

    assert isinstance(
        approval,
        ApprovalRequest,
    )

    #
    # --------------------------------------------------
    # Comprobaciones cognitivas LIVE
    # --------------------------------------------------
    #

    assert (
        agents.classification_result
        is not None
    )

    assert (
        agents.knowledge_result
        is not None
    )

    assert (
        agents.triage_result
        is not None
    )

    assert (
        agents.procedure_result
        is not None
    )

    assert (
        agents.triage_result.procedure_found
        is True
    )

    assert (
        agents.triage_result.procedure_match
        == "exact"
    )

    assert (
        agents.triage_result.execution_eligible
        is True
    )

    #
    # --------------------------------------------------
    # Procedure exacto
    # --------------------------------------------------
    #

    assert (
        agents.procedure_result.procedure.id
        == "NTTSY-SBX-AZ-001"
    )

    assert (
        agents.procedure_result.procedure.version
        == "1.0"
    )

    assert (
        agents.procedure_result.step.operation_domain
        == "azure"
    )

    assert (
        agents.procedure_result.step.operation_kind
        == "read"
    )

    assert (
        agents.procedure_result.next_action
        == "execute_step"
    )

    assert (
        agents.procedure_result.step.target_resource
        == SUBSCRIPTION_ID
    )

    assert (
        agents.procedure_result.step.required_parameters
        == [
            "subscription_id",
        ]
    )

    #
    # --------------------------------------------------
    # Snapshot HITL exacto
    # --------------------------------------------------
    #

    assert (
        approval.alert_id
        == "ALT-AZ-RG-LIST-001"
    )

    assert (
        approval.correlation_id
        == "corr-azure-rg-list-live-001"
    )

    assert (
        approval.procedure_id
        == "NTTSY-SBX-AZ-001"
    )

    assert (
        approval.procedure_version
        == "1.0"
    )

    assert (
        approval.operation_domain
        == "azure"
    )

    assert (
        approval.operation_kind
        == "read"
    )

    assert (
        approval.next_action
        == "execute_step"
    )

    assert (
        approval.target_resource
        == SUBSCRIPTION_ID
    )

    assert (
        approval.required_parameters
        == [
            "subscription_id",
        ]
    )

    assert (
        len(
            approval.resolved_parameters
        )
        == 1
    )

    resolved = (
        approval.resolved_parameters[0]
    )

    assert (
        resolved.name
        == "subscription_id"
    )

    assert (
        resolved.value
        == SUBSCRIPTION_ID
    )

    #
    # Antes de aprobar:
    #
    # Azure Operations = 0
    # MCP = 0
    #
    assert (
        "azure_operations"
        not in agents.calls
    )

    assert (
        agents.azure_native_response
        is None
    )

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    #
    # --------------------------------------------------
    # Segunda ejecución:
    #
    # Respuesta HITL
    #     → Azure
    #     → MCP
    #     → Registration
    #     → Procedure Validation
    #     → Transition Gate
    # --------------------------------------------------
    #

    output_events = []

    async for event in workflow.run(
        responses=pending_responses,
        stream=True,
    ):
        if event.type == "output":
            output_events.append(
                event.data
            )

    #
    # --------------------------------------------------
    # No deben reinvocarse agentes cognitivos.
    # --------------------------------------------------
    #

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
        "procedure_validation",
    ]

    assert (
        agents.calls.count(
            "classification"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "knowledge"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "alert_triage"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_execution"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    #
    # --------------------------------------------------
    # Resultado terminal del workflow FASE 16
    # --------------------------------------------------
    #

    assert len(
        output_events
    ) == 1

    runtime_state = (
        output_events[0]
    )

    assert isinstance(
        runtime_state,
        ProcedureRuntimeState,
    )

    assert (
        runtime_state.step_status
        == StepStatus.SUCCEEDED
    )

    assert (
        runtime_state.workflow_status
        in {
            WorkflowStatus.RUNNING,
            WorkflowStatus.RESOLVED,
        }
    )

    assert (
        runtime_state.approval_id
        == approval.approval_id
    )

    assert (
        runtime_state.operation_result
        is not None
    )

    assert (
        runtime_state.verification_result
        is not None
    )

    #
    # Recuperamos el OperationResult registrado
    # autoritativamente por el workflow.
    #
    operation_result = (
        OperationResult.model_validate(
            runtime_state
            .operation_result
            .result
        )
    )

    assert (
        operation_result.success
        is True
    )

    #
    # El MCP real debe haber producido evidencia
    # técnica suficiente para demostrar éxito.
    #
    assert (
        operation_result.technical_success
        is True
    )

    assert (
        operation_result.evidence
        is not None
    )

    assert (
        operation_result.alert_id
        == "ALT-AZ-RG-LIST-001"
    )

    assert (
        operation_result.correlation_id
        == "corr-azure-rg-list-live-001"
    )

    assert (
        operation_result.procedure_id
        == "NTTSY-SBX-AZ-001"
    )

    assert (
        operation_result.procedure_version
        == "1.0"
    )

    assert (
        operation_result.operation_kind.value
        == "read"
    )

    assert (
        operation_result.target_resource
        == SUBSCRIPTION_ID
    )

    assert (
        operation_result.approval_id
        == approval.approval_id
    )

    assert (
        len(
            operation_result
            .resolved_parameters
        )
        == 1
    )

    assert (
        operation_result
        .resolved_parameters[0]
        .name
        == "subscription_id"
    )

    assert (
        operation_result
        .resolved_parameters[0]
        .value
        == SUBSCRIPTION_ID
    )

    #
    # Evidencia operacional normalizada por
    # AzureOperationsExecutor.
    #
    assert (
        len(
            operation_result
            .evidence
            .mcp_calls
        )
        == 1
    )

    assert (
        operation_result
        .evidence
        .mcp_calls[0]
        .tool_name
        == "group_list"
    )

    assert (
        len(
            operation_result
            .evidence
            .mcp_results
        )
        == 1
    )

    #
    # --------------------------------------------------
    # Procedure Validation v6 REAL
    # --------------------------------------------------
    #

    assert (
        agents.procedure_validation_prompt
        is not None
    )

    assert (
        agents.procedure_validation_result
        is not None
    )

    validation_result = (
        agents.procedure_validation_result
    )

    assert (
        validation_result.operation_id
        == operation_result.operation_id
    )

    #
    # Con una llamada MCP group_list completada
    # correctamente y evidencia técnica real,
    # el criterio del paso debe quedar satisfecho.
    #
    assert (
        validation_result.validation_status
        == "satisfied"
    )

    assert (
        validation_result.proposed_next_action
        in {
            "continue",
            "resolved",
        }
    )

    assert (
        runtime_state
        .verification_result
        .success
        is True
    )

    #
    # --------------------------------------------------
    # Prompt hacia Azure Operations
    # --------------------------------------------------
    #

    assert (
        agents.azure_operations_prompt
        is not None
    )

    assert (
        SUBSCRIPTION_ID
        in agents.azure_operations_prompt
    )

    assert (
        "subscription_id"
        in agents.azure_operations_prompt
    )

    assert (
        "NTTSY-SBX-AZ-001"
        in agents.azure_operations_prompt
    )

    #
    # --------------------------------------------------
    # Evidencia MCP NATIVA
    # --------------------------------------------------
    #

    assert (
        agents.azure_native_response
        is not None
    )

    serialized_response = (
        serialize_value(
            agents.azure_native_response
        )
    )

    mcp_calls = (
        find_mcp_calls(
            serialized_response
        )
    )

    #
    # Este procedimiento sólo requiere una
    # operación MCP.
    #
    assert len(
        mcp_calls
    ) == 1

    mcp_call = (
        mcp_calls[0]
    )

    #
    # --------------------------------------------------
    # Tool MCP exacta
    # --------------------------------------------------
    #

    assert (
        mcp_call["name"]
        == "group_list"
    )

    assert (
        mcp_call["server_label"]
        == "azure-mcp-operations-sbx"
    )

    assert (
        mcp_call["status"]
        == "completed"
    )

    assert (
        mcp_call.get(
            "error"
        )
        is None
    )

    #
    # group_list actualmente está configurado
    # server-side sin segunda aprobación MCP.
    #
    assert (
        mcp_call.get(
            "approval_request_id"
        )
        is None
    )

    #
    # --------------------------------------------------
    # Argumentos MCP exactos
    # --------------------------------------------------
    #

    arguments = json.loads(
        mcp_call[
            "arguments"
        ]
    )

    assert arguments == {
        "subscription":
            SUBSCRIPTION_ID,
    }

    #
    # --------------------------------------------------
    # Ground truth
    # --------------------------------------------------
    #

    actual_resource_groups = (
        extract_group_names_from_mcp_output(
            mcp_call
        )
    )

    assert (
        actual_resource_groups
        == EXPECTED_RESOURCE_GROUPS
    )

    #
    # También exigimos exactamente 5.
    #
    assert len(
        actual_resource_groups
    ) == 5

    #
    # --------------------------------------------------
    # Diagnóstico visible
    # --------------------------------------------------
    #

    print()
    print("=" * 80)
    print(
        "FASE 16.12.8 — LIVE E2E PASSED"
    )
    print("=" * 80)

    print(
        "Procedure:"
        " NTTSY-SBX-AZ-001 1.0"
    )

    print(
        "HITL approval_id:",
        approval.approval_id,
    )

    print(
        "workflow_id:",
        approval.workflow_id,
    )

    print(
        "correlation_id:",
        approval.correlation_id,
    )

    print(
        "MCP server:",
        mcp_call[
            "server_label"
        ],
    )

    print(
        "MCP tool:",
        mcp_call[
            "name"
        ],
    )

    print(
        "MCP arguments:",
        arguments,
    )

    print(
        "MCP status:",
        mcp_call[
            "status"
        ],
    )

    print(
        "Resource Groups:",
        sorted(
            actual_resource_groups
        ),
    )

    print("=" * 80)