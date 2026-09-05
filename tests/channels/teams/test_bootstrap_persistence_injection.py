from __future__ import annotations

import ast
import inspect
import textwrap

from dataclasses import fields
from pathlib import Path


from src.channels.teams import (
    bootstrap as teams_bootstrap,
)


EXPECTED_PERSISTENCE_FIELDS = (
    "store",
    "checkpoint_storage",
    "operation_dispatch_ledger",
    "wait_recheck_consumption_ledger",
    "continuation_store",
    "conversation_store",
)


class FakeConversationStore:
    def upsert(
        self,
        binding,
    ) -> None:
        raise AssertionError(
            "No debe usarse durante bootstrap."
        )

    def get_exact(
        self,
        *,
        tenant_id,
        conversation_id,
    ):
        raise AssertionError(
            "No debe usarse durante bootstrap."
        )


def _settings(
    tmp_path: Path,
):
    return teams_bootstrap.TeamsHitlSettings(
        client_id=(
            "aaaaaaaa-aaaa-4aaa-"
            "8aaa-aaaaaaaaaaaa"
        ),
        client_secret=(
            "sandbox-test-secret"
        ),
        bot_tenant_id=(
            "0cb40b2b-6cfc-4c63-"
            "bf7b-da710ea390cb"
        ),
        teams_channel_tenant_id=(
            "3048dc87-43f0-4100-"
            "9acb-ae1971c79395"
        ),
        approver_aad_object_id=(
            "69916319-588a-42a9-"
            "9109-b57c6d1c7501"
        ),
        pending_database_path=(
            tmp_path
            / "must-not-create-pending.db"
        ),
        checkpoint_path=(
            tmp_path
            / "must-not-create-checkpoints"
        ),
        operation_dispatch_database_path=(
            tmp_path
            / "must-not-create-dispatch.db"
        ),
        conversation_binding_database_path=(
            tmp_path
            / "must-not-create-conversation.db"
        ),
    )


def test_teams_hitl_persistence_bundle_exists_with_exact_fields():
    persistence_type = getattr(
        teams_bootstrap,
        "TeamsHitlPersistence",
        None,
    )

    assert persistence_type is not None

    actual_fields = tuple(
        field.name
        for field in fields(
            persistence_type
        )
    )

    assert (
        actual_fields
        == EXPECTED_PERSISTENCE_FIELDS
    )


def test_build_teams_hitl_app_accepts_keyword_only_persistence():
    signature = inspect.signature(
        teams_bootstrap
        .build_teams_hitl_app
    )

    assert (
        "persistence"
        in signature.parameters
    )

    persistence_parameter = (
        signature.parameters[
            "persistence"
        ]
    )

    assert (
        persistence_parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_build_teams_hitl_app_does_not_construct_local_persistence_directly():
    source = textwrap.dedent(
        inspect.getsource(
            teams_bootstrap
            .build_teams_hitl_app
        )
    )

    tree = ast.parse(
        source
    )

    called_names = set()

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        function = node.func

        if isinstance(
            function,
            ast.Name,
        ):
            called_names.add(
                function.id
            )

        elif isinstance(
            function,
            ast.Attribute,
        ):
            called_names.add(
                function.attr
            )

    forbidden_calls = {
        "SqlitePendingApprovalStore",
        "SqliteOperationDispatchLedger",
        "SqliteWaitRecheckConsumptionLedger",
        "SqliteIncidentContinuationStore",
        "SqliteTeamsConversationBindingStore",
        "build_incident_checkpoint_storage",
    }

    assert forbidden_calls.isdisjoint(
        called_names
    )


def test_local_persistence_factory_exists():
    factory = getattr(
        teams_bootstrap,
        "build_local_teams_hitl_persistence",
        None,
    )

    assert callable(
        factory
    )

    signature = inspect.signature(
        factory
    )

    assert (
        tuple(
            signature.parameters
        )
        == (
            "settings",
        )
    )


def test_injected_persistence_is_used_exactly_without_local_store_creation(
    monkeypatch,
    tmp_path,
):
    persistence_type = getattr(
        teams_bootstrap,
        "TeamsHitlPersistence",
        None,
    )

    assert persistence_type is not None

    pending_store = object()
    checkpoint_storage = object()
    operation_dispatch_ledger = object()
    wait_recheck_consumption_ledger = object()
    continuation_store = object()
    conversation_store = (
        FakeConversationStore()
    )

    persistence = persistence_type(
        store=pending_store,
        checkpoint_storage=(
            checkpoint_storage
        ),
        operation_dispatch_ledger=(
            operation_dispatch_ledger
        ),
        wait_recheck_consumption_ledger=(
            wait_recheck_consumption_ledger
        ),
        continuation_store=(
            continuation_store
        ),
        conversation_store=(
            conversation_store
        ),
    )

    def forbidden_local_constructor(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "No debe construirse persistencia "
            "local cuando persistence se inyecta."
        )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqlitePendingApprovalStore",
        forbidden_local_constructor,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqliteOperationDispatchLedger",
        forbidden_local_constructor,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqliteWaitRecheckConsumptionLedger",
        forbidden_local_constructor,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqliteIncidentContinuationStore",
        forbidden_local_constructor,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqliteTeamsConversationBindingStore",
        forbidden_local_constructor,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "build_incident_checkpoint_storage",
        forbidden_local_constructor,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "register_teams_approval_handler",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "register_teams_conversation_handler",
        lambda **kwargs: None,
    )

    bootstrap = (
        teams_bootstrap
        .build_teams_hitl_app(
            _settings(
                tmp_path
            ),
            persistence=persistence,
        )
    )

    assert (
        bootstrap.store
        is pending_store
    )

    assert (
        bootstrap.checkpoint_storage
        is checkpoint_storage
    )

    assert (
        bootstrap.operation_dispatch_ledger
        is operation_dispatch_ledger
    )

    assert (
        bootstrap.wait_recheck_consumption_ledger
        is wait_recheck_consumption_ledger
    )

    assert (
        bootstrap.continuation_store
        is continuation_store
    )

    assert (
        bootstrap.conversation_store
        is conversation_store
    )

    assert (
        bootstrap.dependencies.store
        is pending_store
    )

    assert (
        bootstrap.dependencies
        .continuation_store
        is continuation_store
    )

    assert (
        bootstrap.conversation_dependencies
        .store
        is conversation_store
    )

    assert (
        bootstrap.outbound.store
        is conversation_store
    )

    assert list(
        tmp_path.iterdir()
    ) == []