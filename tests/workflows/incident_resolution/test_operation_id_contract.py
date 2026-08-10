from uuid import (
    UUID,
)

from src.runtime.procedure.identity import (
    create_operation_id,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.operation_evidence import (
    OperationEvidence,
)

from src.workflows.incident_resolution.operation_models import (
    OperationRequest,
    OperationResult,
)

from tests.workflows.incident_resolution.test_operation_request_contract import (
    create_approved_step,
)


def build_id(
    step,
) -> str:
    return create_operation_id(
        workflow_id=(
            step.workflow_id
        ),

        approval_id=(
            step.approval_id
        ),

        alert_id=(
            step.alert_id
        ),

        procedure_id=(
            step.procedure_id
        ),

        current_step=(
            step.current_step
        ),

        step_id=(
            step.step_id
        ),
    )


def test_operation_id_is_deterministic():
    step = (
        create_approved_step()
    )

    assert (
        build_id(step)
        == build_id(step)
    )


def test_different_approved_identity_changes_operation_id():
    step = (
        create_approved_step()
    )

    changed = (
        step.model_copy(
            update={
                "approval_id":
                    (
                        "apr-22222222-2222-4222-"
                        "8222-222222222222"
                    )
            },
            deep=True,
        )
    )

    assert (
        build_id(step)
        != build_id(changed)
    )


def test_operation_id_has_distinct_uuid5_identity():
    step = (
        create_approved_step()
    )

    operation_id = (
        build_id(step)
    )

    assert (
        operation_id.startswith(
            "op-"
        )
    )

    parsed = UUID(
        operation_id.removeprefix(
            "op-"
        )
    )

    assert parsed.version == 5

    assert (
        operation_id
        != step.workflow_id
    )

    assert (
        operation_id
        != step.approval_id
    )


def test_operation_id_survives_common_contract_boundary():
    step = (
        create_approved_step()
    )

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    assert (
        candidate.operation_id
        == build_id(step)
    )

    assert (
        "operation_id"
        in OperationRequest.model_fields
    )

    assert (
        "operation_id"
        in OperationResult.model_fields
    )

    assert (
        "operation_id"
        in OperationEvidence.model_fields
    )
