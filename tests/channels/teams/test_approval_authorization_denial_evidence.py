from __future__ import annotations

import json
import logging

import pytest

from src.channels.teams.approval_authorization import (
    TeamsApprovalAuthorizationError,
    authorize_teams_approval_invocation,
)

from tests.channels.teams.test_approval_authorization import (
    APPROVAL_ID,
    AUTHORIZED_GROUP_OBJECT_ID,
    CROSS_TENANT_AUTHORIZATION_TENANT_ID,
    CROSS_TENANT_GUEST_OBJECT_ID,
    CROSS_TENANT_HOME_OBJECT_ID,
    CROSS_TENANT_SOURCE_TENANT_ID,
    ExactAuthorizationObjectIdResolver,
    MembershipChecker,
    create_cross_tenant_invocation,
    create_cross_tenant_policy,
)


LOGGER_NAME = (
    "src.channels.teams.approval_authorization"
)

EVENT_NAME = (
    "teams_hitl_authorization_denied_v1"
)


def _resolver():
    return ExactAuthorizationObjectIdResolver(
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


def _structured_denials(
    caplog,
):
    payloads = []

    for record in caplog.records:
        if record.name != LOGGER_NAME:
            continue

        try:
            payload = json.loads(
                record.getMessage()
            )
        except json.JSONDecodeError:
            continue

        if (
            isinstance(
                payload,
                dict,
            )
            and payload.get("event")
            == EVENT_NAME
        ):
            payloads.append(
                payload
            )

    return payloads


@pytest.mark.asyncio
async def test_group_membership_false_emits_exact_per_request_denial_evidence(
    caplog,
):
    checker = MembershipChecker(
        members=()
    )

    with caplog.at_level(
        logging.WARNING,
        logger=LOGGER_NAME,
    ):
        with pytest.raises(
            TeamsApprovalAuthorizationError
        ):
            await authorize_teams_approval_invocation(
                invocation=(
                    create_cross_tenant_invocation()
                ),
                policy=(
                    create_cross_tenant_policy()
                ),
                membership_checker=checker,
                operator_identity_resolver=(
                    _resolver()
                ),
            )

    payloads = _structured_denials(
        caplog
    )

    assert len(payloads) == 1

    assert payloads[0] == {
        "event":
            EVENT_NAME,

        "reason":
            "group_membership_false",

        "approval_id":
            APPROVAL_ID,

        "decision":
            "approve",

        "policy_id":
            "teams-hitl-technicians-group-v1",

        "source_tenant_id":
            CROSS_TENANT_SOURCE_TENANT_ID,

        "source_user_object_id":
            CROSS_TENANT_HOME_OBJECT_ID,

        "authorization_tenant_id":
            CROSS_TENANT_AUTHORIZATION_TENANT_ID,

        "authorization_user_object_id":
            CROSS_TENANT_GUEST_OBJECT_ID,

        "group_object_id":
            AUTHORIZED_GROUP_OBJECT_ID,
    }

    assert checker.calls == [
        (
            CROSS_TENANT_GUEST_OBJECT_ID,
            AUTHORIZED_GROUP_OBJECT_ID,
        )
    ]


@pytest.mark.asyncio
async def test_missing_mapping_does_not_emit_group_membership_false_evidence(
    caplog,
):
    checker = MembershipChecker(
        members=(
            CROSS_TENANT_GUEST_OBJECT_ID,
        )
    )

    resolver = (
        ExactAuthorizationObjectIdResolver(
            mappings=()
        )
    )

    with caplog.at_level(
        logging.WARNING,
        logger=LOGGER_NAME,
    ):
        with pytest.raises(
            TeamsApprovalAuthorizationError
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

    assert _structured_denials(
        caplog
    ) == []

    assert checker.calls == []


class FailingMembershipChecker:
    async def is_transitive_member(
        self,
        *,
        user_object_id,
        group_object_id,
    ):
        raise RuntimeError(
            "synthetic Graph failure"
        )


@pytest.mark.asyncio
async def test_graph_failure_does_not_emit_group_membership_false_evidence(
    caplog,
):
    with caplog.at_level(
        logging.WARNING,
        logger=LOGGER_NAME,
    ):
        with pytest.raises(
            TeamsApprovalAuthorizationError
        ):
            await authorize_teams_approval_invocation(
                invocation=(
                    create_cross_tenant_invocation()
                ),
                policy=(
                    create_cross_tenant_policy()
                ),
                membership_checker=(
                    FailingMembershipChecker()
                ),
                operator_identity_resolver=(
                    _resolver()
                ),
            )

    assert _structured_denials(
        caplog
    ) == []


@pytest.mark.asyncio
async def test_authorized_member_emits_no_denial_evidence(
    caplog,
):
    checker = MembershipChecker(
        members=(
            CROSS_TENANT_GUEST_OBJECT_ID,
        )
    )

    with caplog.at_level(
        logging.WARNING,
        logger=LOGGER_NAME,
    ):
        result = await (
            authorize_teams_approval_invocation(
                invocation=(
                    create_cross_tenant_invocation()
                ),
                policy=(
                    create_cross_tenant_policy()
                ),
                membership_checker=checker,
                operator_identity_resolver=(
                    _resolver()
                ),
            )
        )

    assert result.action.approval_id == APPROVAL_ID

    assert _structured_denials(
        caplog
    ) == []