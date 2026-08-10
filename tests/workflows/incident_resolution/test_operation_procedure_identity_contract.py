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


PROCEDURE_FIELDS = (
    "procedure_id",
    "procedure_version",
    "current_step",
    "step_id",
)


BASE_IDENTITY = {
    "operation_id":
        "op-procedure-001",

    "workflow_id":
        "wf-procedure-001",

    "approval_id":
        "apr-procedure-001",

    "alert_id":
        "ALT-PROCEDURE-001",

    "correlation_id":
        "corr-procedure-001",

    "conversation_id":
        "conv-procedure-001",

    "procedure_id":
        "PROC-PROCEDURE-001",

    "procedure_version":
        "v1.0",

    "current_step":
        1,

    "step_id":
        "1",
}


def operational_fields():
    return {
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
        **operational_fields(),
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
    **updates,
) -> OperationResult:
    data = {
        **BASE_IDENTITY,
        **operational_fields(),
    }

    data.update(
        updates
    )

    return OperationResult(
        **data,

        success=True,

        response_text="result",

        error=None,

        evidence=evidence,
    )


def test_operation_request_contains_procedure_identity():
    for field_name in PROCEDURE_FIELDS:
        assert (
            field_name
            in OperationRequest.model_fields
        )


def test_operation_result_contains_procedure_identity():
    for field_name in PROCEDURE_FIELDS:
        assert (
            field_name
            in OperationResult.model_fields
        )


def test_operation_evidence_contains_procedure_identity():
    for field_name in PROCEDURE_FIELDS:
        assert (
            field_name
            in OperationEvidence.model_fields
        )


def test_matching_procedure_identity_is_accepted():
    result = (
        create_result(
            evidence=(
                create_evidence()
            )
        )
    )

    for field_name in PROCEDURE_FIELDS:
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
            "procedure_id",
            "PROC-OTHER",
        ),
        (
            "procedure_version",
            "v9.9",
        ),
        (
            "current_step",
            99,
        ),
        (
            "step_id",
            "99",
        ),
    ],
)
def test_result_rejects_procedure_identity_tampering(
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


def test_optional_procedure_version_must_match():
    evidence = (
        create_evidence(
            procedure_version=None,
        )
    )

    result = (
        create_result(
            evidence=evidence,
            procedure_version=None,
        )
    )

    assert (
        result.procedure_version
        is None
    )

    assert (
        result.evidence.procedure_version
        is None
    )
