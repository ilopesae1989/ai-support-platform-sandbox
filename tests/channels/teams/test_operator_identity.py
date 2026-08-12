import pytest

from pydantic import (
    ValidationError,
)

from src.channels.teams.operator_identity import (
    TeamsOperatorIdentity,
)


TENANT_ID = (
    "0cb40b2b-6cfc-4c63-"
    "bf7b-da710ea390cb"
)

AAD_OBJECT_ID = (
    "11111111-1111-4111-"
    "8111-111111111111"
)

TEAMS_USER_ID = (
    "29:teams-user-001"
)

CONVERSATION_ID = (
    "19:conversation-001@thread.v2"
)


def create_identity(
) -> TeamsOperatorIdentity:
    return TeamsOperatorIdentity(
        tenant_id=(
            TENANT_ID
        ),

        aad_object_id=(
            AAD_OBJECT_ID
        ),

        teams_user_id=(
            TEAMS_USER_ID
        ),

        conversation_id=(
            CONVERSATION_ID
        ),

        display_name=(
            "Operador Sandbox"
        ),
    )


def test_authenticated_teams_identity_is_valid():
    identity = (
        create_identity()
    )

    assert (
        identity.tenant_id
        == TENANT_ID
    )

    assert (
        identity.aad_object_id
        == AAD_OBJECT_ID
    )

    assert (
        identity.teams_user_id
        == TEAMS_USER_ID
    )

    assert (
        identity.conversation_id
        == CONVERSATION_ID
    )


def test_identity_contains_no_operational_authority():
    identity = (
        create_identity()
    )

    payload = (
        identity.model_dump()
    )

    assert set(
        payload
    ) == {
        "tenant_id",
        "aad_object_id",
        "teams_user_id",
        "conversation_id",
        "display_name",
    }

    forbidden = {
        "approval_id",
        "decision",
        "workflow_id",
        "alert_id",
        "procedure_id",
        "procedure_version",
        "step_id",
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
    }

    assert (
        forbidden.isdisjoint(
            payload
        )
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "tenant_id",
        "aad_object_id",
        "teams_user_id",
        "conversation_id",
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        " ",
        " invalid",
        "invalid ",
    ],
)
def test_required_teams_identity_is_strict(
    field_name,
    invalid_value,
):
    payload = {
        "tenant_id": (
            TENANT_ID
        ),

        "aad_object_id": (
            AAD_OBJECT_ID
        ),

        "teams_user_id": (
            TEAMS_USER_ID
        ),

        "conversation_id": (
            CONVERSATION_ID
        ),

        "display_name": (
            "Operador Sandbox"
        ),
    }

    payload[
        field_name
    ] = invalid_value

    with pytest.raises(
        ValidationError,
    ):
        TeamsOperatorIdentity(
            **payload
        )


def test_extra_payload_fields_are_rejected():
    with pytest.raises(
        ValidationError,
    ):
        TeamsOperatorIdentity(
            tenant_id=(
                TENANT_ID
            ),

            aad_object_id=(
                AAD_OBJECT_ID
            ),

            teams_user_id=(
                TEAMS_USER_ID
            ),

            conversation_id=(
                CONVERSATION_ID
            ),

            capability_id=(
                "azure.vm.delete"
            ),
        )


def test_operator_identity_is_immutable():
    identity = (
        create_identity()
    )

    with pytest.raises(
        ValidationError,
    ):
        identity.aad_object_id = (
            "22222222-2222-4222-"
            "8222-222222222222"
        )


def test_blank_display_name_is_not_identity():
    identity = (
        TeamsOperatorIdentity(
            tenant_id=(
                TENANT_ID
            ),

            aad_object_id=(
                AAD_OBJECT_ID
            ),

            teams_user_id=(
                TEAMS_USER_ID
            ),

            conversation_id=(
                CONVERSATION_ID
            ),

            display_name=(
                "   "
            ),
        )
    )

    assert (
        identity.display_name
        is None
    )