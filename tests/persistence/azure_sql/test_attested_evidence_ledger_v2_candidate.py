"""F27-B05-T06: DB-API stub adversarial tests, completely OFFLINE.

No SQL engine, network, Azure, credential, migration or production wiring.
The signature pair is independently covered by existing bridge/store tests.
"""
from __future__ import annotations

from dataclasses import replace
import pytest

from src.persistence.azure_sql import attested_evidence_ledger_v2_candidate as candidate
from src.workflows.incident_resolution.mcp_attested_evidence_store_offline import (
    OfflinePreparedEvidenceV2,
)


class UniqueViolation(Exception):
    pass


class StubDB:
    def __init__(self):
        self.rows = {}
        self.opened = 0
        self.executions = []
        self.fail_insert = None
        self.commit_mode = "success"
        self.fail_read = False
        self.multiple_rows = False
        self.commit_attempts = 0

    def connect(self):
        self.opened += 1
        return StubConnection(self)


class StubConnection:
    def __init__(self, db):
        self.db = db
        self.pending = None
        self.closed = False
        self.rolled_back = False

    def cursor(self):
        return StubCursor(self)

    def commit(self):
        self.db.commit_attempts += 1
        if self.db.commit_mode == "error_before":
            raise ConnectionError("Synthetic uncertain commit")
        if self.pending is not None:
            key, row = self.pending
            self.db.rows[key] = row
            self.pending = None
        if self.db.commit_mode == "error_after":
            raise ConnectionError("Synthetic uncertain commit after record")

    def rollback(self):
        self.rolled_back = True
        self.pending = None

    def close(self):
        self.closed = True


class StubCursor:
    def __init__(self, connection):
        self.connection = connection
        self.fetched = []
        self.closed = False

    def execute(self, sql, params):
        db = self.connection.db
        db.executions.append((sql, dict(params)))
        assert sql.startswith("\nINSERT INTO dbo.attested_evidence_claims") or sql.startswith("\nSELECT subject_sha256")
        assert not any(x in sql.upper() for x in ("UPDATE ", "DELETE ", "MERGE ", "DROP ", "ALTER "))
        key = (params["scope_id"], params["issuer"], params["evidence_domain"], params["logical_sha256"])
        if sql.lstrip().startswith("INSERT"):
            if db.fail_insert is not None:
                raise db.fail_insert
            if key in db.rows:
                raise UniqueViolation("23000 Violation of UNIQUE KEY constraint 'UQ_attested_evidence_logical_v2' (2627)")
            self.connection.pending = (key, candidate._expected_row(params))
        else:
            if db.fail_read:
                raise ConnectionError("synthetic read failure")
            row = db.rows.get(key)
            self.fetched = ([] if row is None else [row, row] if db.multiple_rows else [row])

    def fetchone(self):
        return self.fetched.pop(0) if self.fetched else None

    def close(self):
        self.closed = True


@pytest.fixture
def claim():
    return OfflinePreparedEvidenceV2(
        scope="sandbox/project", issuer="mcp_backend", domain="event:MCP_TOOL_DISPATCH_STARTED",
        operation_id="operation-1", workflow_id="workflow-1", backend_event_id="event-1",
        backend_request_id="request-1", bridge_id="bridge-1", approval_state="PENDING",
        logical_sha256="a" * 64, subject_sha256="b" * 64,
        backend_kid="c" * 64, attestor_kid="d" * 64,
    )


@pytest.fixture
def setup(monkeypatch, claim):
    db = StubDB()
    ledger = candidate.AzureSqlAttestedEvidenceV2OfflineCandidate(connection_factory=db.connect)
    calls = []
    def verified(**kwargs):
        calls.append(kwargs)
        return claim
    monkeypatch.setattr(candidate, "prepare_offline_backend_evidence_v2", verified)
    args = dict(pinned=object(), signed_bridge={}, backend_event={},
                bridge_verifier=object(), backend_verifier=object())
    return db, ledger, args, calls


def test_insert_once_and_binary_digest(setup):
    db, ledger, args, calls = setup
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
    assert db.commit_attempts == 1
    assert db.opened == 1
    assert len(calls) == 1
    sql, params = db.executions[0]
    assert len(params["logical_sha256"]) == 32
    assert isinstance(params["subject_sha256"], bytes)
    assert b"\xaa" * 32 == params["logical_sha256"]
    assert "%(logical_sha256)s" in sql


def test_duplicate_only_after_verified_re_read(setup):
    db, ledger, args, _ = setup
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.DUPLICATE_OFFLINE_NO_AUTHORITY
    assert db.commit_attempts == 1
    assert db.opened == 3


def test_conflicting_payload_same_logical_identity_fail_closed(setup, claim):
    db, ledger, args, _ = setup
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
    key = candidate._read_params(candidate._params(claim))
    k = tuple(key.values())
    db.rows[k] = (b"\xff" * 32, *candidate._expected_row(candidate._params(claim))[1:])
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.CONFLICT_FAIL_CLOSED


def test_different_attestor_key_never_hidden_as_identical_duplicate(setup, claim, monkeypatch):
    db, ledger, args, _ = setup
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
    monkeypatch.setattr(candidate, "prepare_offline_backend_evidence_v2", lambda **kw: replace(claim, attestor_kid="e" * 64))
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.CONFLICT_FAIL_CLOSED


@pytest.mark.parametrize("mode,expected", [
    ("error_before", candidate.CandidateSqlOutcome.COMMIT_OUTCOME_UNKNOWN),
    ("error_after", candidate.CandidateSqlOutcome.COMMIT_OUTCOME_UNKNOWN),
])
def test_commit_ambiguous_never_retried(setup, mode, expected):
    db, ledger, args, _ = setup
    db.commit_mode = mode
    assert ledger.observe_signed(**args) == expected
    assert len([x for x, _ in db.executions if "INSERT INTO" in x]) == 1
    assert db.commit_attempts == 1


def test_reconcile_commit_unknown_present(setup):
    db, ledger, args, _ = setup
    db.commit_mode = "error_after"
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.COMMIT_OUTCOME_UNKNOWN
    assert ledger.reconcile_signed(**args) == candidate.CandidateSqlOutcome.PRESENT_OFFLINE_NO_AUTHORITY
    assert db.commit_attempts == 1


def test_reconcile_commit_unknown_absent_never_auto_retries(setup):
    db, ledger, args, _ = setup
    db.commit_mode = "error_before"
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.COMMIT_OUTCOME_UNKNOWN
    assert ledger.reconcile_signed(**args) == candidate.CandidateSqlOutcome.ABSENT_UNCERTAIN_NO_RETRY
    assert len([x for x, _ in db.executions if "INSERT INTO" in x]) == 1


def test_error_of_other_constraint_is_not_duplicate(setup):
    db, ledger, args, _ = setup
    db.fail_insert = UniqueViolation("23000 CHECK constraint violated (547)")
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY
    assert db.opened == 1


def test_duplicate_number_without_expected_named_constraint_is_not_duplicate(setup):
    db, ledger, args, _ = setup
    db.fail_insert = UniqueViolation("23000 Violation of other constraint (2627)")
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY
    assert db.opened == 1


def test_replay_reconciliation_read_failure_fail_closed(setup):
    db, ledger, args, _ = setup
    db.fail_read = True
    assert ledger.reconcile_signed(**args) == candidate.CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY


def test_multiple_rows_is_schema_corruption_and_conflict(setup, claim):
    db, ledger, args, _ = setup
    db.commit_mode = "success"
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
    db.multiple_rows = True
    assert ledger.reconcile_signed(**args) == candidate.CandidateSqlOutcome.CONFLICT_FAIL_CLOSED


def test_verification_failure_rejects_before_db_open(setup, monkeypatch):
    db, ledger, args, _ = setup
    def invalid(**kwargs):
        raise ValueError("Synthetic invalid signature")
    monkeypatch.setattr(candidate, "prepare_offline_backend_evidence_v2", invalid)
    with pytest.raises(ValueError, match="Synthetic invalid signature"):
        ledger.observe_signed(**args)
    assert db.opened == 0


def test_claim_must_be_reprepared_and_forged_input_not_accepted(setup, claim):
    db, ledger, args, _ = setup
    with pytest.raises(TypeError):
        ledger.observe_signed(claim=claim)  # no raw forged claim accepted
    assert db.opened == 0


def test_only_first_insert_has_side_effects(setup):
    db, ledger, args, _ = setup
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
    assert ledger.observe_signed(**args) == candidate.CandidateSqlOutcome.DUPLICATE_OFFLINE_NO_AUTHORITY
    assert all("operation_dispatch_claims" not in query for query, _ in db.executions)
    assert all("mcp" not in query.lower() or "attested" in query.lower() for query, _ in db.executions)


def test_bad_factory_fails_at_construction():
    with pytest.raises(TypeError):
        candidate.AzureSqlAttestedEvidenceV2OfflineCandidate(connection_factory=None)
