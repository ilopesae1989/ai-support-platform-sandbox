import pytest

from pydantic import (
    ValidationError,
)

from src.runtime.procedure.models import (
    NextAction,
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


IDENTITY_FIELDS = (
    "workflow_id",
    "approval_id",
    "alert_id",
    "correlation_id",
    "conversation_id",
)


BASE_IDENTITY = {
    "operation_id":
        "op-correlation-001",

    "workflow_id":
        "wf-correlation-001",

    "approval_id":
        "apr-correlation-001",

    "alert_id":
        "ALT-CORRELATION-001",

    "correlation_id":
        "corr-correlation-001",

    "conversation_id":
        "conv-correlation-001",
}


def operation_fields():
    return {
        "procedure_id":
            "PROC-CORRELATION-001",

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
                ResolvedParameter(
                    name="subscription_id",

                    value="sub-001",

                    source=(
                        "normalized_alert."
                        "subscription_id"
                    ),
                )
            ],
    }


def create_evidence(
    **updates,
) -> OperationEvidence:
    data = {
        **BASE_IDENTITY,
        **operation_fields(),
    }

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
        **BASE_IDENTITY,
        **operation_fields(),

        success=True,

        response_text="result",

        error=None,

        evidence=evidence,
    )


def test_operation_request_contains_all_correlation_fields():
    for field_name in IDENTITY_FIELDS:
        assert (
            field_name
            in OperationRequest.model_fields
        )


def test_operation_result_contains_all_correlation_fields():
    for field_name in IDENTITY_FIELDS:
        assert (
            field_name
            in OperationResult.model_fields
        )


def test_operation_evidence_contains_all_correlation_fields():
    for field_name in IDENTITY_FIELDS:
        assert (
            field_name
            in OperationEvidence.model_fields
        )


def test_matching_correlation_identity_is_accepted():
    result = (
        create_result(
            evidence=(
                create_evidence()
            )
        )
    )

    for field_name in IDENTITY_FIELDS:
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
            "workflow_id",
            "wf-other",
        ),
        (
            "approval_id",
            "apr-other",
        ),
        (
            "alert_id",
            "ALT-OTHER",
        ),
        (
            "correlation_id",
            "corr-other",
        ),
        (
            "conversation_id",
            "conv-other",
        ),
    ],
)
def test_result_rejects_evidence_identity_tampering(
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


def test_optional_correlation_values_must_also_match():
    evidence = (
        create_evidence(
            correlation_id=None,
            conversation_id=None,
        )
    )

    result_data = dict(
        BASE_IDENTITY
    )

    result_data[
        "correlation_id"
    ] = None

    result_data[
        "conversation_id"
    ] = None

    result = OperationResult(
        **result_data,
        **operation_fields(),

        success=True,

        response_text="result",

        error=None,

        evidence=evidence,
    )

    assert (
        result.correlation_id
        is None
    )

    assert (
        result.conversation_id
        is None
    )
