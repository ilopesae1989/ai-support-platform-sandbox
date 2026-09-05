from pathlib import Path

import pytest

import src.channels.teams.bootstrap as teams_bootstrap

from src.channels.teams.approval_processor import (
    process_authorized_teams_approval,
)

from src.channels.teams.bootstrap import (
    TeamsHitlSettings,
)


def create_settings(tmp_path):
    return TeamsHitlSettings(
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret="test-secret",
        bot_tenant_id="22222222-2222-2222-2222-222222222222",
        teams_channel_tenant_id="33333333-3333-3333-3333-333333333333",
        approver_aad_object_id="44444444-4444-4444-4444-444444444444",
        pending_database_path=tmp_path / "pending.db",
        checkpoint_path=tmp_path / "checkpoints",
        operation_dispatch_database_path=(
            tmp_path / "operation-dispatch.db"
        ),
        conversation_binding_database_path=(
            tmp_path / "conversation-bindings.db"
        ),
    )


def install_future_component_fakes(*, monkeypatch):
    checkpoint_storage = object()
    dispatch_ledger = object()
    wait_recheck_ledger = object()
    incident_workflow = object()
    processor_result = object()

    calls = {
        "checkpoint_paths": [],
        "ledger_paths": [],
        "wait_ledger_paths": [],
        "incident_ledgers": [],
        "incident_wait_ledgers": [],
        "incident_readers": [],
        "incident_processor": [],
        "legacy_workflow": [],
    }

    def fake_checkpoint_builder(checkpoint_path):
        calls["checkpoint_paths"].append(Path(checkpoint_path))
        return checkpoint_storage

    def fake_ledger_builder(database_path):
        calls["ledger_paths"].append(Path(database_path))
        return dispatch_ledger

    def fake_wait_ledger_builder(database_path):
        calls["wait_ledger_paths"].append(
            Path(database_path)
        )
        return wait_recheck_ledger

    def fake_incident_workflow_builder(
        *,
        operation_dispatch_ledger,
        wait_recheck_consumption_ledger,
        azure_vm_power_state_reader,
    ):
        calls["incident_ledgers"].append(
            operation_dispatch_ledger
        )

        calls["incident_wait_ledgers"].append(
            wait_recheck_consumption_ledger
        )

        calls["incident_readers"].append(
            azure_vm_power_state_reader
        )

        return incident_workflow

    async def fake_incident_processor(
        *,
        invocation,
        store,
        workflow,
        checkpoint_storage,
    ):
        calls["incident_processor"].append(
            {
                "invocation": invocation,
                "store": store,
                "workflow": workflow,
                "checkpoint_storage": checkpoint_storage,
            }
        )
        return processor_result

    def fake_legacy_workflow_builder(checkpoint_path):
        calls["legacy_workflow"].append(checkpoint_path)
        return object()

    monkeypatch.setattr(
        teams_bootstrap,
        "build_incident_checkpoint_storage",
        fake_checkpoint_builder,
        raising=False,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqliteOperationDispatchLedger",
        fake_ledger_builder,
        raising=False,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "SqliteWaitRecheckConsumptionLedger",
        fake_wait_ledger_builder,
        raising=False,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "build_incident_resolution_workflow",
        fake_incident_workflow_builder,
        raising=False,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "process_authorized_teams_incident_approval",
        fake_incident_processor,
        raising=False,
    )

    monkeypatch.setattr(
        teams_bootstrap,
        "build_procedure_approval_workflow",
        fake_legacy_workflow_builder,
    )

    return {
        "checkpoint_storage": checkpoint_storage,
        "dispatch_ledger": dispatch_ledger,
        "wait_recheck_ledger": wait_recheck_ledger,
        "incident_workflow": incident_workflow,
        "processor_result": processor_result,
        "calls": calls,
    }


def test_bootstrap_builds_durable_incident_authorities(
    monkeypatch,
    tmp_path,
):
    fakes = install_future_component_fakes(
        monkeypatch=monkeypatch,
    )

    settings = create_settings(tmp_path)

    teams_bootstrap.build_teams_hitl_app(settings)

    assert fakes["calls"]["checkpoint_paths"] == [
        settings.checkpoint_path
    ]

    assert fakes["calls"]["ledger_paths"] == [
        settings.operation_dispatch_database_path
    ]

    assert fakes["calls"]["wait_ledger_paths"] == [
        (
            settings.pending_database_path.parent
            / "wait-recheck-consumption.db"
        )
    ]


def test_workflow_factory_builds_full_incident_workflow_with_durable_ledger(
    monkeypatch,
    tmp_path,
):
    fakes = install_future_component_fakes(
        monkeypatch=monkeypatch,
    )

    reader = object()

    bootstrap = teams_bootstrap.build_teams_hitl_app(
        create_settings(tmp_path),
        azure_vm_power_state_reader=reader,
    )

    workflow = bootstrap.dependencies.workflow_factory()

    assert workflow is fakes["incident_workflow"]

    assert fakes["calls"]["incident_ledgers"] == [
        fakes["dispatch_ledger"]
    ]

    assert fakes["calls"]["incident_wait_ledgers"] == [
        fakes["wait_recheck_ledger"]
    ]

    assert fakes["calls"]["incident_readers"] == [
        reader
    ]

    assert fakes["calls"]["legacy_workflow"] == []


@pytest.mark.asyncio
async def test_processor_closure_injects_same_checkpoint_storage(
    monkeypatch,
    tmp_path,
):
    fakes = install_future_component_fakes(
        monkeypatch=monkeypatch,
    )

    bootstrap = teams_bootstrap.build_teams_hitl_app(
        create_settings(tmp_path)
    )

    assert (
        bootstrap.dependencies.processor
        is not process_authorized_teams_approval
    )

    invocation = object()
    store = object()
    workflow = object()

    result = await bootstrap.dependencies.processor(
        invocation=invocation,
        store=store,
        workflow=workflow,
    )

    assert result is fakes["processor_result"]

    assert fakes["calls"]["incident_processor"] == [
        {
            "invocation": invocation,
            "store": store,
            "workflow": workflow,
            "checkpoint_storage": fakes["checkpoint_storage"],
        }
    ]


def test_bootstrap_exposes_durable_incident_components(
    monkeypatch,
    tmp_path,
):
    fakes = install_future_component_fakes(
        monkeypatch=monkeypatch,
    )

    bootstrap = teams_bootstrap.build_teams_hitl_app(
        create_settings(tmp_path)
    )

    assert (
        bootstrap.checkpoint_storage
        is fakes["checkpoint_storage"]
    )

    assert (
        bootstrap.operation_dispatch_ledger
        is fakes["dispatch_ledger"]
    )

    assert (
        bootstrap.wait_recheck_consumption_ledger
        is fakes["wait_recheck_ledger"]
    )
