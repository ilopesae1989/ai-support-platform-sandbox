import pytest

from pydantic import (
    ValidationError,
)

from src.channels.teams.action_parser import (
    TeamsApprovalActionError,
)

from src.channels.teams.activity_identity import (
    TeamsActivityIdentityError,
)

from src.channels.teams.approval_invocation import (
    TeamsApprovalInvocation,
    build_teams_approval_invocation,
)

from src.runtime.procedure.approval_channel import (
    ApprovalDecision,
)

from tests.channels.teams.test_activity_identity import (
    AAD_OBJECT_ID,
    CONVERSATION_ID,
    TENANT_ID,
    TEAMS_USER_ID,
    create_activity,
)


APPROVAL_ID = (
    "apr-11111111-1111-4111-"
    "8111-111111111111"
)


def test_real_activity_builds_clean_approval_invocation():
    activity = (
        create_activity(
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
            }
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    assert (
        invocation.operator.tenant_id
        == TENANT_ID
    )

    assert (
        invocation.operator.aad_object_id
        == AAD_OBJECT_ID
    )

    assert (
        invocation.operator.teams_user_id
        == TEAMS_USER_ID
    )

    assert (
        invocation.operator.conversation_id
        == CONVERSATION_ID
    )

    assert (
        invocation.action.approval_id
        == APPROVAL_ID
    )

    assert (
        invocation.action.decision
        == ApprovalDecision.APPROVE
    )


def test_reject_activity_builds_reject_invocation():
    activity = (
        create_activity(
            action_data={
                "action": (
                    "approval_decision"
                ),

                "approval_id": (
                    APPROVAL_ID
                ),

                "decision": (
                    "reject"
                ),
            }
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    assert (
        invocation.action.decision
        == ApprovalDecision.REJECT
    )


def test_action_payload_cannot_replace_operator_identity():
    activity = (
        create_activity(
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

                "tenant_id": (
                    "attacker-tenant"
                ),

                "aad_object_id": (
                    "attacker-object"
                ),
            }
        )
    )

    # El contrato estricto del Action.Execute
    # rechaza el intento antes de construir
    # la invocación.
    with pytest.raises(
        TeamsApprovalActionError,
    ):
        build_teams_approval_invocation(
            activity
        )


def test_missing_authenticated_operator_identity_blocks_invocation():
    activity = (
        create_activity(
            aad_object_id=None,

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

    with pytest.raises(
        TeamsActivityIdentityError,
        match="aad_object_id",
    ):
        build_teams_approval_invocation(
            activity
        )


def test_invocation_contains_no_operational_authority():
    activity = (
        create_activity(
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
            }
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    payload = (
        invocation.model_dump(
            mode="json"
        )
    )

    assert set(
        payload
    ) == {
        "operator",
        "action",
    }

    assert set(
        payload["action"]
    ) == {
        "approval_id",
        "decision",
    }

    assert set(
        payload["operator"]
    ) == {
        "tenant_id",
        "aad_object_id",
        "teams_user_id",
        "conversation_id",
        "display_name",
    }

    serialized = str(
        payload
    )

    forbidden_values = [
        "procedure_id",
        "procedure_version",
        "capability_id",
        "operation_action",
        "operation_domain",
        "operation_kind",
        "target_resource",
        "resolved_parameters",
        "subscription_id",
        "resource_group",
        "vm_name",
        "request_id",
        "checkpoint_id",
    ]

    for forbidden in forbidden_values:
        assert (
            forbidden
            not in serialized
        )


def test_invocation_is_immutable():
    activity = (
        create_activity(
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
            }
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        invocation.action = (
            invocation.action.model_copy(
                update={
                    "decision": (
                        ApprovalDecision.REJECT
                    )
                }
            )
        )


def test_invocation_rejects_extra_top_level_fields():
    activity = (
        create_activity(
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
            }
        )
    )

    invocation = (
        build_teams_approval_invocation(
            activity
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        TeamsApprovalInvocation(
            operator=(
                invocation.operator
            ),

            action=(
                invocation.action
            ),

            capability_id=(
                "azure.vm.delete"
            ),
        )