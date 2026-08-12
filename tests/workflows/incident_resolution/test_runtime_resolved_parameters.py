import pytest

from src.agents.contracts import (
    ProcedureExecutionResult,
)

from src.runtime.procedure.models import (
    ResolvedParameter,
)

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)

from src.workflows.incident_resolution.models import (
    ExecutionIdentity,
    ProcedureExecutionContext,
    ProcedureExecutionRequest,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

TENANT_ID = (
    "0cb40b2b-6cfc-4c63-"
    "bf7b-da710ea390cb"
)

WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

CORRELATION_ID = (
    "corr-azure-rg-list-live-001"
)


def create_request() -> (
    ProcedureExecutionRequest
):
    return ProcedureExecutionRequest(
        alert_id="ALT-AZ-RG-LIST-001",

        procedure_found=True,
        procedure_match="exact",
        execution_eligible=True,

        procedure_id=(
            "NTTSY-SBX-AZ-001"
        ),

        procedure_name=(
            "Consulta de Resource Groups "
            "de una suscripción Azure"
        ),

        procedure_version="v1.0",

        affected_resource=(
            SUBSCRIPTION_ID
        ),

        incident_description=(
            "Obtener la lista de Resource Groups "
            "de la suscripción autorizada."
        ),
    )


def create_identity() -> ExecutionIdentity:
    return ExecutionIdentity(
        workflow_id=WORKFLOW_ID,

        alert_id=(
            "ALT-AZ-RG-LIST-001"
        ),

        correlation_id=(
            CORRELATION_ID
        ),
    )


def create_operational_context(
    *,
    subscription_id: str | None = (
        SUBSCRIPTION_ID
    ),
    resource_group: str | None = None,
) -> OperationalContext:
    return OperationalContext(
        alert_id=(
            "ALT-AZ-RG-LIST-001"
        ),

        affected_resource=(
            SUBSCRIPTION_ID
        ),

        resource_type=(
            "subscription"
        ),

        service=(
            "Azure Resource Manager"
        ),

        environment=(
            "sandbox"
        ),

        subscription_id=(
            subscription_id
        ),

        resource_group=(
            resource_group
        ),

        tenant_id=(
            TENANT_ID
        ),

        correlation_id=(
            CORRELATION_ID
        ),
    )


def create_result(
    *,
    required_parameters: list[str],
    target_resource: str = "subscription",
) -> ProcedureExecutionResult:
    return (
        ProcedureExecutionResult.model_validate(
            {
                "alert_id":
                    "ALT-AZ-RG-LIST-001",

                "procedure": {
                    "id":
                        "NTTSY-SBX-AZ-001",

                    "name": (
                        "Consulta de Resource Groups "
                        "de una suscripción Azure"
                    ),

                    "version":
                        "v1.0",
                },

                "execution_allowed":
                    True,

                "blocked_by_policy":
                    False,

                "total_steps":
                    1,

                "current_step":
                    1,

                "step": {
                    "id":
                        "1",

                    "description": (
                        "Consultar los Resource Groups "
                        "de la suscripción autorizada."
                    ),

                    "step_type":
                        "technical_operation",

                    "operation_domain":
                        "azure",

                    "operation_kind":
                        "read",

                    "target_resource":
                        target_resource,

                    "required_parameters":
                        required_parameters,

                    "preconditions":
                        [],

                    "expected_result": (
                        "Lista de Resource Groups "
                        "visibles en la suscripción."
                    ),

                    "verification": (
                        "Validar que únicamente se "
                        "devuelve información de la "
                        "suscripción autorizada."
                    ),
                },

                "resolution_criteria":
                    (
                        "La lista se obtiene "
                        "correctamente."
                    ),

                "next_action":
                    "execute_step",

                "escalation": {
                    "required":
                        False,

                    "team":
                        None,

                    "level":
                        None,

                    "criteria":
                        None,
                },

                "requires_clarification":
                    False,

                "missing_information":
                    [],

                "source_documents": [
                    (
                        "NTTSY-SBX-AZ-001 "
                        "v1.0"
                    )
                ],

                "confidence":
                    0.99,
            }
        )
    )


def create_execution_context(
    *,
    required_parameters: list[str],
    subscription_id: str | None = (
        SUBSCRIPTION_ID
    ),
    target_resource: str = "subscription",
) -> ProcedureExecutionContext:
    return ProcedureExecutionContext(
        request=(
            create_request()
        ),

        result=create_result(
            required_parameters=(
                required_parameters
            ),

            target_resource=(
                target_resource
            ),
        ),

        execution_identity=(
            create_identity()
        ),

        operational_context=(
            create_operational_context(
                subscription_id=(
                    subscription_id
                )
            )
        ),
    )


def test_runtime_resolves_subscription_id_before_hitl():
    context = (
        create_execution_context(
            required_parameters=[
                "subscription_id",
            ],
        )
    )

    state = (
        ProcedureRuntimeExecutor
        ._build_runtime_state(
            context
        )
    )

    assert (
        state.step.target_resource
        == "subscription"
    )

    assert (
        state.step.required_parameters
        == [
            "subscription_id",
        ]
    )

    assert state.resolved_parameters == [
        ResolvedParameter(
            name=(
                "subscription_id"
            ),

            value=(
                SUBSCRIPTION_ID
            ),

            source=(
                "normalized_alert.subscription_id"
            ),
        )
    ]


def test_runtime_uses_authoritative_resource_type_instead_of_llm_target():
    """
    Reproduce el comportamiento observado LIVE:

    Procedure puede expresar cognitivamente el
    target_resource como el UUID concreto de la
    suscripción.

    El Runtime debe convertir exclusivamente esta
    operación conocida al scope canónico:

        target_resource = "subscription"

    mientras la identidad concreta permanece en:

        resolved_parameters.subscription_id
    """

    context = (
        create_execution_context(
            required_parameters=[
                "subscription_id",
            ],

            target_resource=(
                SUBSCRIPTION_ID
            ),
        )
    )

    #
    # Precondición:
    #
    # La salida cognitiva contiene el UUID.
    #
    assert (
        context.result.step.target_resource
        == SUBSCRIPTION_ID
    )

    #
    # Fuente operacional autoritativa.
    #
    assert (
        context.operational_context.resource_type
        == "subscription"
    )

    assert (
        context.operational_context.subscription_id
        == SUBSCRIPTION_ID
    )

    state = (
        ProcedureRuntimeExecutor
        ._build_runtime_state(
            context
        )
    )

    #
    # El UUID cognitivo no atraviesa como
    # target_resource operacional.
    #
    assert (
        state.step.target_resource
        == "subscription"
    )

    #
    # El identificador concreto sí permanece,
    # resuelto exclusivamente desde la alerta
    # normalizada.
    #
    assert state.resolved_parameters == [
        ResolvedParameter(
            name=(
                "subscription_id"
            ),

            value=(
                SUBSCRIPTION_ID
            ),

            source=(
                "normalized_alert.subscription_id"
            ),
        )
    ]


def test_runtime_preserves_other_azure_target_without_canonical_rule():
    """
    Una regla de canonicalización específica para
    subscription no puede destruir otros targets
    Azure concretos.

    Este test protege la regresión observada cuando
    Runtime sustituía cualquier target Azure por:

        OperationalContext.resource_type
    """

    target_resource = (
        "/subscriptions/sub-test/"
        "resourceGroups/rg-lab-ia-copilot/"
        "providers/Microsoft.Compute/"
        "virtualMachines/vm-demo-01"
    )

    context = (
        create_execution_context(
            required_parameters=[],

            target_resource=(
                target_resource
            ),
        )
    )

    state = (
        ProcedureRuntimeExecutor
        ._build_runtime_state(
            context
        )
    )

    assert (
        state.step.target_resource
        == target_resource
    )

    assert (
        state.resolved_parameters
        == []
    )


def test_runtime_blocks_mismatched_subscription_target_before_hitl():
    """
    Si Procedure devuelve una suscripción distinta
    de la que existe en OperationalContext, Runtime
    debe bloquear antes del HITL.

    No se normaliza silenciosamente un target
    cognitivo incompatible.
    """

    context = (
        create_execution_context(
            required_parameters=[
                "subscription_id",
            ],

            target_resource=(
                "00000000-0000-0000-"
                "0000-000000000000"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "target_resource incompatible"
        ),
    ):
        (
            ProcedureRuntimeExecutor
            ._build_runtime_state(
                context
            )
        )


def test_runtime_blocks_missing_required_parameter_before_hitl():
    context = (
        create_execution_context(
            required_parameters=[
                "subscription_id",
            ],

            subscription_id=None,
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "No pueden resolverse todos "
            "los parámetros"
        ),
    ):
        (
            ProcedureRuntimeExecutor
            ._build_runtime_state(
                context
            )
        )


def test_runtime_blocks_unknown_required_parameter_before_hitl():
    context = (
        create_execution_context(
            required_parameters=[
                "invented_parameter",
            ],
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Parámetros pendientes: "
            "invented_parameter"
        ),
    ):
        (
            ProcedureRuntimeExecutor
            ._build_runtime_state(
                context
            )
        )