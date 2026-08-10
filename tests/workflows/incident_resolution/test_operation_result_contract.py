from src.runtime.procedure.models import (
    OperationKind,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


CURRENT_OPERATION_RESULT_FIELDS = (
    "workflow_id",
    "approval_id",
    "alert_id",
    "correlation_id",
    "procedure_id",
    "procedure_version",
    "current_step",
    "step_id",
    "operation_kind",
    "target_resource",
    "success",
    "response_text",
    "error",
)


def create_azure_result(
    *,
    success: bool = True,
) -> AzureOperationResult:
    return AzureOperationResult(
        workflow_id="wf-operation-result-001",

        approval_id="apr-operation-result-001",

        alert_id="ALT-AZ-001",

        correlation_id="corr-azure-001",

        procedure_id="PROC-AZ-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        operation_kind=(
            OperationKind.READ
        ),

        target_resource=(
            "/subscriptions/sub-001/"
            "resourceGroups/rg-demo"
        ),

        success=success,

        response_text=(
            "Azure operation fake result."
            if success
            else None
        ),

        error=(
            None
            if success
            else "RuntimeError: test failure"
        ),
    )


def test_operation_result_contains_exact_current_contract():
    """
    FASE 15.3

    OperationResult extrae exactamente el contrato
    de resultado existente.

    No se adelantan campos pertenecientes a las
    siguientes subfases.
    """

    assert (
        tuple(
            OperationResult.model_fields
        )
        == CURRENT_OPERATION_RESULT_FIELDS
    )


def test_azure_operation_result_reuses_common_contract():
    """
    AzureOperationResult debe ser una especialización
    del resultado vendor-neutral.
    """

    assert issubclass(
        AzureOperationResult,
        OperationResult,
    )

    assert (
        tuple(
            AzureOperationResult.model_fields
        )
        == CURRENT_OPERATION_RESULT_FIELDS
    )


def test_azure_result_is_common_operation_result():
    """
    Un resultado Azure producido por el executor debe
    ser consumible como OperationResult común.
    """

    result = (
        create_azure_result()
    )

    assert isinstance(
        result,
        OperationResult,
    )

    assert isinstance(
        result,
        AzureOperationResult,
    )

    assert result.success is True

    assert (
        result.operation_kind
        == OperationKind.READ
    )


def test_operation_result_does_not_advance_later_phases():
    """
    FASE 15.3 no debe introducir accidentalmente
    contratos reservados para 15.5-15.11.
    """

    fields = (
        OperationResult.model_fields
    )

    assert (
        "operation_id"
        not in fields
    )

    assert (
        "conversation_id"
        not in fields
    )

    assert (
        "operation_domain"
        not in fields
    )

    assert (
        "next_action"
        not in fields
    )

    assert (
        "required_parameters"
        not in fields
    )

    assert (
        "resolved_parameters"
        not in fields
    )

    assert (
        "tool_provider"
        not in fields
    )

    assert (
        "tool_name"
        not in fields
    )

    assert (
        "mcp_call_id"
        not in fields
    )

    assert (
        "response_id"
        not in fields
    )

    assert (
        "evidence"
        not in fields
    )


def test_common_result_supports_failure_without_changing_semantics():
    """
    El contrato común preserva también el resultado
    de fallo existente.

    La semántica técnica definitiva de success se
    endurecerá en fases posteriores.
    """

    result = (
        create_azure_result(
            success=False
        )
    )

    assert isinstance(
        result,
        OperationResult,
    )

    assert result.success is False

    assert (
        result.response_text
        is None
    )

    assert (
        result.error
        == "RuntimeError: test failure"
    )
