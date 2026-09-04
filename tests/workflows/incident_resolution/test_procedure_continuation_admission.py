import pytest
from pydantic import ValidationError

from src.workflows.incident_resolution.continuation_context import (
    ProcedureContinuationContext,
)


ADMISSION_FIELDS = {
    "procedure_found",
    "procedure_match",
    "execution_eligible",
}


def base_payload():
    # Payload deliberadamente previo al admission
    # snapshot. No construimos el modelo aquí:
    # precisamente necesitamos poder probar que
    # la ausencia de esos campos falla cerrado.
    return {
        "request_affected_resource":
            "SERVER01",

        "incident_description":
            "Incident description",

        "operational_affected_resource":
            "SERVER01",

        "resource_type":
            "TestResource",

        "service":
            "Test Service",

        "environment":
            None,

        "incident_origin":
            "observed",

        "subscription_id":
            None,

        "resource_group":
            None,

        "vm_name":
            None,

        "tenant_id":
            None,
    }


def test_continuation_context_declares_required_admission_snapshot():
    assert ADMISSION_FIELDS.issubset(
        ProcedureContinuationContext.model_fields
    )


def test_continuation_context_accepts_exact_admitted_snapshot():
    payload = base_payload()

    payload.update(
        {
            "procedure_found": True,
            "procedure_match": "exact",
            "execution_eligible": True,
        }
    )

    context = (
        ProcedureContinuationContext
        .model_validate(
            payload
        )
    )

    assert context.procedure_found is True
    assert context.procedure_match == "exact"
    assert context.execution_eligible is True


def test_continuation_context_missing_admission_snapshot_fails_closed():
    payload = base_payload()

    with pytest.raises(
        ValidationError
    ):
        ProcedureContinuationContext.model_validate(
            payload
        )
