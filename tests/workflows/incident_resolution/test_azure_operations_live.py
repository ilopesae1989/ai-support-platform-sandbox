import os

import pytest

from src.agents.catalog import (
    AgentKey,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)
from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-a9ae-e9e89b5ad172"
)


@pytest.mark.asyncio
@pytest.mark.live
async def test_azure_operations_live_read_resource_groups():
    """
    FASE 13.11

    Prueba LIVE aislada:

        FoundryAgents
            ↓
        agent-azure-operations-sbx v11
            ↓
        Azure MCP
            ↓
        Azure

    Operación deliberadamente READ.

    No modifica recursos.

    Objetivo:
    obtener los Resource Groups visibles en la
    suscripción sandbox actual.
    """

    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = FoundryAgents()

    #
    # --------------------------------------------------
    # Gate de catálogo
    # --------------------------------------------------
    #

    definition = agents.get_definition(
        AgentKey.AZURE_OPERATIONS
    )

    assert (
        definition.name
        == "agent-azure-operations-sbx"
    )

    assert definition.version == "11"

    #
    # --------------------------------------------------
    # Prompt LIVE
    # --------------------------------------------------
    #
    # Importante:
    #
    # - READ únicamente;
    # - suscripción explícita;
    # - no cambiar configuración;
    # - no realizar operaciones alternativas.
    #

    prompt = f"""
Realiza exclusivamente una operación de lectura
contra Azure.

Suscripción autorizada:
{SUBSCRIPTION_ID}

Operación solicitada:
Lista los Resource Groups existentes en esta
suscripción.

Restricciones obligatorias:

- La operación es exclusivamente READ.
- No crees recursos.
- No actualices recursos.
- No elimines recursos.
- No inicies ni detengas recursos.
- No modifiques RBAC.
- No cambies de suscripción.
- Utiliza únicamente Azure MCP.
- Si no puedes realizar exactamente esta consulta,
  no ejecutes ninguna operación alternativa.

Devuelve el resultado obtenido de Azure.
""".strip()

    #
    # --------------------------------------------------
    # Invocación LIVE
    # --------------------------------------------------
    #

    response = await agents.run_azure_operations(
        prompt
    )

    #
    # --------------------------------------------------
    # Diagnóstico de la respuesta nativa
    # --------------------------------------------------
    #
    # Durante FASE 13 todavía NO asumimos de antemano
    # cómo expone Agent Framework todos los detalles
    # MCP.
    #
    # Por eso mostramos únicamente metadatos seguros
    # de la respuesta.
    #

    print()
    print("=" * 80)
    print("AZURE OPERATIONS LIVE RESPONSE")
    print("=" * 80)

    print(
        "response_type =",
        type(response).__name__,
    )

    text = getattr(
        response,
        "text",
        None,
    )

    print(
        "text =",
        text,
    )

    messages = getattr(
        response,
        "messages",
        None,
    )

    print(
        "messages_type =",
        (
            type(messages).__name__
            if messages is not None
            else None
        ),
    )

    user_input_requests = getattr(
        response,
        "user_input_requests",
        None,
    )

    print(
        "user_input_requests =",
        user_input_requests,
    )

    #
    # No afirmamos todavía que el MCP haya terminado
    # correctamente sólo porque agent.run() devolvió.
    #
    # El objetivo de 13.11 es observar el comportamiento
    # LIVE real de v11.
    #

    #
    # --------------------------------------------------
    # Evidencia MCP estructurada
    # --------------------------------------------------
    #
    # Esta prueba valida también el contrato:
    #
    #     1 invocation
    #         ↓
    #     máximo 1 MCP tool call
    #
    # La extracción utiliza exactamente la misma
    # lógica de producción que AzureOperationsExecutor.
    #

    mcp_calls = (
        AzureOperationsExecutor
        ._extract_mcp_calls(
            response
        )
    )

    mcp_results = (
        AzureOperationsExecutor
        ._extract_mcp_results(
            response
        )
    )

    print()
    print(
        "mcp_call_count =",
        len(mcp_calls),
    )

    print(
        "mcp_result_count =",
        len(mcp_results),
    )

    for index, call in enumerate(
        mcp_calls,
        start=1,
    ):
        print(
            f"mcp_call[{index}] =",
            call,
        )

    for index, result in enumerate(
        mcp_results,
        start=1,
    ):
        print(
            f"mcp_result[{index}] =",
            result,
        )

    assert len(
        mcp_calls
    ) == 1

    mcp_call = (
        mcp_calls[0]
    )

    assert (
        mcp_call.tool_name
        == "group_list"
    )

    assert dict(
        mcp_call.arguments
    ) == {
        "subscription":
            SUBSCRIPTION_ID,
    }

    assert len(
        mcp_results
    ) == 1

    assert (
        mcp_results[0].mcp_call_id
        == mcp_call.mcp_call_id
    )

    assert response is not None