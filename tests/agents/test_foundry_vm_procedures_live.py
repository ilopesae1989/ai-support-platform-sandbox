import os

import pytest

from src.agents.catalog import (
    AgentKey,
)

from src.agents.contracts import (
    AlertTriageResult,
    KnowledgeResult,
    ProcedureExecutionResult,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)


RESOURCE_TYPE = (
    "Microsoft.Compute/virtualMachines"
)


CASES = [
    {
        "alert_id":
            "ALT-AZ-VM-STOPPED-001",

        "vm_name":
            "vm-sbx-stopped-01",

        "power_state":
            "PowerState/stopped",

        "description": (
            "Azure informa que la máquina virtual "
            "vm-sbx-stopped-01 se encuentra en "
            "PowerState/stopped (Stopped Allocated). "
            "La máquina virtual debería estar en "
            "ejecución y no existe mantenimiento "
            "ni parada planificada conocida."
        ),

        "classification":
            "azure_vm_stopped_allocated",

        "expected_procedure_id":
            "NTTSY-SBX-AZ-VM-001",

        "expected_procedure_name": (
            "Arranque de máquina virtual Azure "
            "en estado Stopped (Allocated)"
        ),

        "expected_version":
            "1.0",
    },

    {
        "alert_id":
            "ALT-AZ-VM-DEALLOCATED-001",

        "vm_name":
            "vm-sbx-deallocated-01",

        "power_state":
            "PowerState/deallocated",

        "description": (
            "Azure informa que la máquina virtual "
            "vm-sbx-deallocated-01 se encuentra en "
            "PowerState/deallocated (Deallocated). "
            "La máquina virtual debería estar en "
            "ejecución y no existe mantenimiento, "
            "auto-shutdown ni desasignación "
            "planificada conocida."
        ),

        "classification":
            "azure_vm_deallocated",

        "expected_procedure_id":
            "NTTSY-SBX-AZ-VM-002",

        "expected_procedure_name": (
            "Arranque de máquina virtual Azure "
            "en estado Deallocated"
        ),

        "expected_version":
            "1.0",
    },
]


def build_knowledge_prompt(
    case,
) -> str:
    return f"""
Busca en el conocimiento corporativo disponible
documentación relacionada con la siguiente incidencia:

AlertId: {case["alert_id"]}

Clasificación técnica:
technical_domain: azure
alert_classification: {case["classification"]}

Recurso:
{case["vm_name"]}

Tipo de recurso:
{RESOURCE_TYPE}

Estado observado:
{case["power_state"]}

Incidencia:
{case["description"]}

Recupera únicamente información respaldada por
la base de conocimiento corporativa.

Es especialmente importante distinguir entre:

- PowerState/stopped / Stopped (Allocated)
- PowerState/deallocated / Deallocated

No trates ambos estados como equivalentes si existen
procedimientos corporativos diferentes.

Devuelve exclusivamente la respuesta estructurada
definida por tus instrucciones.
""".strip()


def build_knowledge_block(
    result: KnowledgeResult,
) -> str:
    documents = []

    for document in result.documents:
        documents.append(
            (
                f"- {document.id or 'sin-id'} — "
                f"{document.name} "
                f"{document.version or ''}\n"
                f"  {document.relevance_summary}"
            )
        )

    return "\n".join(
        documents
    )


def build_triage_prompt(
    case,
    knowledge: KnowledgeResult,
) -> str:
    knowledge_block = (
        build_knowledge_block(
            knowledge
        )
    )

    return f"""
Analiza la siguiente alerta:

Origen: Synthetic Azure Monitor
AlertId: {case["alert_id"]}
Nombre: Azure VM unexpected power state
Severidad origen: Critical

Recurso:
{case["vm_name"]}

Tipo de recurso:
{RESOURCE_TYPE}

Estado observado:
{case["power_state"]}

Descripción:
{case["description"]}

Clasificación previa:

alert_classification:
{case["classification"]}

technical_domain:
azure

affected_resource:
{case["vm_name"]}

affected_service:
Azure Virtual Machines

Disponibilidad de contexto operacional tipado:

Parámetros disponibles:
subscription_id, resource_group, vm_name

Parámetros no disponibles:
tenant_id

Reglas sobre este contexto:

- Esta sección indica exclusivamente disponibilidad.
- No contiene los valores operacionales autorizados.
- No inventes valores para ningún parámetro.
- La resolución de los valores exactos se realiza posteriormente
    mediante las capas deterministas Python.
- Utiliza esta información únicamente para determinar si el contexto
    requerido por el procedimiento está disponible.

Conocimiento corporativo recuperado:

{knowledge_block}

Resumen del conocimiento:

{knowledge.knowledge_summary or "Sin resumen"}

Clasifica la alerta utilizando exclusivamente
los procedimientos y matrices corporativas
disponibles.

La criticidad corporativa debe determinarse
independientemente de la severidad de origen.

Los procedimientos de VM no asignan por sí mismos
criticidad corporativa.

Selecciona exclusivamente el procedimiento que
corresponda al estado observado exacto de la VM.

Devuelve únicamente la respuesta estructurada
definida por tus instrucciones.
""".strip()


def build_procedure_prompt(
    case,
    triage: AlertTriageResult,
) -> str:
    procedure = triage.procedure

    assert procedure is not None

    return f"""
mode = "prepare_step"

Prepara la ejecución del procedimiento asociado
a la siguiente alerta:

AlertId: {case["alert_id"]}

Resultado del Triage:

procedure_found: true
procedure_match: exact
execution_eligible: true

Procedimiento:

ID: {procedure.id}
Nombre: {procedure.name}
Versión: {procedure.version}

Recurso afectado:

{case["vm_name"]}

Tipo de recurso:

{RESOURCE_TYPE}

Estado observado:

{case["power_state"]}

Incidencia:

{case["description"]}

Recupera exclusivamente el procedimiento
corporativo indicado.

No sustituyas el procedure_id.
No sustituyas la versión.
No selecciones el procedimiento correspondiente
al otro estado de energía de Azure.

Devuelve únicamente el paso que corresponde
procesar.
""".strip()


@pytest.mark.asyncio
@pytest.mark.live
@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[
        "vm-stopped-allocated",
        "vm-deallocated",
    ],
)
async def test_vm_state_selects_exact_operational_procedure_live(
    case,
):
    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = FoundryAgents()

    #
    # ==================================================
    # GATE DE VERSIONES
    # ==================================================
    #

    knowledge_definition = (
        agents.get_definition(
            AgentKey.KNOWLEDGE
        )
    )

    triage_definition = (
        agents.get_definition(
            AgentKey.ALERT_TRIAGE
        )
    )

    procedure_definition = (
        agents.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        )
    )

    assert (
        knowledge_definition.name
        == "agent-knowledge-sbx"
    )

    assert (
        knowledge_definition.version
        == "8"
    )

    assert (
        triage_definition.name
        == "agent-alert-triage-sbx"
    )

    assert (
        triage_definition.version
        == "10"
    )

    assert (
        procedure_definition.name
        == "agent-procedure-execution-sbx"
    )

    assert (
        procedure_definition.version
        == "6"
    )

    #
    # ==================================================
    # 1. KNOWLEDGE LIVE
    # ==================================================
    #

    knowledge = (
        await agents.run_knowledge(
            build_knowledge_prompt(
                case
            )
        )
    )

    assert isinstance(
        knowledge,
        KnowledgeResult,
    )

    assert (
        knowledge.alert_id
        == case["alert_id"]
    )

    assert (
        knowledge.knowledge_found
        is True
    )

    assert knowledge.documents

    document_ids = {
        document.id
        for document
        in knowledge.documents
        if document.id is not None
    }

    print()
    print(
        f"[KNOWLEDGE] {case['power_state']}"
    )
    print(
        "Document IDs:",
        document_ids,
    )

    #
    # El documento esperado debe estar disponible.
    #
    # NO exigimos que el otro procedimiento no aparezca:
    # ambos documentos son semánticamente similares y
    # Search puede recuperarlos como candidatos.
    #
    # La selección exacta corresponde a Triage.
    #
    assert (
        case[
            "expected_procedure_id"
        ]
        in document_ids
    )

    assert (
        knowledge.knowledge_summary
        is not None
    )

    assert (
        0.0
        < knowledge.confidence
        <= 1.0
    )

    #
    # ==================================================
    # 2. TRIAGE LIVE
    # ==================================================
    #

    triage = (
        await agents.run_alert_triage(
            build_triage_prompt(
                case,
                knowledge,
            )
        )
    )

    assert isinstance(
        triage,
        AlertTriageResult,
    )

    print()
    print(
        f"[TRIAGE] {case['power_state']}"
    )

    print(
        "procedure_id:",
        (
            triage.procedure.id
            if triage.procedure
            else None
        ),
    )

    print(
        "procedure_version:",
        (
            triage.procedure.version
            if triage.procedure
            else None
        ),
    )

    print(
        "corporate_criticality:",
        triage.corporate_criticality,
    )

    print(
        "criticality_source:",
        triage.criticality_source,
    )

    assert (
        triage.alert_classification
        == case["classification"]
    )

    assert (
        triage.technical_domain
        == "azure"
    )

    assert (
        triage.affected_resource
        == case["vm_name"]
    )

    #
    # Criticidad separada del procedimiento.
    #
    assert (
        triage.corporate_criticality
        in {
            "critical",
            "high",
            "medium",
            "low",
            "informational",
            "unknown",
        }
    )

    assert (
        triage.criticality_source
        in {
            "procedure",
            "escalation_matrix",
            "corporate_matrix",
            "unknown",
        }
    )

    #
    # Nuestros procedimientos VM no asignan
    # criticidad.
    #
    assert (
        triage.criticality_source
        != "procedure"
    )

    #
    # Selección exacta.
    #
    assert (
        triage.procedure_found
        is True
    )

    assert (
        triage.procedure_match
        == "exact"
    )

    assert (
        triage.procedure
        is not None
    )

    assert (
        triage.procedure.id
        == case[
            "expected_procedure_id"
        ]
    )

    assert (
        triage.procedure.name
        == case[
            "expected_procedure_name"
        ]
    )

    assert (
        triage.procedure.version
        == case[
            "expected_version"
        ]
    )

    print(
        "execution_eligible:",
        triage.execution_eligible,
    )

    print(
        "knowledge_coverage:",
        triage.knowledge_coverage,
    )

    print(
        "recommended_next_step:",
        triage.recommended_next_step,
    )

    print(
        "missing_context:",
        triage.missing_context,
    )

    print(
        "escalation:",
        triage.escalation.model_dump(
            mode="python"
        ),
    )

    assert (
        triage.execution_eligible
        is True
    )

    assert (
        triage.knowledge_coverage
        == "complete"
    )

    assert (
        triage.recommended_next_step
        == "procedure_execution"
    )

    assert (
        triage.missing_context
        == []
    )

    #
    # ==================================================
    # 3. PROCEDURE EXECUTION LIVE
    # ==================================================
    #

    procedure_result = (
        await agents.run_procedure_execution(
            build_procedure_prompt(
                case,
                triage,
            )
        )
    )

    assert isinstance(
        procedure_result,
        ProcedureExecutionResult,
    )

    print()
    print(
        f"[PROCEDURE] {case['power_state']}"
    )

    print(
        "procedure:",
        procedure_result.procedure.id,
        procedure_result.procedure.version,
    )

    print(
        "step:",
        (
            procedure_result.step.id
            if procedure_result.step
            else None
        ),
    )

    print(
        "target_resource:",
        (
            procedure_result
            .step
            .target_resource
            if procedure_result.step
            else None
        ),
    )

    print(
        "required_parameters:",
        (
            procedure_result
            .step
            .required_parameters
            if procedure_result.step
            else None
        ),
    )

    #
    # El Procedure Agent no puede cambiar la
    # identidad seleccionada por Triage.
    #
    assert (
        procedure_result.alert_id
        == case["alert_id"]
    )

    assert (
        procedure_result.procedure.id
        == case[
            "expected_procedure_id"
        ]
    )

    assert (
        procedure_result.procedure.name
        == case[
            "expected_procedure_name"
        ]
    )

    assert (
        procedure_result.procedure.version
        == case[
            "expected_version"
        ]
    )

    assert (
        procedure_result.execution_allowed
        is True
    )

    assert (
        procedure_result.blocked_by_policy
        is False
    )

    assert (
        procedure_result.total_steps
        >= 1
    )

    assert (
        procedure_result.current_step
        == 1
    )

    assert (
        procedure_result.step
        is not None
    )

    assert (
        procedure_result.step.id
        == "1"
    )

    assert (
        procedure_result.step.operation_domain
        == "azure"
    )

    assert (
        procedure_result.step.operation_kind
        == "write"
    )

    #
    # CRÍTICO:
    #
    # Procedure únicamente describe parámetros
    # cognitivos.
    #
    # capability_id / operation_action serán
    # añadidos después por Python.
    #
    assert (
        procedure_result
        .step
        .required_parameters
        == [
            "subscription_id",
            "resource_group",
            "vm_name",
        ]
    )

    assert (
        procedure_result
        .step
        .target_resource
        == case["vm_name"]
    )

    assert (
        procedure_result.next_action
        == "execute_step"
    )

    assert (
        procedure_result.requires_clarification
        is False
    )

    assert (
        procedure_result.missing_information
        == []
    )

    assert (
        procedure_result.source_documents
    )

    assert any(
        (
            case[
                "expected_procedure_id"
            ]
            in document
        )
        for document
        in procedure_result.source_documents
    )

    assert (
        0.0
        <= procedure_result.confidence
        <= 1.0
    )