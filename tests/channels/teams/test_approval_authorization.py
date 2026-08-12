import pytest

from pydantic import (
    ValidationError,
)

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
    ExactTeamsApprovalPolicy,
    TeamsApprovalAuthorizationError,
    TeamsApprovalPrincipal,
    authorize_teams_approval_invocation,
)

from src.channels.teams.approval_invocation import (
    build_teams_approval_invocation,
)

from tests.channels.teams.test_activity_identity import (
    AAD_OBJECT_ID,
    TENANT_ID,
    create_activity,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)

POLICY_ID = (
    "teams-hitl-sandbox-v1"
)


def create_invocation(
    *,
    tenant_id: str = TENANT_ID,
    aad_object_id: str = AAD_OBJECT_ID,
):
    activity = (
        create_activity(
            tenant_id=(
                tenant_id
            ),

            aad_object_id=(
                aad_object_id
            ),

            action_data={
                "action": (
                    "approval_decision"
                ),

                "approval_id": (
                    APPROVAL_ID
                ),

                "decision": (
                    "approve"
                ),
            },
        )
    )

    return (
        build_teams_approval_invocation(
            activity
        )
    )


def create_policy(
) -> ExactTeamsApprovalPolicy:
    return ExactTeamsApprovalPolicy(
        policy_id=(
            POLICY_ID
        ),

        allowed_principals=(
            TeamsApprovalPrincipal(
                tenant_id=(
                    TENANT_ID
                ),

                aad_object_id=(
                    AAD_OBJECT_ID
                ),
            ),
        ),
    )


def test_exact_authenticated_principal_is_authorized():
    authorized = (
        authorize_teams_approval_invocation(
            invocation=(
                create_invocation()
            ),

            policy=(
                create_policy()
            ),
        )
    )

    assert isinstance(
        authorized,
        AuthorizedTeamsApprovalInvocation,
    )

    assert (
        authorized.policy_id
        == POLICY_ID
    )

    assert (
        authorized.operator.tenant_id
        == TENANT_ID
    )

    assert (
        authorized.operator.aad_object_id
        == AAD_OBJECT_ID
    )

    assert (
        authorized.action.approval_id
        == APPROVAL_ID
    )


def test_wrong_aad_object_id_is_rejected():
    invocation = (
        create_invocation(
            aad_object_id=(
                "22222222-2222-4222-"
                "8222-222222222222"
            )
        )
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
        )


def test_wrong_tenant_is_rejected():
    invocation = (
        create_invocation(
            tenant_id=(
                "aaaaaaaa-aaaa-4aaa-"
                "8aaa-aaaaaaaaaaaa"
            )
        )
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
        )


def test_same_aad_object_id_in_other_tenant_is_rejected():
    invocation = (
        create_invocation(
            tenant_id=(
                "aaaaaaaa-aaaa-4aaa-"
                "8aaa-aaaaaaaaaaaa"
            ),

            aad_object_id=(
                AAD_OBJECT_ID
            ),
        )
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
        )


def test_policy_cannot_authorize_by_display_name():
    invocation = (
        create_invocation(
            aad_object_id=(
                "22222222-2222-4222-"
                "8222-222222222222"
            )
        )
    )

    # El activity helper utiliza el mismo
    # display_name "Operador Sandbox".
    #
    # Ese nombre no concede autorización.
    assert (
        invocation.operator.display_name
        == "Operador Sandbox"
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
        )


def test_authorized_invocation_contains_no_operational_authority():
    authorized = (
        authorize_teams_approval_invocation(
            invocation=(
                create_invocation()
            ),

            policy=(
                create_policy()
            ),
        )
    )

    payload = (
        authorized.model_dump(
            mode="json"
        )
    )

    assert set(
        payload
    ) == {
        "policy_id",
        "operator",
        "action",
    }

    serialized = str(
        payload
    )

    forbidden = [
        "procedure_id",
        "procedure_version",
        "capability_id",
        "operation_action",
        "operation_domain",
        "operation_kind",
        "target_resource",
        "required_parameters",
        "resolved_parameters",
        "subscription_id",
        "resource_group",
        "vm_name",
        "request_id",
        "checkpoint_id",
    ]

    for field in forbidden:
        assert (
            field
            not in serialized
        )


def test_empty_allowlist_is_rejected():
    with pytest.raises(
        ValidationError,
        match="al menos un principal",
    ):
        ExactTeamsApprovalPolicy(
            policy_id=(
                POLICY_ID
            ),

            allowed_principals=(),
        )


def test_duplicate_principal_is_rejected():
    principal = (
        TeamsApprovalPrincipal(
            tenant_id=(
                TENANT_ID
            ),

            aad_object_id=(
                AAD_OBJECT_ID
            ),
        )
    )

    with pytest.raises(
        ValidationError,
        match="duplicados",
    ):
        ExactTeamsApprovalPolicy(
            policy_id=(
                POLICY_ID
            ),

            allowed_principals=(
                principal,
                principal,
            ),
        )


def test_authorized_invocation_is_immutable():
    authorized = (
        authorize_teams_approval_invocation(
            invocation=(
                create_invocation()
            ),

            policy=(
                create_policy()
            ),
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        authorized.policy_id = (
            "attacker-policy"
        )