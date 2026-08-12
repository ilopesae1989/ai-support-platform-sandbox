import os

import pytest

from src.agents.catalog import (
    AgentKey,
)

from src.agents.foundry_agents import (
    FoundryAgents,
)

from src.workflows.incident_resolution.executors.procedure import (
    ProcedureExecutionExecutor,
)

from src.workflows.incident_resolution.models import (
    ProcedureExecutionRequest,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

PROCEDURE_ID = (
    "NTTSY-SBX-AZ-001"
)

PROCEDURE_NAME = (
    "Consulta de Resource Groups "
    "de una suscripción Azure"
)


def create_procedure_request(
) -> ProcedureExecutionRequest:
    """
    Request exacto del caso LIVE Azure RG List.

    Este test no ejecuta:

    - Classification;
    - Knowledge;
    - Triage;
    - Runtime;
    - HITL;
    - Azure Operations;
    - MCP.

    Prueba exclusivamente la estabilidad del contrato
    de salida de Procedure v6 para target_resource.
    """

    return ProcedureExecutionRequest(
        alert_id=(
            "ALT-AZ-RG-LIST-001"
        ),

        procedure_found=True,

        procedure_match="exact",

        execution_eligible=True,

        procedure_id=(
            PROCEDURE_ID
        ),

        procedure_name=(
            PROCEDURE_NAME
        ),

        procedure_version="1.0",

        affected_resource=(
            SUBSCRIPTION_ID
        ),

        incident_description=(
            "Se requiere obtener el listado de "
            "Resource Groups existentes en la "
            "suscripción Azure "
            f"{SUBSCRIPTION_ID}. "
            "La consulta debe ser exclusivamente "
            "de lectura y limitarse a esta "
            "suscripción."
        ),
    )


@pytest.mark.asyncio
@pytest.mark.live
async def test_procedure_target_resource_is_stable_across_three_live_runs():
    """
    FASE 16 — LIVE stability probe.

    Ejecuta Procedure v6 tres veces con exactamente
    el mismo prompt.

    Valores permitidos:

        "subscription"

    o:

        SUBSCRIPTION_ID

    Cualquier otra representación debe fallar.

    No se acepta:

        "Azure subscription"
        "suscripción Azure"
        "subscription_id"
        rutas ARM
        texto libre
        otro UUID
    """

    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = (
        FoundryAgents()
    )

    #
    # --------------------------------------------------
    # Baseline exacta
    # --------------------------------------------------
    #

    definition = (
        agents.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        )
    )

    assert (
        definition.version
        == "6"
    )

    request = (
        create_procedure_request()
    )

    prompt = (
        ProcedureExecutionExecutor
        ._build_prompt(
            request
        )
    )

    allowed_targets = {
        "subscription",
        SUBSCRIPTION_ID,
    }

    observed_targets = []

    print()
    print("=" * 80)
    print(
        "PROCEDURE TARGET_RESOURCE "
        "LIVE STABILITY PROBE"
    )
    print("=" * 80)

    for attempt in range(
        1,
        4,
    ):
        result = (
            await agents
            .run_procedure_execution(
                prompt
            )
        )

        assert (
            result
            is not None
        )

        assert (
            result.step
            is not None
        )

        target_resource = (
            result.step.target_resource
        )

        observed_targets.append(
            target_resource
        )

        print()
        print(
            f"attempt[{attempt}]"
        )

        print(
            "procedure_id =",
            result.procedure.id,
        )

        print(
            "procedure_version =",
            result.procedure.version,
        )

        print(
            "operation_domain =",
            result.step.operation_domain,
        )

        print(
            "operation_kind =",
            result.step.operation_kind,
        )

        print(
            "next_action =",
            result.next_action,
        )

        print(
            "required_parameters =",
            result.step.required_parameters,
        )

        print(
            "target_resource =",
            repr(
                target_resource
            ),
        )

        #
        # --------------------------------------------------
        # Identidad mínima del caso esperado
        # --------------------------------------------------
        #

        assert (
            result.alert_id
            == request.alert_id
        )

        assert (
            result.procedure.id
            == PROCEDURE_ID
        )

        assert (
            result.step.operation_domain
            == "azure"
        )

        assert (
            result.step.operation_kind
            == "read"
        )

        assert (
            result.next_action
            == "execute_step"
        )

        assert (
            result.step.required_parameters
            == [
                "subscription_id",
            ]
        )

        #
        # --------------------------------------------------
        # Gate principal
        # --------------------------------------------------
        #

        assert (
            target_resource
            in allowed_targets
        ), (
            "Procedure v6 devolvió un "
            "target_resource fuera del contrato. "
            f"attempt={attempt}; "
            f"target_resource={target_resource!r}; "
            f"allowed_targets="
            f"{sorted(allowed_targets)!r}"
        )

    print()
    print(
        "observed_targets =",
        observed_targets,
    )

    print()
    print(
        "RESULT = 3/3 accepted"
    )

    assert (
        len(
            observed_targets
        )
        == 3
    )