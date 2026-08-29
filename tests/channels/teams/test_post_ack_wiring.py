from __future__ import annotations

import ast

from pathlib import Path


def test_bootstrap_wires_fast_handler_and_worker():
    text = Path(
        "src/channels/teams/bootstrap.py"
    ).read_text(
        encoding="utf-8"
    )

    required = (
        "incident_approval_handoff_handler",
        "SqliteIncidentContinuationStore",
        "IncidentContinuationWorker",
        "notify_teams_incident_terminal_result",
        "continuation_store=(",
        "continuation_worker=(",
    )

    for token in required:
        assert token in text


def test_main_runs_server_and_worker_together():
    text = Path(
        "src/channels/teams/main.py"
    ).read_text(
        encoding="utf-8"
    )

    ast.parse(text)

    assert "asyncio.TaskGroup()" in text

    assert (
        "bootstrap.continuation_worker.run"
        in text
    )

    assert "bootstrap.app.start()" in text
    assert "stop_event.set()" in text


def test_registered_fast_handler_has_no_external_execution():
    text = Path(
        "src/channels/teams/"
        "incident_approval_handoff_handler.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "workflow.run(",
        "compute_vm_power-state",
        "azure.vm.start",
        "subscription_id",
        "resource_group",
    )

    for token in forbidden:
        assert token not in text