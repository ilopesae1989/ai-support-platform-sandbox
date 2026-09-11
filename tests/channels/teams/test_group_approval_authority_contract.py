from __future__ import annotations

import inspect

from dataclasses import fields
from pathlib import Path

import pytest

from pydantic import ValidationError

from src.channels.teams import (
    approval_authorization as authorization,
)

from src.channels.teams import (
    bootstrap as bootstrap_module,
)

from src.channels.teams.approval_invocation import (
    build_teams_approval_invocation,
)

from src.channels.teams.production_settings import (
    TeamsProductionHostConfigurationError,
    build_production_teams_host_settings,
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

OTHER_GROUP_OBJECT_ID = (
    "66666666-6666-4666-"
    "8666-666666666666"
)

OTHER_TENANT_ID = (
    "aaaaaaaa-aaaa-4aaa-"
    "8aaa-aaaaaaaaaaaa"
)


class MembershipCheckerStub:
    def __init__(
        self,
        *,
        result: bool = True,
        error: Exception | None = None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    async def is_transitive_member(
        self,
        *,
        user_object_id: str,
        group_object_id: str,
    ) -> bool:
        self.calls.append(
            {
                "user_object_id": user_object_id,
                "group_object_id": group_object_id,
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


def _require_group_contract():
    policy_cls = (
        authorization.ExactTeamsApprovalPolicy
    )

    assert set(
        policy_cls.model_fields
    ) == {
        "policy_id",
        "tenant_id",
        "authorized_technicians_group_object_id",
    }

    assert not hasattr(
        authorization,
        "TeamsApprovalPrincipal",
    )

    function = (
        authorization
        .authorize_teams_approval_invocation
    )

    assert inspect.iscoroutinefunction(
        function
    )

    assert tuple(
        inspect.signature(
            function
        ).parameters
    ) == (
        "invocation",
        "policy",
        "membership_checker",
    )

    return (
        policy_cls,
        function,
    )


def _policy():
    policy_cls, _function = (
        _require_group_contract()
    )

    return policy_cls(
        policy_id=POLICY_ID,
        tenant_id=TENANT_ID,
        authorized_technicians_group_object_id=(
            AUTHORIZED_GROUP_OBJECT_ID
        ),
    )


def _invocation(
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

    return (
        build_teams_approval_invocation(
            activity
        )
    )


def _production_environment():
    return {
        "CLIENT_ID": (
            "11111111-1111-4111-"
            "8111-111111111111"
        ),
        "MANAGED_IDENTITY_CLIENT_ID": (
            "22222222-2222-4222-"
            "8222-222222222222"
        ),
        "TENANT_ID": TENANT_ID,
        "TEAMS_CHANNEL_TENANT_ID": TENANT_ID,
        (
            "TEAMS_AUTHORIZED_TECHNICIANS_"
            "GROUP_OBJECT_ID"
        ): AUTHORIZED_GROUP_OBJECT_ID,
        "AZURE_SQL_SERVER": (
            "sql.example.database.windows.net"
        ),
        "AZURE_SQL_DATABASE": (
            "ai-support-platform"
        ),
    }


def test_policy_is_group_authority_not_individual_allowlist():
    policy_cls, _function = (
        _require_group_contract()
    )

    assert (
        "allowed_principals"
        not in policy_cls.model_fields
    )


def test_group_policy_rejects_noncanonical_group_object_id():
    policy_cls, _function = (
        _require_group_contract()
    )

    with pytest.raises(
        ValidationError,
    ):
        policy_cls(
            policy_id=POLICY_ID,
            tenant_id=TENANT_ID,
            authorized_technicians_group_object_id=(
                "not-a-guid"
            ),
        )


@pytest.mark.asyncio
async def test_transitive_group_member_is_authorized():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        result=True
    )

    authorized = await function(
        invocation=_invocation(),
        policy=_policy(),
        membership_checker=checker,
    )

    assert isinstance(
        authorized,
        authorization.AuthorizedTeamsApprovalInvocation,
    )

    assert (
        authorized.policy_id
        == POLICY_ID
    )

    assert (
        authorized.operator.aad_object_id
        == AAD_OBJECT_ID
    )

    assert checker.calls == [
        {
            "user_object_id": (
                AAD_OBJECT_ID
            ),
            "group_object_id": (
                AUTHORIZED_GROUP_OBJECT_ID
            ),
        }
    ]


@pytest.mark.asyncio
async def test_non_member_is_rejected():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        result=False
    )

    with pytest.raises(
        authorization.TeamsApprovalAuthorizationError,
    ):
        await function(
            invocation=_invocation(),
            policy=_policy(),
            membership_checker=checker,
        )


@pytest.mark.asyncio
async def test_membership_backend_failure_fails_closed():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        error=RuntimeError(
            "graph unavailable"
        )
    )

    with pytest.raises(
        authorization.TeamsApprovalAuthorizationError,
    ):
        await function(
            invocation=_invocation(),
            policy=_policy(),
            membership_checker=checker,
        )


@pytest.mark.asyncio
async def test_membership_timeout_fails_closed():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        error=TimeoutError(
            "graph timeout"
        )
    )

    with pytest.raises(
        authorization.TeamsApprovalAuthorizationError,
    ):
        await function(
            invocation=_invocation(),
            policy=_policy(),
            membership_checker=checker,
        )


@pytest.mark.asyncio
async def test_wrong_tenant_is_rejected_before_graph_membership_call():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        result=True
    )

    with pytest.raises(
        authorization.TeamsApprovalAuthorizationError,
    ):
        await function(
            invocation=_invocation(
                tenant_id=OTHER_TENANT_ID
            ),
            policy=_policy(),
            membership_checker=checker,
        )

    assert checker.calls == []


@pytest.mark.asyncio
async def test_group_authorization_uses_aad_object_id_not_display_name():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        result=True
    )

    invocation = _invocation()

    assert (
        invocation.operator.display_name
        == "Operador Sandbox"
    )

    await function(
        invocation=invocation,
        policy=_policy(),
        membership_checker=checker,
    )

    serialized_calls = str(
        checker.calls
    )

    assert (
        invocation.operator.display_name
        not in serialized_calls
    )

    assert (
        invocation.operator.teams_user_id
        not in serialized_calls
    )


@pytest.mark.asyncio
async def test_authorized_invocation_surface_remains_non_operational():
    _policy_cls, function = (
        _require_group_contract()
    )

    checker = MembershipCheckerStub(
        result=True
    )

    authorized = await function(
        invocation=_invocation(),
        policy=_policy(),
        membership_checker=checker,
    )

    payload = authorized.model_dump(
        mode="json"
    )

    assert set(payload) == {
        "policy_id",
        "operator",
        "action",
    }

    forbidden = (
        "group_object_id",
        "capability_id",
        "target_resource",
        "subscription_id",
        "resource_group",
        "vm_name",
        "operation_action",
        "resolved_parameters",
    )

    serialized = str(payload)

    for fragment in forbidden:
        assert fragment not in serialized


def test_production_settings_require_authorized_technicians_group():
    settings = (
        build_production_teams_host_settings(
            _production_environment()
        )
    )

    app_settings = (
        settings.app_settings
    )

    assert (
        app_settings
        .authorized_technicians_group_object_id
        == AUTHORIZED_GROUP_OBJECT_ID
    )

    assert not hasattr(
        app_settings,
        "approver_aad_object_id",
    )


def test_deprecated_individual_env_does_not_satisfy_new_contract():
    environment = (
        _production_environment()
    )

    environment.pop(
        "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID"
    )

    environment[
        "TEAMS_HITL_APPROVER_AAD_OBJECT_ID"
    ] = (
        "77777777-7777-4777-"
        "8777-777777777777"
    )

    with pytest.raises(
        TeamsProductionHostConfigurationError,
        match=(
            "TEAMS_AUTHORIZED_TECHNICIANS_"
            "GROUP_OBJECT_ID"
        ),
    ):
        build_production_teams_host_settings(
            environment
        )


def test_all_teams_settings_replace_individual_approver_field():
    for cls in (
        bootstrap_module.TeamsHitlAppSettings,
        bootstrap_module.TeamsManagedIdentityAppSettings,
        bootstrap_module.TeamsHitlSettings,
    ):
        names = {
            field.name
            for field in fields(cls)
        }

        assert (
            "authorized_technicians_group_object_id"
            in names
        )

        assert (
            "approver_aad_object_id"
            not in names
        )


def test_deprecated_individual_env_name_is_absent_from_python_runtime():
    paths = (
        Path(
            "src/channels/teams/bootstrap.py"
        ),
        Path(
            "src/channels/teams/production_settings.py"
        ),
    )

    for path in paths:
        text = path.read_text(
            encoding="utf-8"
        )

        assert (
            "TEAMS_HITL_APPROVER_AAD_OBJECT_ID"
            not in text
        )