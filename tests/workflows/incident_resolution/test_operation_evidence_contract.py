import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
    StepEvidence,
)

from src.workflows.incident_resolution.azure_operations_models import (
    AzureOperationResult,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


OPERATION_ID = "op-evidence-001"
WORKFLOW_ID = "wf-evidence-001"
APPROVAL_ID = "apr-evidence-001"
ALERT_ID = "ALT-EVIDENCE-001"
CORRELATION_ID = "corr-evidence-001"
CONVERSATION_ID = "conv-evidence-001"

PROCEDURE_ID = "PROC-EVIDENCE-001"
PROCEDURE_VERSION = "v1.0"
CURRENT_STEP = 1
STEP_ID = "1"

OPERATION_DOMAIN = "azure"
OPERATION_KIND = OperationKind.READ
NEXT_ACTION = NextAction.EXECUTE_STEP
TARGET_RESOURCE = "subscription"

REQUIRED_PARAMETERS = [
    "subscription_id",
]


def resolved_parameters():
    return [
        ResolvedParameter(
            name="subscription_id",

            value="sub-001",

            source=(
                "normalized_alert."
                "subscription_id"
            ),
        )
    ]


def create_evidence(
) -> OperationEvidence:
    return OperationEvidence(
        operation_id=OPERATION_ID,
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        alert_id=ALERT_ID,

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure_id=PROCEDURE_ID,

        procedure_version=(
            PROCEDURE_VERSION
        ),

        current_step=CURRENT_STEP,
        step_id=STEP_ID,

        operation_domain=(
            OPERATION_DOMAIN
        ),

        operation_kind=(
            OPERATION_KIND
        ),

        next_action=(
            NEXT_ACTION
        ),

        target_resource=(
            TARGET_RESOURCE
        ),

        required_parameters=list(
            REQUIRED_PARAMETERS
        ),

        resolved_parameters=(
            resolved_parameters()
        ),
    )


def create_common_result(
    *,
    evidence: OperationEvidence | None = None,
) -> OperationResult:
    return OperationResult(
        operation_id=OPERATION_ID,
        workflow_id=WORKFLOW_ID,
        approval_id=APPROVAL_ID,
        alert_id=ALERT_ID,

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure_id=PROCEDURE_ID,

        procedure_version=(
            PROCEDURE_VERSION
        ),

        current_step=CURRENT_STEP,
        step_id=STEP_ID,

        operation_domain=(
            OPERATION_DOMAIN
        ),

        operation_kind=(
            OPERATION_KIND
        ),

        next_action=(
            NEXT_ACTION
        ),

        target_resource=(
            TARGET_RESOURCE
        ),

        required_parameters=list(
            REQUIRED_PARAMETERS
        ),

        resolved_parameters=(
            resolved_parameters()
        ),

        success=True,

        response_text="fake-result",

        error=None,

        evidence=evidence,
    )


def test_operation_evidence_contains_operational_identity():
    assert (
        tuple(
            OperationEvidence.model_fields
        )
        == (
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
            "tool_calls",
            "mcp_calls",
            "tool_results",
            "mcp_results",
            "response_errors",
        )
    )


def test_operation_evidence_rejects_unmodeled_fields():
    data = (
        create_evidence()
        .model_dump()
    )

    data[
        "tool_name"
    ] = "invented-tool"

    with pytest.raises(
        ValidationError,
    ):
        OperationEvidence(
            **data
        )


def test_operation_result_exposes_optional_evidence():
    result = (
        create_common_result()
    )

    assert result.evidence is None


def test_operation_result_accepts_matching_operation_evidence():
    evidence = (
        create_evidence()
    )

    result = (
        create_common_result(
            evidence=evidence
        )
    )

    assert (
        result.evidence
        == evidence
    )


def test_azure_operation_result_inherits_evidence_contract():
    result = AzureOperationResult(
        **create_common_result(
            evidence=(
                create_evidence()
            )
        ).model_dump()
    )

    assert isinstance(
        result,
        OperationResult,
    )

    assert isinstance(
        result.evidence,
        OperationEvidence,
    )


def test_operation_evidence_is_distinct_from_step_evidence():
    assert (
        OperationEvidence
        is not StepEvidence
    )

    assert not issubclass(
        OperationEvidence,
        StepEvidence,
    )

    assert not issubclass(
        StepEvidence,
        OperationEvidence,
    )
