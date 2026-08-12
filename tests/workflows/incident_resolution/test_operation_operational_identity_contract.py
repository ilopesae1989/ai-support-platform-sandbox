import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationRequest,
    OperationResult,
)


OPERATIONAL_FIELDS = (
    "operation_domain",
    "operation_kind",
    "operation_action",
    "capability_id",
    "hitl_required",
    "next_action",
    "target_resource",
    "required_parameters",
    "resolved_parameters",
)


def resolved_parameter(
    *,
    value: str = "sub-001",
    source: str = (
        "normalized_alert."
        "subscription_id"
    ),
):
    return ResolvedParameter(
        name="subscription_id",
        value=value,
        source=source,
    )


def base_data():
    return {
        "operation_id":
            "op-operational-001",

        "workflow_id":
            "wf-operational-001",

        "approval_id":
            "apr-operational-001",

        "alert_id":
            "ALT-OPERATIONAL-001",

        "correlation_id":
            "corr-operational-001",

        "conversation_id":
            "conv-operational-001",

        "procedure_id":
            "PROC-OPERATIONAL-001",

        "procedure_version":
            "v1.0",

        "current_step":
            1,

        "step_id":
            "1",

        "operation_domain":
            "azure",

        "operation_kind":
            OperationKind.READ,

        "next_action":
            NextAction.EXECUTE_STEP,

        "target_resource":
            "subscription",

        "required_parameters":
            [
                "subscription_id",
            ],

        "resolved_parameters":
            [
                resolved_parameter()
            ],
    }


def create_evidence(
    **updates,
) -> OperationEvidence:
    data = (
        base_data()
    )

    data.update(
        updates
    )

    return OperationEvidence(
        **data
    )


def create_result(
    *,
    evidence: OperationEvidence | None = None,
) -> OperationResult:
    return OperationResult(
        **base_data(),

        success=True,

        response_text="result",

        error=None,

        evidence=evidence,
    )


def test_operation_request_contains_operational_identity():
    for field_name in (
        OPERATIONAL_FIELDS
    ):
        assert (
            field_name
            in OperationRequest.model_fields
        )


def test_operation_result_contains_operational_identity():
    for field_name in (
        OPERATIONAL_FIELDS
    ):
        assert (
            field_name
            in OperationResult.model_fields
        )


def test_operation_evidence_contains_operational_identity():
    for field_name in (
        OPERATIONAL_FIELDS
    ):
        assert (
            field_name
            in OperationEvidence.model_fields
        )


def test_matching_operational_identity_is_accepted():
    evidence = (
        create_evidence()
    )

    result = (
        create_result(
            evidence=evidence
        )
    )

    for field_name in (
        OPERATIONAL_FIELDS
    ):
        assert (
            getattr(
                result.evidence,
                field_name,
            )
            == getattr(
                result,
                field_name,
            )
        )


@pytest.mark.parametrize(
    (
        "field_name",
        "tampered_value",
    ),
    [
        (
            "operation_domain",
            "database",
        ),
        (
            "operation_kind",
            OperationKind.WRITE,
        ),
        (
            "operation_action",
            OperationAction.VM_START,
        ),
        (
            "capability_id",
            "azure.vm.start",
        ),
        (
            "hitl_required",
            True,
        ),
        (
            "next_action",
            NextAction.BLOCKED,
        ),
        (
            "target_resource",
            "resource_group",
        ),
        (
            "required_parameters",
            [
                "tenant_id",
            ],
        ),
        (
            "resolved_parameters",
            [
                resolved_parameter(
                    value="sub-other"
                )
            ],
        ),
    ],
)
def test_result_rejects_operational_identity_tampering(
    field_name,
    tampered_value,
):
    evidence = (
        create_evidence(
            **{
                field_name:
                    tampered_value
            }
        )
    )

    with pytest.raises(
        ValidationError,
        match=field_name,
    ):
        create_result(
            evidence=evidence
        )


def test_result_rejects_resolved_parameter_source_tampering():
    evidence = (
        create_evidence(
            resolved_parameters=[
                resolved_parameter(
                    source="untrusted_source"
                )
            ]
        )
    )

    with pytest.raises(
        ValidationError,
        match="resolved_parameters",
    ):
        create_result(
            evidence=evidence
        )
