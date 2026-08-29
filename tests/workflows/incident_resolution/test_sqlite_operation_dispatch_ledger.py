from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

import src.workflows.incident_resolution.operation_dispatch_ledger as ledger_module


OPERATION_ID = "op-phase18-sqlite-0001"


def build_ledger(database_path):
    return ledger_module.SqliteOperationDispatchLedger(database_path)


def test_claim_persists_and_blocks_replay_across_instances(tmp_path):
    database_path = tmp_path / "operation-dispatch.db"

    ledger_a = build_ledger(database_path)
    ledger_a.claim(OPERATION_ID)

    ledger_b = build_ledger(database_path)

    with pytest.raises(
        ledger_module.OperationAlreadyDispatchedError
    ):
        ledger_b.claim(OPERATION_ID)


def test_distinct_operation_ids_are_independent(tmp_path):
    database_path = tmp_path / "operation-dispatch.db"

    ledger = build_ledger(database_path)

    ledger.claim("op-phase18-A")
    ledger.claim("op-phase18-B")

    with pytest.raises(
        ledger_module.OperationAlreadyDispatchedError
    ):
        ledger.claim("op-phase18-A")

    with pytest.raises(
        ledger_module.OperationAlreadyDispatchedError
    ):
        ledger.claim("op-phase18-B")


def test_two_sqlite_instances_concurrent_claim_exactly_one_wins(tmp_path):
    database_path = tmp_path / "operation-dispatch.db"

    ledger_a = build_ledger(database_path)
    ledger_b = build_ledger(database_path)

    barrier = Barrier(2)

    def attempt(ledger):
        barrier.wait(timeout=10)

        try:
            ledger.claim(OPERATION_ID)
            return "claimed"
        except ledger_module.OperationAlreadyDispatchedError:
            return "replay"

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(attempt, ledger_a)
        future_b = executor.submit(attempt, ledger_b)

        results = [
            future_a.result(timeout=15),
            future_b.result(timeout=15),
        ]

    assert sorted(results) == [
        "claimed",
        "replay",
    ]

    ledger_after_restart = build_ledger(database_path)

    with pytest.raises(
        ledger_module.OperationAlreadyDispatchedError
    ):
        ledger_after_restart.claim(OPERATION_ID)
