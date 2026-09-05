from __future__ import annotations

import ast
import inspect
import textwrap

from dataclasses import (
    fields,
)

from pathlib import (
    Path,
)

from src.channels.teams import (
    azure_sql_persistence,
    bootstrap as teams_bootstrap,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)

from src.persistence.azure_sql.wait_recheck_consumption_ledger import (
    AzureSqlWaitRecheckConsumptionLedger,
)

from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
    SqliteWaitRecheckConsumptionLedger,
)


EXPECTED_BASE_PERSISTENCE_FIELDS = (
    "store",
    "checkpoint_storage",
    "operation_dispatch_ledger",
    "wait_recheck_consumption_ledger",
    "continuation_store",
    "conversation_store",
)


def _local_settings(
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
            / "pending.db"
        ),
        checkpoint_path=(
            tmp_path
            / "checkpoints"
        ),
        operation_dispatch_database_path=(
            tmp_path
            / "operation-dispatch.db"
        ),
        conversation_binding_database_path=(
            tmp_path
            / "conversation-bindings.db"
        ),
    )


def _azure_sql_settings():
    return AzureSqlManagedIdentitySettings(
        server=(
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        database=(
            "ai_support_platform_sbx"
        ),
    )


def test_base_persistence_bundle_declares_separate_wait_recheck_authority():
    actual = tuple(
        field.name
        for field in fields(
            teams_bootstrap
            .TeamsHitlPersistence
        )
    )

    assert (
        actual
        == EXPECTED_BASE_PERSISTENCE_FIELDS
    )


def test_bootstrap_exposes_wait_recheck_authority_as_separate_dependency():
    field_names = tuple(
        field.name
        for field in fields(
            teams_bootstrap
            .TeamsHitlBootstrap
        )
    )

    assert (
        "wait_recheck_consumption_ledger"
        in field_names
    )

    assert (
        field_names.index(
            "wait_recheck_consumption_ledger"
        )
        != field_names.index(
            "operation_dispatch_ledger"
        )
    )


def test_local_persistence_builds_dedicated_sqlite_wait_recheck_ledger(
    tmp_path,
):
    persistence = (
        teams_bootstrap
        .build_local_teams_hitl_persistence(
            _local_settings(
                tmp_path
            )
        )
    )

    ledger = (
        persistence
        .wait_recheck_consumption_ledger
    )

    assert isinstance(
        ledger,
        SqliteWaitRecheckConsumptionLedger,
    )

    assert (
        ledger._database_path
        == (
            tmp_path
            / "wait-recheck-consumption.db"
        )
    )

    assert (
        ledger
        is not persistence
        .operation_dispatch_ledger
    )


def test_azure_sql_persistence_builds_dedicated_wait_recheck_ledger(
    monkeypatch,
):
    opened = []

    def shared_factory():
        opened.append(
            object()
        )

        raise AssertionError(
            "Composition must not open SQL."
        )

    monkeypatch.setattr(
        azure_sql_persistence,
        "build_mssql_python_connection_factory",
        lambda settings:
            shared_factory,
    )

    persistence = (
        azure_sql_persistence
        .build_azure_sql_teams_hitl_persistence(
            _azure_sql_settings()
        )
    )

    ledger = (
        persistence
        .wait_recheck_consumption_ledger
    )

    assert isinstance(
        ledger,
        AzureSqlWaitRecheckConsumptionLedger,
    )

    assert (
        ledger._connection_factory
        is shared_factory
    )

    assert (
        ledger
        is not persistence
        .operation_dispatch_ledger
    )

    assert opened == []


def test_teams_workflow_factory_propagates_wait_recheck_ledger_exactly():
    source = textwrap.dedent(
        inspect.getsource(
            teams_bootstrap
            .build_teams_hitl_app
        )
    )

    tree = ast.parse(
        source
    )

    workflow_calls = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "build_incident_resolution_workflow"
        ):
            workflow_calls.append(
                node
            )

    assert len(
        workflow_calls
    ) == 1

    keywords = {
        keyword.arg:
            keyword.value
        for keyword
        in workflow_calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        "wait_recheck_consumption_ledger"
        in keywords
    )

    value = keywords[
        "wait_recheck_consumption_ledger"
    ]

    assert isinstance(
        value,
        ast.Name,
    )

    assert (
        value.id
        == "wait_recheck_consumption_ledger"
    )


def test_azure_sql_composition_constructs_wait_ledger_from_same_factory():
    source = textwrap.dedent(
        inspect.getsource(
            azure_sql_persistence
            .build_azure_sql_teams_hitl_persistence
        )
    )

    tree = ast.parse(
        source
    )

    constructors = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "AzureSqlWaitRecheckConsumptionLedger"
        ):
            constructors.append(
                node
            )

    assert len(
        constructors
    ) == 1

    kwargs = {
        keyword.arg:
            keyword.value
        for keyword
        in constructors[0].keywords
        if keyword.arg is not None
    }

    assert set(
        kwargs
    ) == {
        "connection_factory",
    }

    factory_value = kwargs[
        "connection_factory"
    ]

    assert isinstance(
        factory_value,
        ast.Name,
    )

    assert (
        factory_value.id
        == "connection_factory"
    )