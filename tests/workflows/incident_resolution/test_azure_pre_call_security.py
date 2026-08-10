import pytest

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from src.workflows.incident_resolution.azure_operations import (
    build_azure_operation_request,
)

from src.workflows.incident_resolution.azure_operations_models import (
    VerifiedAzureOperationRequest,
)

from src.workflows.incident_resolution.executors.azure_operations import (
    AzureOperationsExecutor,
)

from src.workflows.incident_resolution.pre_call_security import (
    PreCallSecurityError,
    PreCallSecurityVerifier,
)


SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

OTHER_SUBSCRIPTION_ID = (
    "00000000-0000-0000-"
    "0000-000000000000"
)


def create_approved_step() -> (
    ApprovedProcedureStep
):
    return ApprovedProcedureStep(
        workflow_id=(
            "wf-ALT-AZ-RG-LIST-001"
        ),

        approval_id=(
            "apr-11111111-1111-4111-"
            "8111-111111111111"
        ),

        alert_id=(
            "ALT-AZ-RG-LIST-001"
        ),

        correlation_id=(
            "corr-azure-rg-list-live-001"
        ),

        conversation_id=(
            "conv-azure-rg-list-001"
        ),

        procedure_id=(
            "NTTSY-SBX-AZ-001"
        ),

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

                value=(
                    SUBSCRIPTION_ID
                ),

                source=(
                    "normalized_alert."
                    "subscription_id"
                ),
            )
        ],

        approved=True,
    )


def test_builder_creates_complete_candidate():
    step = create_approved_step()

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    assert (
        candidate.workflow_id
        == step.workflow_id
    )

    assert (
        candidate.alert_id
        == step.alert_id
    )

    assert (
        candidate.conversation_id
        == step.conversation_id
    )

    assert (
        candidate.procedure_id
        == step.procedure_id
    )

    assert (
        candidate.procedure_version
        == step.procedure_version
    )

    assert (
        candidate.current_step
        == step.current_step
    )

    assert (
        candidate.step_id
        == step.step_id
    )

    assert (
        candidate.operation_domain
        == "azure"
    )

    assert (
        candidate.operation_kind
        == OperationKind.READ
    )

    assert (
        candidate.next_action
        == NextAction.EXECUTE_STEP
    )

    assert (
        candidate.target_resource
        == "subscription"
    )

    assert (
        candidate.required_parameters
        == [
            "subscription_id",
        ]
    )

    assert len(
        candidate.resolved_parameters
    ) == 1

    assert (
        candidate
        .resolved_parameters[0]
        .value
        == SUBSCRIPTION_ID
    )


def test_exact_candidate_becomes_verified_request():
    step = create_approved_step()

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    verified = (
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=candidate,
        )
    )

    assert isinstance(
        verified,
        VerifiedAzureOperationRequest,
    )

    assert (
        verified.security_verified
        is True
    )

    assert (
        verified.verification_source
        == "pre_call_security_verifier"
    )

    assert (
        verified
        .resolved_parameters[0]
        .value
        == SUBSCRIPTION_ID
    )


def test_candidate_does_not_share_resolved_parameter_object():
    step = create_approved_step()

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    candidate.resolved_parameters[
        0
    ].value = OTHER_SUBSCRIPTION_ID

    #
    # Modificar candidate no debe poder alterar
    # el snapshot aprobado.
    #
    assert (
        step.resolved_parameters[0].value
        == SUBSCRIPTION_ID
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "modified_value",
    ),
    [
        (
            "operation_id",
            (
                "op-00000000-0000-5000-"
                "8000-000000000000"
            ),
        ),
        (
            "workflow_id",
            "wf-other",
        ),
        (
            "alert_id",
            "ALT-OTHER",
        ),
        (
            "conversation_id",
            "conv-other",
        ),
        (
            "approval_id",
            (
                "apr-22222222-2222-4222-"
                "8222-222222222222"
            ),
        ),
        (
            "correlation_id",
            "corr-attacker",
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
            99,
        ),
        (
            "step_id",
            "99",
        ),
        (
            "operation_domain",
            "database",
        ),
        (
            "operation_kind",
            OperationKind.WRITE,
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
                ResolvedParameter(
                    name="subscription_id",

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
def test_pre_call_rejects_candidate_tampering(
    field_name,
    modified_value,
):
    step = create_approved_step()

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    tampered = (
        candidate.model_copy(
            update={
                field_name:
                    modified_value,
            },
            deep=True,
        )
    )

    with pytest.raises(
        PreCallSecurityError,
    ):
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=tampered,
        )


def test_pre_call_rejects_parameter_source_tampering():
    step = create_approved_step()

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    tampered = candidate.model_copy(
        deep=True
    )

    tampered.resolved_parameters[
        0
    ].source = "untrusted_source"

    with pytest.raises(
        PreCallSecurityError,
        match="resolved_parameters",
    ):
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=tampered,
        )


def test_builder_rejects_parameter_binding_mismatch():
    step = create_approved_step()

    step.resolved_parameters = []

    with pytest.raises(
        ValueError,
        match="no coinciden exactamente",
    ):
        build_azure_operation_request(
            step
        )


def test_builder_rejects_duplicate_required_parameters():
    step = create_approved_step()

    step.required_parameters = [
        "subscription_id",
        "subscription_id",
    ]

    step.resolved_parameters = [
        ResolvedParameter(
            name="subscription_id",
            value=SUBSCRIPTION_ID,
            source=(
                "normalized_alert."
                "subscription_id"
            ),
        ),
        ResolvedParameter(
            name="subscription_id",
            value=SUBSCRIPTION_ID,
            source=(
                "normalized_alert."
                "subscription_id"
            ),
        ),
    ]

    with pytest.raises(
        ValueError,
        match="duplicados",
    ):
        build_azure_operation_request(
            step
        )


def test_builder_requires_exact_azure_domain():
    step = create_approved_step()

    step.operation_domain = (
        " Azure "
    )

    with pytest.raises(
        ValueError,
        match="exactamente",
    ):
        build_azure_operation_request(
            step
        )


def test_prompt_contains_exact_resolved_parameter():
    step = create_approved_step()

    candidate = (
        build_azure_operation_request(
            step
        )
    )

    verified = (
        PreCallSecurityVerifier.verify(
            approved_step=step,
            candidate=candidate,
        )
    )

    prompt = (
        AzureOperationsExecutor
        ._build_prompt(
            verified
        )
    )

    assert (
        SUBSCRIPTION_ID
        in prompt
    )

    assert (
        (
            "subscription_id = "
            + SUBSCRIPTION_ID
        )
        in prompt
    )

    assert (
        "Dominio: azure"
        in prompt
    )

    assert (
        "Tipo: read"
        in prompt
    )

    assert (
        "Acción: execute_step"
        in prompt
    )

    assert (
        "Recurso objetivo: subscription"
        in prompt
    )