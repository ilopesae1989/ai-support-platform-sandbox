from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from pydantic import BaseModel, ValidationError

from src.channels.teams.approval_authorization import AuthorizedTeamsApprovalInvocation
from src.channels.teams.continuation_payload import TEAMS_CONTINUATION_CODEC
from src.persistence.azure_sql.incident_continuation_store import (
    AzureSqlIncidentContinuationStore, _job_from_row,
)
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.incident_continuation_store import (
    IncidentContinuationConflictError, IncidentContinuationStatus,
)
from src.runtime.procedure.approval_channel import ApprovalChannelAction
from src.runtime.procedure.approval_correlation import PendingApprovalCorrelation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/continuations/teams_before_e3_p2.json"


class LocalAuthorizedInvocation(AuthorizedApprovalInvocation):
    """Synthetic trusted adapter for exercising the core, not a new product channel."""
    principal_id: str


LOCAL_CODEC = ContinuationPayloadCodec(invocation_type=LocalAuthorizedInvocation)


def local_invocation(**changes):
    fields = dict(
        policy_id="local-policy", principal_id="operator-a",
        action=ApprovalChannelAction(approval_id="approval-local", decision="approve"),
    )
    fields.update(changes)
    return LocalAuthorizedInvocation(**fields)


def historical_payload():
    return FIXTURE.read_text(encoding="utf-8").rstrip("\n")


def test_historical_payload_is_byte_compatible_and_keeps_authenticated_identity():
    payload = historical_payload()
    invocation = TEAMS_CONTINUATION_CODEC.decode(payload)
    assert type(invocation) is AuthorizedTeamsApprovalInvocation
    assert invocation.operator.display_name == "Operador Íñigo"
    assert TEAMS_CONTINUATION_CODEC.encode(invocation) == payload
    assert json.loads(payload) == invocation.model_dump(mode="json")


@pytest.mark.parametrize("status,owner,attempts", [
    ("pending", None, 0), ("claimed", "worker-old", 2),
    ("completed", None, 1), ("failed", None, 3),
])
def test_sql_row_reader_preserves_historical_payload_and_lifecycle(status, owner, attempts):
    row = ("approval-fixture-v1", historical_payload(), status, attempts,
           owner, None, 100.0, 101.0)
    job = _job_from_row(row, payload_codec=TEAMS_CONTINUATION_CODEC)
    assert job.invocation.model_dump(mode="json") == json.loads(historical_payload())
    assert job.status.value == status
    assert (job.claimed_by, job.attempt_count) == (owner, attempts)


def test_sqlite_reads_and_deduplicates_payload_written_before_extraction(tmp_path):
    path = tmp_path / "historical.db"
    SqliteIncidentContinuationStore(path, payload_codec=TEAMS_CONTINUATION_CODEC)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO incident_continuation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   ("approval-fixture-v1", historical_payload(), "pending", 0,
                    None, None, 100.0, 100.0))
    restarted = SqliteIncidentContinuationStore(path, payload_codec=TEAMS_CONTINUATION_CODEC)
    invocation = TEAMS_CONTINUATION_CODEC.decode(historical_payload())
    assert restarted.enqueue(invocation).attempt_count == 0
    assert restarted.claim_next(worker_id="worker-new").invocation == invocation
    assert restarted.claim_next(worker_id="other-worker") is None
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT payload_json FROM incident_continuation_jobs").fetchone()[0] == historical_payload()


@pytest.mark.parametrize("change", [
    {"principal_id": "operator-b"}, {"policy_id": "different-policy"},
    {"action": ApprovalChannelAction(approval_id="approval-local", decision="reject")},
], ids=["identity", "policy", "decision"])
def test_alternative_adapter_preserves_conflict_detection(tmp_path, change):
    store = SqliteIncidentContinuationStore(tmp_path / "jobs.db", payload_codec=LOCAL_CODEC)
    original = local_invocation()
    store.enqueue(original)
    with pytest.raises(IncidentContinuationConflictError):
        store.enqueue(local_invocation(**change))
    assert store.get(original.action.approval_id).invocation == original


@pytest.mark.parametrize("bad", [dict, BaseModel, object, None], ids=["dict", "model", "object", "none"])
def test_codec_rejects_unrelated_model_selection(bad):
    with pytest.raises(TypeError):
        ContinuationPayloadCodec(invocation_type=bad)


@pytest.mark.parametrize("backend", ["sql", "sqlite"])
@pytest.mark.parametrize("bad_codec", [None, object()], ids=["none", "object"])
def test_store_requires_selected_codec_before_opening_connection(tmp_path, backend, bad_codec):
    def forbidden_connection():
        pytest.fail("must reject before opening SQL")
    with pytest.raises(TypeError):
        if backend == "sql":
            AzureSqlIncidentContinuationStore(connection_factory=forbidden_connection, payload_codec=bad_codec)
        else:
            SqliteIncidentContinuationStore(tmp_path / "absent.db", payload_codec=bad_codec)
    assert not (tmp_path / "absent.db").exists()


@pytest.mark.parametrize("backend", ["sql", "sqlite"])
@pytest.mark.parametrize("bad_kind", ["dict", "other-channel"])
def test_wrong_payload_type_cannot_enter_selected_store(tmp_path, backend, bad_kind):
    def forbidden_connection():
        pytest.fail("must reject before opening SQL")
    if backend == "sql":
        store = AzureSqlIncidentContinuationStore(connection_factory=forbidden_connection,
                                                  payload_codec=TEAMS_CONTINUATION_CODEC)
    else:
        store = SqliteIncidentContinuationStore(tmp_path / "jobs.db", payload_codec=TEAMS_CONTINUATION_CODEC)
    bad = local_invocation() if bad_kind == "other-channel" else json.loads(historical_payload())
    with pytest.raises(TypeError):
        store.enqueue(bad)


@pytest.mark.parametrize("mutation", ["extra-authority", "type-selector", "missing-identity", "wrong-approval"])
def test_historical_reader_does_not_accept_new_authority_or_broken_identity(mutation):
    payload = json.loads(historical_payload())
    approval_id = "approval-fixture-v1"
    if mutation == "extra-authority":
        payload["action"]["target_resource"] = "vm-untrusted"
    elif mutation == "type-selector":
        payload["invocation_type"] = "some.module:SomeClass"
    elif mutation == "missing-identity":
        del payload["operator"]["aad_object_id"]
    else:
        approval_id = "different-row-approval"
    with pytest.raises(ValidationError):
        _job_from_row((approval_id, json.dumps(payload), "pending", 0, None, None, 1.0, 1.0),
                      payload_codec=TEAMS_CONTINUATION_CODEC)


def test_restarted_core_worker_processes_non_teams_adapter_without_channel_imports(tmp_path):
    path = tmp_path / "jobs.db"
    approvals_path = tmp_path / "approvals.db"
    store = SqliteIncidentContinuationStore(path, payload_codec=LOCAL_CODEC)
    store.enqueue(local_invocation())
    approvals = SqlitePendingApprovalStore(approvals_path)
    approvals.register(PendingApprovalCorrelation(approval_id="approval-local", workflow_id="wf-local",
                                                 request_id="request-local", checkpoint_id="checkpoint-local"))
    code = r'''
import importlib.abc
import sys
class NoChannels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "src.channels" or fullname.startswith(("src.channels.", "microsoft_teams")):
            raise AssertionError("Core imported channel: " + fullname)
sys.meta_path.insert(0, NoChannels())
import asyncio
from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation
from src.runtime.procedure.approval_store import SqlitePendingApprovalStore
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec
from src.runtime.incident_continuation_worker import (
    IncidentContinuationWorker, IncidentContinuationWorkerDependencies, IncidentContinuationWorkerOutcome,
)
from src.persistence.sqlite.incident_continuation_store import SqliteIncidentContinuationStore
from src.persistence.azure_sql.incident_continuation_store import AzureSqlIncidentContinuationStore
class LocalAuthorizedInvocation(AuthorizedApprovalInvocation):
    principal_id: str
codec = ContinuationPayloadCodec(invocation_type=LocalAuthorizedInvocation)
sql = AzureSqlIncidentContinuationStore(connection_factory=lambda: None, payload_codec=codec)
store = SqliteIncidentContinuationStore(sys.argv[1], payload_codec=codec)
approvals = SqlitePendingApprovalStore(sys.argv[2])
events = []
async def processor(*, invocation, store, workflow):
    assert invocation.principal_id == "operator-a"
    assert invocation.policy_id == "local-policy"
    store.claim(approval_id=invocation.action.approval_id, approved=True)
    store.complete(invocation.action.approval_id)
    events.append("processed")
    return "terminal"
async def notifier(*, invocation, processed):
    assert processed == "terminal"
    events.append("notified")
worker = IncidentContinuationWorker(IncidentContinuationWorkerDependencies(
    continuation_store=store, approval_store=approvals, workflow_factory=lambda: object(),
    processor=processor, terminal_notifier=notifier, worker_id="restarted-core",
))
assert asyncio.run(worker.process_next_once()) == IncidentContinuationWorkerOutcome.COMPLETED
assert asyncio.run(worker.process_next_once()) == IncidentContinuationWorkerOutcome.IDLE
assert events == ["processed", "notified"]
'''
    completed = subprocess.run([sys.executable, "-B", "-c", code, str(path), str(approvals_path)],
                               cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    job = store.get("approval-local")
    assert job.status == IncidentContinuationStatus.COMPLETED
    assert job.attempt_count == 1
    assert approvals.get_consumption_record("approval-local") == ("completed", True)
