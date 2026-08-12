from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


CURRENT_OPERATION_RESULT_FIELDS = (
    "operation_id",
    "workflow_id",
    "approval_id",
    "alert_id",
    "correlation_id",
    "conversation_id",
    "procedure_id",
    "procedure_version",
    "current_step",
    "step_id",
    "operation_domain",
    "operation_kind",
    "operation_action",
    "next_action",
    "target_resource",
    "required_parameters",
    "resolved_parameters",
    "success",
    "technical_success",
    "response_text",
    "error",
    "evidence",
)


def create_azure_result(
    *,
    success: bool = True,
) -> AzureOperationResult:
    return AzureOperationResult(
        operation_id="op-operation-result-001",

        workflow_id="wf-operation-result-001",

        approval_id="apr-operation-result-001",

        alert_id="ALT-AZ-001",

        correlation_id="corr-azure-001",

        conversation_id="conv-azure-001",

        procedure_id="PROC-AZ-001",

        procedure_version="v1.0",

        current_step=1,

        step_id="1",

        operation_domain="azure",

        operation_kind=(
            OperationKind.READ
        ),

        next_action=(
            NextAction.EXECUTE_STEP
        ),

        target_resource="subscription",

        required_parameters=[
            "subscription_id",
        ],

        resolved_parameters=[
            ResolvedParameter(
                name="subscription_id",

                value="sub-001",

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        success=success,

        technical_success=(
            None
            if success
            else False
        ),

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


def test_operation_result_contains_current_contract():
    assert (
        tuple(
            OperationResult.model_fields
        )
        == CURRENT_OPERATION_RESULT_FIELDS
    )


def test_azure_operation_result_reuses_common_contract():
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
    result = (
        create_azure_result()
    )

    assert isinstance(
        result,
        OperationResult,
    )

    assert result.success is True

    assert (
        result.technical_success
        is None
    )

    assert result.evidence is None


def test_operation_result_does_not_advance_later_phases():
    fields = (
        OperationResult.model_fields
    )

    assert (
        "technical_success"
        in fields
    )

    assert (
        "tool_provider"
        not in fields
    )

    assert (
        "provider_response_id"
        not in fields
    )


def test_common_result_supports_failure_semantics():
    result = (
        create_azure_result(
            success=False
        )
    )

    assert result.success is False

    assert (
        result.technical_success
        is False
    )

    assert (
        result.response_text
        is None
    )

    assert (
        result.error
        == "RuntimeError: test failure"
    )
