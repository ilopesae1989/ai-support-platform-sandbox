from __future__ import annotations

import pytest

from microsoft_teams.apps import (
    App,
)

from src.channels.teams import (
    bootstrap as teams_bootstrap,
)

from src.channels.teams.approval_authorization import (
    ExactTeamsApprovalPolicy,
)

from src.channels.teams.incident_approval_handoff_handler import (
    TeamsApprovalHandlerDependencies,
)

from src.channels.teams.bootstrap import (
    TeamsHitlBootstrap,
    TeamsHitlConfigurationError,
    TeamsHitlSettings,
    build_teams_hitl_app,
)

from src.channels.teams.conversation_binding_store import (
    SqliteTeamsConversationBindingStore,
)

from src.channels.teams.conversation_handler import (
    TeamsConversationHandlerDependencies,
)

from src.runtime.procedure.approval_store import (
    SqlitePendingApprovalStore,
)


BOT_TENANT_ID = (
    "0cb40b2b-6cfc-4c63-"
    "bf7b-da710ea390cb"
)

CHANNEL_TENANT_ID = (
    "3048dc87-43f0-4100-"
    "9acb-ae1971c79395"
)

CLIENT_ID = (
    "aaaaaaaa-aaaa-4aaa-"
    "8aaa-aaaaaaaaaaaa"
)

AUTHORIZED_GROUP_OBJECT_ID = (
    "69916319-588a-42a9-"
    "9109-b57c6d1c7501"
)


class MembershipChecker:
    async def is_transitive_member(
        self,
        *,
        user_object_id,
        group_object_id,
    ):
        return True


def create_membership_checker():
    return MembershipChecker()


def configure_environment(
    *,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "CLIENT_ID",
        CLIENT_ID,
    )

    monkeypatch.setenv(
        "CLIENT_SECRET",
        "sandbox-secret-for-test-only",
    )

    monkeypatch.setenv(
        "TENANT_ID",
        BOT_TENANT_ID,
    )

    monkeypatch.setenv(
        "TEAMS_CHANNEL_TENANT_ID",
        CHANNEL_TENANT_ID,
    )

    monkeypatch.setenv(
        "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID",
        AUTHORIZED_GROUP_OBJECT_ID,
    )

    monkeypatch.setenv(
        "TEAMS_HITL_PENDING_DB",
        str(
            tmp_path
            / "pending-approvals.db"
        ),
    )

    monkeypatch.setenv(
        "TEAMS_HITL_CHECKPOINT_DIR",
        str(
            tmp_path
            / "checkpoints"
        ),
    )

    monkeypatch.setenv(
        "TEAMS_CONVERSATION_BINDING_DB",
        str(
            tmp_path
            / "conversation-bindings.db"
        ),
    )

    monkeypatch.setenv(
        "TEAMS_OPERATION_DISPATCH_DB",
        str(
            tmp_path
            / "operation-dispatch.db"
        ),
    )


def test_settings_are_loaded_from_environment(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    settings = (
        TeamsHitlSettings
        .from_environment()
    )

    assert settings.client_id == CLIENT_ID

    assert (
        settings.bot_tenant_id
        == BOT_TENANT_ID
    )

    assert (
        settings.teams_channel_tenant_id
        == CHANNEL_TENANT_ID
    )

    assert (
        settings.bot_tenant_id
        != settings.teams_channel_tenant_id
    )

    assert (
        settings
        .authorized_technicians_group_object_id
        == AUTHORIZED_GROUP_OBJECT_ID
    )

    assert (
        settings.pending_database_path
        == tmp_path / "pending-approvals.db"
    )

    assert (
        settings.checkpoint_path
        == tmp_path / "checkpoints"
    )

    assert (
        settings.conversation_binding_database_path
        == tmp_path / "conversation-bindings.db"
    )


@pytest.mark.parametrize(
    "missing_variable",
    [
        "CLIENT_ID",
        "CLIENT_SECRET",
        "TENANT_ID",
        "TEAMS_CHANNEL_TENANT_ID",
        "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID",
        "TEAMS_HITL_PENDING_DB",
        "TEAMS_HITL_CHECKPOINT_DIR",
        "TEAMS_CONVERSATION_BINDING_DB",
        "TEAMS_OPERATION_DISPATCH_DB",
    ],
)
def test_missing_required_configuration_fails_closed(
    monkeypatch,
    tmp_path,
    missing_variable,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    monkeypatch.delenv(
        missing_variable
    )

    with pytest.raises(
        TeamsHitlConfigurationError,
        match=missing_variable,
    ):
        TeamsHitlSettings.from_environment()


def test_secret_is_not_exposed_in_settings_repr(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    settings = (
        TeamsHitlSettings
        .from_environment()
    )

    assert (
        "sandbox-secret-for-test-only"
        not in repr(settings)
    )


def test_bootstrap_builds_real_teams_app(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    settings = (
        TeamsHitlSettings
        .from_environment()
    )

    bootstrap = build_teams_hitl_app(
        settings,
        membership_checker=(
            create_membership_checker()
        ),
    )

    assert isinstance(
        bootstrap,
        TeamsHitlBootstrap,
    )

    assert isinstance(
        bootstrap.app,
        App,
    )

    assert isinstance(
        bootstrap.policy,
        ExactTeamsApprovalPolicy,
    )

    assert isinstance(
        bootstrap.store,
        SqlitePendingApprovalStore,
    )

    assert isinstance(
        bootstrap.dependencies,
        TeamsApprovalHandlerDependencies,
    )

    assert (
        bootstrap.dependencies.membership_checker
        is not None
    )

    assert isinstance(
        bootstrap.conversation_store,
        SqliteTeamsConversationBindingStore,
    )

    assert isinstance(
        bootstrap.conversation_dependencies,
        TeamsConversationHandlerDependencies,
    )

    assert (
        bootstrap
        .conversation_dependencies
        .expected_tenant_id
        == CHANNEL_TENANT_ID
    )


def test_bootstrap_governs_exact_tenant_and_group(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    bootstrap = build_teams_hitl_app(
        TeamsHitlSettings.from_environment(),
        membership_checker=(
            create_membership_checker()
        ),
    )

    assert (
        bootstrap.policy.tenant_id
        == CHANNEL_TENANT_ID
    )

    assert (
        bootstrap
        .policy
        .authorized_technicians_group_object_id
        == AUTHORIZED_GROUP_OBJECT_ID
    )


def test_bootstrap_registers_conversation_handler(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    registrations = []

    def fake_register(
        *,
        app,
        dependencies,
    ):
        registrations.append(
            (
                app,
                dependencies,
            )
        )

    monkeypatch.setattr(
        teams_bootstrap,
        "register_teams_conversation_handler",
        fake_register,
    )

    bootstrap = (
        teams_bootstrap
        .build_teams_hitl_app(
            TeamsHitlSettings
            .from_environment(),
            membership_checker=(
                create_membership_checker()
            ),
        )
    )

    assert registrations == [
        (
            bootstrap.app,
            bootstrap.conversation_dependencies,
        )
    ]


def test_bootstrap_contains_no_operational_configuration(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    settings = (
        TeamsHitlSettings
        .from_environment()
    )

    fields = set(
        settings.__dataclass_fields__
    )

    forbidden = {
        "subscription_id",
        "resource_group",
        "vm_name",
        "target_resource",
        "procedure_id",
        "capability_id",
        "operation_action",
        "request_id",
        "checkpoint_id",
    }

    assert forbidden.isdisjoint(
        fields
    )


def test_bot_tenant_and_channel_tenant_are_separate_authorities(
    monkeypatch,
    tmp_path,
):
    configure_environment(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    settings = (
        TeamsHitlSettings
        .from_environment()
    )

    bootstrap = build_teams_hitl_app(
        settings,
        membership_checker=(
            create_membership_checker()
        ),
    )

    assert (
        settings.bot_tenant_id
        == BOT_TENANT_ID
    )

    assert (
        settings.teams_channel_tenant_id
        == CHANNEL_TENANT_ID
    )

    assert (
        bootstrap
        .conversation_dependencies
        .expected_tenant_id
        == CHANNEL_TENANT_ID
    )

    assert (
        bootstrap.policy.tenant_id
        == CHANNEL_TENANT_ID
    )

    assert (
        bootstrap
        .policy
        .authorized_technicians_group_object_id
        == AUTHORIZED_GROUP_OBJECT_ID
    )
