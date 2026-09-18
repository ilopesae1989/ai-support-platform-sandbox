import pytest

from pydantic import (
    ValidationError,
)

from src.channels.teams.approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
    ExactTeamsApprovalPolicy,
    TeamsApprovalAuthorizationError,
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
    "teams-hitl-technicians-group-v1"
)

AUTHORIZED_GROUP_OBJECT_ID = (
    "55555555-5555-4555-"
    "8555-555555555555"
)

OTHER_AAD_OBJECT_ID = (
    "22222222-2222-4222-"
    "8222-222222222222"
)

OTHER_TENANT_ID = (
    "aaaaaaaa-aaaa-4aaa-"
    "8aaa-aaaaaaaaaaaa"
)


class MembershipChecker:
    def __init__(
        self,
        *,
        members=(),
    ):
        self.members = set(
            members
        )

        self.calls = []

    async def is_transitive_member(
        self,
        *,
        user_object_id,
        group_object_id,
    ):
        self.calls.append(
            (
                user_object_id,
                group_object_id,
            )
        )

        return (
            group_object_id
            == AUTHORIZED_GROUP_OBJECT_ID
            and user_object_id
            in self.members
        )


def create_checker(
    *,
    members=(AAD_OBJECT_ID,),
):
    return MembershipChecker(
        members=members
    )


def create_invocation(
    *,
    tenant_id: str = TENANT_ID,
    aad_object_id: str = AAD_OBJECT_ID,
):
    activity = create_activity(
        tenant_id=tenant_id,
        aad_object_id=aad_object_id,
        action_data={
            "action": "approval_decision",
            "approval_id": APPROVAL_ID,
            "decision": "approve",
        },
    )

    return build_teams_approval_invocation(
        activity
    )


def create_policy():
    return ExactTeamsApprovalPolicy(
        policy_id=POLICY_ID,
        tenant_id=TENANT_ID,
        authorized_technicians_group_object_id=(
            AUTHORIZED_GROUP_OBJECT_ID
        ),
    )


@pytest.mark.asyncio
async def test_exact_authenticated_group_member_is_authorized():
    checker = create_checker()

    authorized = await (
        authorize_teams_approval_invocation(
            invocation=create_invocation(),
            policy=create_policy(),
            membership_checker=checker,
        )
    )

    assert isinstance(
        authorized,
        AuthorizedTeamsApprovalInvocation,
    )

    assert authorized.policy_id == POLICY_ID

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

    assert checker.calls == [
        (
            AAD_OBJECT_ID,
            AUTHORIZED_GROUP_OBJECT_ID,
        )
    ]


@pytest.mark.asyncio
async def test_wrong_aad_object_id_is_rejected_when_not_group_member():
    checker = create_checker()

    invocation = create_invocation(
        aad_object_id=(
            OTHER_AAD_OBJECT_ID
        )
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        await authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
            membership_checker=checker,
        )


@pytest.mark.asyncio
async def test_wrong_tenant_is_rejected_before_membership():
    checker = create_checker()

    invocation = create_invocation(
        tenant_id=OTHER_TENANT_ID
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        await authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
            membership_checker=checker,
        )

    assert checker.calls == []


@pytest.mark.asyncio
async def test_same_aad_object_id_in_other_tenant_is_rejected():
    checker = create_checker()

    invocation = create_invocation(
        tenant_id=OTHER_TENANT_ID,
        aad_object_id=AAD_OBJECT_ID,
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        await authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
            membership_checker=checker,
        )

    assert checker.calls == []


@pytest.mark.asyncio
async def test_policy_cannot_authorize_by_display_name():
    checker = create_checker()

    invocation = create_invocation(
        aad_object_id=(
            OTHER_AAD_OBJECT_ID
        )
    )

    assert (
        invocation.operator.display_name
        == "Operador Sandbox"
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        await authorize_teams_approval_invocation(
            invocation=invocation,
            policy=create_policy(),
            membership_checker=checker,
        )


@pytest.mark.asyncio
async def test_authorized_invocation_contains_no_operational_authority():
    authorized = await (
        authorize_teams_approval_invocation(
            invocation=create_invocation(),
            policy=create_policy(),
            membership_checker=create_checker(),
        )
    )

    payload = authorized.model_dump(
        mode="json"
    )

    assert set(payload) == {
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
        assert field not in serialized


def test_empty_group_object_id_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        ExactTeamsApprovalPolicy(
            policy_id=POLICY_ID,
            tenant_id=TENANT_ID,
            authorized_technicians_group_object_id="",
        )


def test_malformed_group_object_id_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        ExactTeamsApprovalPolicy(
            policy_id=POLICY_ID,
            tenant_id=TENANT_ID,
            authorized_technicians_group_object_id=(
                "not-a-guid"
            ),
        )


@pytest.mark.asyncio
async def test_authorized_invocation_is_immutable():
    authorized = await (
        authorize_teams_approval_invocation(
            invocation=create_invocation(),
            policy=create_policy(),
            membership_checker=create_checker(),
        )
    )

    with pytest.raises(
        ValidationError,
    ):
        authorized.policy_id = (
            "attacker-policy"
        )


# CROSS_TENANT_AUTHORIZATION_IDENTITY_RESOLUTION_CONTRACT

CROSS_TENANT_SOURCE_TENANT_ID = (
    "3048dc87-43f0-4100-9acb-ae1971c79395"
)

CROSS_TENANT_AUTHORIZATION_TENANT_ID = (
    "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb"
)

CROSS_TENANT_HOME_OBJECT_ID = (
    "69916319-588a-42a9-9109-b57c6d1c7501"
)

CROSS_TENANT_GUEST_OBJECT_ID = (
    "497a925f-15f1-4583-9d15-29b65590bbcf"
)


class ExactAuthorizationObjectIdResolver:
    def __init__(
        self,
        *,
        mappings=(),
    ):
        self.mappings = dict(
            mappings
        )

        self.calls = []

    async def resolve_authorization_user_object_id(
        self,
        *,
        source_tenant_id,
        source_user_object_id,
        target_tenant_id,
    ):
        key = (
            source_tenant_id,
            source_user_object_id,
            target_tenant_id,
        )

        self.calls.append(
            key
        )

        if key not in self.mappings:
            raise RuntimeError(
                "No existe correlación exacta "
                "de identidad."
            )

        return self.mappings[
            key
        ]


def create_cross_tenant_policy():
    return ExactTeamsApprovalPolicy(
        policy_id=POLICY_ID,
        tenant_id=(
            CROSS_TENANT_SOURCE_TENANT_ID
        ),
        authorization_directory_tenant_id=(
            CROSS_TENANT_AUTHORIZATION_TENANT_ID
        ),
        authorized_technicians_group_object_id=(
            AUTHORIZED_GROUP_OBJECT_ID
        ),
    )


def create_cross_tenant_invocation():
    return create_invocation(
        tenant_id=(
            CROSS_TENANT_SOURCE_TENANT_ID
        ),
        aad_object_id=(
            CROSS_TENANT_HOME_OBJECT_ID
        ),
    )


@pytest.mark.asyncio
async def test_cross_tenant_authorization_identity_resolution_contract_maps_home_object_before_membership():
    checker = MembershipChecker(
        members=(
            CROSS_TENANT_GUEST_OBJECT_ID,
        )
    )

    resolver = ExactAuthorizationObjectIdResolver(
        mappings=(
            (
                (
                    CROSS_TENANT_SOURCE_TENANT_ID,
                    CROSS_TENANT_HOME_OBJECT_ID,
                    CROSS_TENANT_AUTHORIZATION_TENANT_ID,
                ),
                CROSS_TENANT_GUEST_OBJECT_ID,
            ),
        )
    )

    authorized = await (
        authorize_teams_approval_invocation(
            invocation=(
                create_cross_tenant_invocation()
            ),
            policy=(
                create_cross_tenant_policy()
            ),
            membership_checker=checker,
            operator_identity_resolver=resolver,
        )
    )

    assert resolver.calls == [
        (
            CROSS_TENANT_SOURCE_TENANT_ID,
            CROSS_TENANT_HOME_OBJECT_ID,
            CROSS_TENANT_AUTHORIZATION_TENANT_ID,
        )
    ]

    assert checker.calls == [
        (
            CROSS_TENANT_GUEST_OBJECT_ID,
            AUTHORIZED_GROUP_OBJECT_ID,
        )
    ]

    assert (
        authorized.operator.tenant_id
        == CROSS_TENANT_SOURCE_TENANT_ID
    )

    assert (
        authorized.operator.aad_object_id
        == CROSS_TENANT_HOME_OBJECT_ID
    )


@pytest.mark.asyncio
async def test_cross_tenant_authorization_identity_resolution_contract_fails_closed_when_mapping_is_missing():
    checker = MembershipChecker(
        members=(
            CROSS_TENANT_GUEST_OBJECT_ID,
        )
    )

    resolver = ExactAuthorizationObjectIdResolver(
        mappings=()
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        await authorize_teams_approval_invocation(
            invocation=(
                create_cross_tenant_invocation()
            ),
            policy=(
                create_cross_tenant_policy()
            ),
            membership_checker=checker,
            operator_identity_resolver=resolver,
        )

    assert resolver.calls == [
        (
            CROSS_TENANT_SOURCE_TENANT_ID,
            CROSS_TENANT_HOME_OBJECT_ID,
            CROSS_TENANT_AUTHORIZATION_TENANT_ID,
        )
    ]

    assert checker.calls == []


@pytest.mark.asyncio
async def test_cross_tenant_authorization_identity_resolution_contract_rejects_missing_resolver_before_membership():
    checker = MembershipChecker(
        members=(
            CROSS_TENANT_GUEST_OBJECT_ID,
        )
    )

    with pytest.raises(
        TeamsApprovalAuthorizationError,
    ):
        await authorize_teams_approval_invocation(
            invocation=(
                create_cross_tenant_invocation()
            ),
            policy=(
                create_cross_tenant_policy()
            ),
            membership_checker=checker,
        )

    assert checker.calls == []


def test_cross_tenant_authorization_identity_resolution_contract_policy_separates_activity_and_authorization_tenants():
    policy = (
        create_cross_tenant_policy()
    )

    assert (
        policy.tenant_id
        == CROSS_TENANT_SOURCE_TENANT_ID
    )

    assert (
        policy.authorization_directory_tenant_id
        == CROSS_TENANT_AUTHORIZATION_TENANT_ID
    )

    assert (
        policy.tenant_id
        != policy.authorization_directory_tenant_id
    )