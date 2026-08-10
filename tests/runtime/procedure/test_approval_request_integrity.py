from dataclasses import (
    replace,
)

import pytest

from src.runtime.procedure.models import (
    ApprovalStatus,
    OperationKind,
    ProcedureReference,
    ProcedureRuntimeState,
    ProcedureStep,
    ResolvedParameter,
    StepStatus,
    WorkflowStatus,
)

from src.runtime.procedure.workflow import (
    ProcedureApprovalExecutor,
)


WORKFLOW_ID = (
    "wf-11111111-1111-4111-"
    "8111-111111111111"
)

APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

ALERT_ID = (
    "ALT-AZ-RG-LIST-001"
)

CORRELATION_ID = (
    "corr-azure-rg-list-live-001"
)

CONVERSATION_ID = (
    "conv-azure-rg-list-001"
)

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

OTHER_SUBSCRIPTION_ID = (
    "00000000-0000-0000-"
    "0000-000000000000"
)


def create_pending_state() -> (
    ProcedureRuntimeState
):
    return ProcedureRuntimeState(
        workflow_id=(
            WORKFLOW_ID
        ),

        approval_id=(
            APPROVAL_ID
        ),

        alert_id=(
            ALERT_ID
        ),

        correlation_id=(
            CORRELATION_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        procedure=ProcedureReference(
            id=(
                "NTTSY-SBX-AZ-001"
            ),

            name=(
                "Consulta de Resource Groups "
                "de una suscripción Azure"
            ),

            version="v1.0",
        ),

        total_steps=1,

        current_step=1,

        step=ProcedureStep(
            id="1",

            description=(
                "Consultar Resource Groups "
                "de la suscripción autorizada."
            ),

            step_type=(
                "technical_operation"
            ),

            operation_domain="azure",

            operation_kind=(
                OperationKind.READ
            ),

            target_resource=(
                "subscription"
            ),

            required_parameters=[
                "subscription_id",
            ],

            preconditions=[],

            expected_result=(
                "Lista de Resource Groups."
            ),

            verification=(
                "Validar que sólo se consulta "
                "la suscripción autorizada."
            ),
        ),

        resolved_parameters=[
            ResolvedParameter(
                name=(
                    "subscription_id"
                ),

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        workflow_status=(
            WorkflowStatus.WAITING_HUMAN
        ),

        step_status=(
            StepStatus.WAITING_APPROVAL
        ),

        approval_status=(
            ApprovalStatus.PENDING
        ),
    )


def create_executor_with_pending_state():
    executor = (
        ProcedureApprovalExecutor()
    )

    executor._pending_state = (
        create_pending_state()
    )

    return executor


def test_approval_request_contains_full_operational_identity():
    executor = (
        create_executor_with_pending_state()
    )

    state = (
        executor._pending_state
    )

    assert state is not None

    request = (
        executor._build_approval_request(
            state
        )
    )

    assert (
        request.workflow_id
        == WORKFLOW_ID
    )

    assert (
        request.approval_id
        == APPROVAL_ID
    )

    assert (
        request.alert_id
        == ALERT_ID
    )

    assert (
        request.correlation_id
        == CORRELATION_ID
    )

    assert (
        request.conversation_id
        == CONVERSATION_ID
    )

    assert (
        request.procedure_id
        == "NTTSY-SBX-AZ-001"
    )

    assert (
        request.procedure_version
        == "v1.0"
    )

    assert (
        request.current_step
        == 1
    )

    assert (
        request.step_id
        == "1"
    )

    assert (
        request.operation_domain
        == "azure"
    )

    assert (
        request.operation_kind
        == "read"
    )

    assert (
        request.next_action
        == "execute_step"
    )

    assert (
        request.target_resource
        == "subscription"
    )

    assert (
        request.required_parameters
        == [
            "subscription_id",
        ]
    )

    assert (
        request.resolved_parameters
        == [
            ResolvedParameter(
                name=(
                    "subscription_id"
                ),

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ]
    )


def test_exact_approval_request_is_valid():
    executor = (
        create_executor_with_pending_state()
    )

    state = (
        executor._pending_state
    )

    assert state is not None

    request = (
        executor._build_approval_request(
            state
        )
    )

    executor._validate_original_request(
        request
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "modified_value",
    ),
    [
        (
            "workflow_id",
            "wf-other",
        ),

        (
            "approval_id",
            (
                "apr-22222222-2222-4222-"
                "8222-222222222222"
            ),
        ),

        (
            "alert_id",
            "ALT-OTHER",
        ),

        (
            "correlation_id",
            "corr-attacker",
        ),

        (
            "conversation_id",
            "conv-other",
        ),

        (
            "procedure_id",
            "NTTSY-OTHER",
        ),

        (
            "procedure_version",
            "v9.9",
        ),

        (
            "current_step",
            2,
        ),

        (
            "step_id",
            "99",
        ),

        (
            "description",
            "Descripción alterada.",
        ),

        (
            "operation_domain",
            "database",
        ),

        (
            "operation_kind",
            "write",
        ),

        (
            "next_action",
            "blocked",
        ),

        (
            "target_resource",
            "another-subscription",
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
                ResolvedParameter(
                    name=(
                        "subscription_id"
                    ),

                    value=(
                        OTHER_SUBSCRIPTION_ID
                    ),

                    source=(
                        "normalized_alert."
                        "subscription_id"
                    ),
                )
            ],
        ),
    ],
)
def test_modified_approval_identity_is_rejected(
    field_name,
    modified_value,
):
    executor = (
        create_executor_with_pending_state()
    )

    state = (
        executor._pending_state
    )

    assert state is not None

    request = (
        executor._build_approval_request(
            state
        )
    )

    modified_request = replace(
        request,
        **{
            field_name:
                modified_value,
        },
    )

    with pytest.raises(
        RuntimeError,
        match="fue alterada",
    ):
        executor._validate_original_request(
            modified_request
        )


def test_required_parameter_order_is_part_of_approval_identity():
    executor = (
        ProcedureApprovalExecutor()
    )

    state = (
        create_pending_state()
    )

    state.step.required_parameters = [
        "tenant_id",
        "subscription_id",
    ]

    state.resolved_parameters = [
        ResolvedParameter(
            name="tenant_id",

            value=(
                "0cb40b2b-6cfc-4c63-"
                "bf7b-da710ea390cb"
            ),

            source=(
                "normalized_alert.tenant_id"
            ),
        ),

        ResolvedParameter(
            name="subscription_id",

            value=(
                SUBSCRIPTION_ID
            ),

            source=(
                "normalized_alert."
                "subscription_id"
            ),
        ),
    ]

    executor._pending_state = (
        state
    )

    request = (
        executor._build_approval_request(
            state
        )
    )

    modified_request = replace(
        request,

        required_parameters=[
            "subscription_id",
            "tenant_id",
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="fue alterada",
    ):
        executor._validate_original_request(
            modified_request
        )


def test_approval_without_pending_state_is_rejected():
    executor = (
        ProcedureApprovalExecutor()
    )

    state = (
        create_pending_state()
    )

    request = (
        executor._build_approval_request(
            state
        )
    )

    with pytest.raises(
        RuntimeError,
        match="sin estado pendiente",
    ):
        executor._validate_original_request(
            request
        )