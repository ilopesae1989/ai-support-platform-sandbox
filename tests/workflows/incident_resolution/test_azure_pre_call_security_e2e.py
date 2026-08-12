import pytest

import src.workflows.incident_resolution.executors.azure_pre_call as azure_pre_call_module

from src.agents.contracts import (
    ProcedureExecutionResult,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityError,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


class AzureWorkflowResolvedParameterFake(
    AzureWorkflowFakeFoundryAgents
):
    """
    Variante del fake Azure que fuerza un parámetro
    operacional REALMENTE resoluble por el workflow.

    Utilizamos:

        environment

    porque forma parte de OperationalContext y
    create_alert() ya proporciona su valor.

    El objetivo no es probar Procedure v6.
    El objetivo es conseguir que el recorrido E2E
    llegue a HITL con un ResolvedParameter real.
    """

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ) -> ProcedureExecutionResult:
        result = (
            await super().run_procedure_execution(
                message,
                agent_version=agent_version,
            )
        )

        assert result.step is not None

        result.step.required_parameters = [
            "environment",
        ]

        return result


async def run_until_hitl(
    *,
    workflow,
) -> dict:
    """
    Ejecuta el workflow hasta la solicitud HITL
    y devuelve la respuesta positiva preparada.

    No resuelve todavía la aprobación.
    """

    pending_responses = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if event.type == "request_info":
            pending_responses[
                event.request_id
            ] = True

    assert len(
        pending_responses
    ) == 1

    return pending_responses


@pytest.mark.asyncio
async def test_e2e_target_resource_tampering_blocks_foundry(
    monkeypatch,
):
    """
    FASE 14.17

    Ataque simulado:

        HITL aprueba target_resource A
                ↓
        candidato Azure intenta target_resource B
                ↓
        PreCallSecurityVerifier
                ↓
        BLOCK

    Garantía crítica:

        run_azure_operations() == 0
    """

    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_hitl(
            workflow=workflow,
        )
    )

    #
    # Hasta HITL no debe existir llamada Azure.
    #
    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 0
    )

    original_builder = (
        azure_pre_call_module
        .build_azure_operation_request
    )

    def tampered_builder(step):
        candidate = (
            original_builder(
                step
            )
        )

        #
        # Simulamos sustitución de recurso
        # DESPUÉS de HITL.
        #
        candidate.target_resource = (
            "/subscriptions/"
            "00000000-0000-0000-"
            "0000-000000000000/"
            "resourceGroups/"
            "rg-attacker"
        )

        return candidate

    monkeypatch.setattr(
        azure_pre_call_module,
        "build_azure_operation_request",
        tampered_builder,
    )

    #
    # La manipulación debe provocar una excepción
    # ANTES de AzureOperationsExecutor.
    #
    with pytest.raises(
        PreCallSecurityError,
        match="target_resource",
    ):
        async for _ in workflow.run(
            responses=pending_responses,
            stream=True,
        ):
            pass

    #
    # La propiedad que realmente queremos demostrar:
    #
    # ni siquiera se ha invocado el agente Azure.
    #
    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 0
    )

    assert (
        agents.azure_operations_prompt
        is None
    )


@pytest.mark.asyncio
async def test_e2e_resolved_parameter_value_tampering_blocks_foundry(
    monkeypatch,
):
    """
    FASE 14.18

    Ataque simulado:

        environment = production
            ↓
        HITL aprueba
            ↓
        candidato intenta:
        environment = sandbox
            ↓
        PreCallSecurityVerifier
            ↓
        BLOCK

    Garantía:

        run_azure_operations() == 0
    """

    agents = (
        AzureWorkflowResolvedParameterFake()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_hitl(
            workflow=workflow,
        )
    )

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 0
    )

    original_builder = (
        azure_pre_call_module
        .build_azure_operation_request
    )

    def tampered_builder(step):
        candidate = (
            original_builder(
                step
            )
        )

        #
        # Debe existir exactamente el parámetro
        # resuelto durante el pipeline.
        #
        assert (
            candidate.required_parameters
            == [
                "environment",
            ]
        )

        assert (
            len(
                candidate.resolved_parameters
            )
            == 1
        )

        assert (
            candidate
            .resolved_parameters[0]
            .name
            == "environment"
        )

        #
        # Modificación DESPUÉS de aprobación.
        #
        candidate.resolved_parameters[
            0
        ].value = "sandbox"

        return candidate

    monkeypatch.setattr(
        azure_pre_call_module,
        "build_azure_operation_request",
        tampered_builder,
    )

    with pytest.raises(
        PreCallSecurityError,
        match="resolved_parameters",
    ):
        async for _ in workflow.run(
            responses=pending_responses,
            stream=True,
        ):
            pass

    #
    # El agente Azure nunca debe haberse llamado.
    #
    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 0
    )

    assert (
        agents.azure_operations_prompt
        is None
    )


@pytest.mark.asyncio
async def test_e2e_resolved_parameter_source_tampering_blocks_foundry(
    monkeypatch,
):
    """
    Defensa adicional.

    Aunque name y value permanezcan intactos,
    sustituir la procedencia autoritativa también
    invalida la operación.
    """

    agents = (
        AzureWorkflowResolvedParameterFake()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    pending_responses = (
        await run_until_hitl(
            workflow=workflow,
        )
    )

    original_builder = (
        azure_pre_call_module
        .build_azure_operation_request
    )

    def tampered_builder(step):
        candidate = (
            original_builder(
                step
            )
        )

        assert (
            len(
                candidate.resolved_parameters
            )
            == 1
        )

        candidate.resolved_parameters[
            0
        ].source = (
            "untrusted.source"
        )

        return candidate

    monkeypatch.setattr(
        azure_pre_call_module,
        "build_azure_operation_request",
        tampered_builder,
    )

    with pytest.raises(
        PreCallSecurityError,
        match="resolved_parameters",
    ):
        async for _ in workflow.run(
            responses=pending_responses,
            stream=True,
        ):
            pass

    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 0
    )

    assert (
        agents.azure_operations_prompt
        is None
    )
