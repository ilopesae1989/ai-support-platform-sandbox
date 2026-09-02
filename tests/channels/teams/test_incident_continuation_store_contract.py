from __future__ import annotations

import importlib

from pathlib import Path


_REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


def _read_source(
    relative_path: str,
) -> str:
    return (
        _REPO_ROOT
        .joinpath(relative_path)
        .read_text(
            encoding="utf-8"
        )
    )


def test_incident_continuation_store_protocol_exists_and_declares_required_surface():
    module = importlib.import_module(
        "src.channels.teams.incident_continuation_store"
    )

    contract = getattr(
        module,
        "IncidentContinuationStore",
        None,
    )

    assert contract is not None, (
        "Debe existir IncidentContinuationStore "
        "como contrato independiente de SQLite."
    )

    assert getattr(
        contract,
        "_is_protocol",
        False,
    ) is True

    required_methods = (
        "enqueue",
        "get",
        "claim_next",
        "complete",
        "fail",
        "recover_claimed_before_approval",
    )

    missing = [
        method_name
        for method_name in required_methods
        if not callable(
            getattr(
                contract,
                method_name,
                None,
            )
        )
    ]

    assert missing == []


def test_incident_approval_handoff_handler_depends_on_continuation_protocol():
    source = _read_source(
        "src/channels/teams/"
        "incident_approval_handoff_handler.py"
    )

    assert (
        "SqliteIncidentContinuationStore"
        not in source
    )

    assert (
        "IncidentContinuationStore"
        in source
    )


def test_incident_continuation_worker_depends_on_continuation_protocol():
    source = _read_source(
        "src/channels/teams/"
        "incident_continuation_worker.py"
    )

    assert (
        "SqliteIncidentContinuationStore"
        not in source
    )

    assert (
        "IncidentContinuationStore"
        in source
    )