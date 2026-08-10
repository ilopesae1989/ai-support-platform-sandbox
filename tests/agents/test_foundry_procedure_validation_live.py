import os

import pytest

from src.agents.catalog import (
    AgentKey,
)

from src.agents.contracts import (
    ProcedureValidationResult,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.runtime.procedure.models import (
    NextAction,
)

from src.workflows.incident_resolution.executors.procedure_validation import (
    ProcedureValidationExecutor,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.procedure_validation_models import (
    ProcedureValidationRequest,
    ProcedureValidationStep,
)


PROCEDURE_ID = "NTTSY-PRO-016"

PROCEDURE_NAME = (
    "SQL AlwaysOn_Rol Change Alerta"
)

PROCEDURE_VERSION = "v1.1"

ALERT_ID = "ALT-SQL-AG-001"

TARGET_RESOURCE = "SQLPROD01"

OPERATION_ID = (
    "op-live-procedure-validation-001"
)

WORKFLOW_ID = (
    "wf-live-procedure-validation-001"
)

APPROVAL_ID = (
    "apr-live-procedure-validation-001"
)

CORRELATION_ID = (
    "corr-live-procedure-validation-001"
)

CONVERSATION_ID = (
    "conv-live-procedure-validation-001"
)


@pytest.mark.asyncio
@pytest.mark.live
async def test_foundry_procedure_validation_v6_live():
    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = FoundryAgents()

    #
    # El catálogo debe seleccionar exactamente v6.
    #
    definition = agents.get_definition(
        AgentKey.PROCEDURE_EXECUTION
    )

    assert (
        definition.name
        == "agent-procedure-execution-sbx"
    )

    assert definition.version == "6"

    #
    # 1. Recuperamos un procedimiento corporativo
    # real cuya recuperación Foundry IQ ya está
    # validada LIVE.
    #
    prepare_prompt = f"""
mode = "prepare_step"

Prepara la ejecución del procedimiento asociado
a la siguiente alerta:

AlertId: {ALERT_ID}

Resultado del Triage:
procedure_found: true
procedure_match: exact
execution_eligible: true

Procedimiento:
ID: {PROCEDURE_ID}
Nombre: {PROCEDURE_NAME}
Versión: {PROCEDURE_VERSION}

Recurso afectado:
{TARGET_RESOURCE}

Incidencia:
La réplica secundaria del Availability Group AG-PROD
ha dejado de sincronizarse con la réplica primaria
durante más de 10 minutos.

Recupera el procedimiento corporativo indicado y
devuelve únicamente el primer paso que debe procesarse.
""".strip()

    prepared = (
        await agents.run_procedure_execution(
            prepare_prompt
        )
    )

    #
    # Foundry IQ debe haber recuperado
    # exactamente el procedimiento real.
    #
    assert prepared.procedure.id == PROCEDURE_ID

    assert (
        prepared.procedure.name
        == PROCEDURE_NAME
    )

    assert (
        prepared.procedure.version
        == PROCEDURE_VERSION
    )

    assert prepared.current_step == 1

    assert prepared.step is not None

    assert prepared.step.id == "1"

    assert (
        prepared.step.operation_domain
        == "database"
    )

    assert (
        prepared.step.operation_kind
        == "read"
    )

    assert (
        prepared.step.target_resource
        == TARGET_RESOURCE
    )

    assert (
        prepared.next_action
        == "execute_step"
    )

    assert prepared.source_documents

    assert any(
        PROCEDURE_ID in document
        for document in prepared.source_documents
    )

    #
    # 2. Construimos un resultado operacional
    # identificado correctamente.
    #
    # La llamada Python terminó correctamente,
    # pero NO existe evidencia técnica que permita
    # demostrar el expected_result.
    #
    operation_result = OperationResult(
        operation_id=OPERATION_ID,

        workflow_id=WORKFLOW_ID,

        approval_id=APPROVAL_ID,

        alert_id=ALERT_ID,

        correlation_id=CORRELATION_ID,

        conversation_id=CONVERSATION_ID,

        procedure_id=(
            prepared.procedure.id
        ),

        procedure_version=(
            prepared.procedure.version
        ),

        current_step=(
            prepared.current_step
        ),

        step_id=(
            prepared.step.id
        ),

        operation_domain=(
            prepared.step.operation_domain
        ),

        operation_kind=(
            prepared.step.operation_kind
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource=(
            prepared.step.target_resource
        ),

        required_parameters=(
            prepared.step.required_parameters
        ),

        resolved_parameters=[],

        success=True,

        technical_success=None,

        response_text=(
            "La llamada de backend finalizó, "
            "pero no existe evidencia técnica "
            "verificable que permita demostrar "
            "el resultado esperado del paso."
        ),

        error=None,

        evidence=None,
    )

    #
    # Este estado es válido por contrato:
    # success=True indica que el backend fue
    # invocado sin excepción.
    #
    # technical_success=None expresa que
    # técnicamente el resultado es indeterminado.
    #
    assert operation_result.success is True

    assert (
        operation_result.technical_success
        is None
    )

    assert operation_result.evidence is None

    #
    # 3. Snapshot cognitivo exacto que recibe
    # Procedure Validation.
    #
    request = ProcedureValidationRequest(
        operation_result=(
            operation_result
        ),

        step=ProcedureValidationStep(
            procedure_id=(
                prepared.procedure.id
            ),

            procedure_version=(
                prepared.procedure.version
            ),

            current_step=(
                prepared.current_step
            ),

            step_id=(
                prepared.step.id
            ),

            description=(
                prepared.step.description
            ),

            expected_result=(
                prepared.step.expected_result
            ),

            verification=(
                prepared.step.verification
            ),
        ),
    )

    #
    # Usamos exactamente el prompt builder
    # de producción.
    #
    prompt = (
        ProcedureValidationExecutor
        ._build_prompt(
            request
        )
    )

    assert (
        '"mode": "validate_result"'
        in prompt
    )

    assert OPERATION_ID in prompt

    #
    # 4. Llamada REAL a Procedure Agent v6.
    #
    result = (
        await agents
        .run_procedure_validation(
            prompt
        )
    )

    assert isinstance(
        result,
        ProcedureValidationResult,
    )

    #
    # La identidad debe sobrevivir exactamente.
    #
    assert (
        result.operation_id
        == OPERATION_ID
    )

    #
    # PRINCIPAL INVARIANTE DE SEGURIDAD:
    #
    # success=True sin evidencia suficiente
    # NO puede convertirse en satisfied.
    #
    assert (
        result.validation_status
        == "indeterminate"
    )

    #
    # validate_result nunca puede preparar
    # directamente otra operación.
    #
    assert (
        result.proposed_next_action
        != "execute_step"
    )

    assert (
        result.proposed_next_action
        in {
            "continue",
            "repeat",
            "wait",
            "resolved",
            "escalate",
            "blocked",
        }
    )

    assert result.validation_summary
