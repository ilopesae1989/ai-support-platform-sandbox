"""DB-API SQL contract with a scripted cursor. Server qualification remains separate."""
import json
import re

import pytest

from src.persistence.execution_inventory import azure_sql_inventory_page, azure_sql_store_residuals
from tests.runtime.test_incident_execution_queue import affinity


class Connection:
    def __init__(self, replies, *, autocommit=False):
        self.autocommit = autocommit
        self.replies = iter(replies)
        self.statements = []
        self.cursors = []
        self.closed = False
        self.rollbacks = 0

    def cursor(self):
        cursor = Cursor(self)
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed = True

    def rollback(self):
        self.rollbacks += 1


class Cursor:
    def __init__(self, db):
        self.db = db
        self.closed = False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        assert sql.startswith("SELECT ") or sql == "SET TRANSACTION ISOLATION LEVEL SNAPSHOT"
        assert set(re.findall(r"%\((\w+)\)s", sql)) == set(params or {})
        self.db.statements.append((sql, params))
        fragment, result = next(self.db.replies)
        assert fragment in sql
        if isinstance(result, Exception):
            raise result
        self.result = list(result)

    def fetchmany(self, count):
        assert count == 64
        result, self.result = self.result[:count], self.result[count:]
        return result

    def close(self):
        self.closed = True


def record(scope=None):
    a = scope or affinity()
    return ("wf-one", "e"*64, a.fingerprint, json.dumps(a.to_document()))


def test_sql_inventory_scopes_before_limit_binds_ids_and_reconciles_checkpoint_ancestry():
    a = affinity()
    state = {"incident_execution_id": "wf-one", "incident_execution_affinity": a.to_document(),
             "procedure_runtime_state": {"workflow_id": "wf-one", "workflow_status": "waiting_human"}}
    checkpoint = dict(workflow_name="incident-resolution", version="1.0", checkpoint_id="cp-one",
                      previous_checkpoint_id="entry", graph_signature_hash="a"*64, state=state,
                      messages={}, pending_request_info_events={"req-one": {"__pickled__": "opaque"}})
    root = {**checkpoint, "checkpoint_id": "entry", "previous_checkpoint_id": None,
            "pending_request_info_events": {}, "state": {},
            "messages": {f"internal:classification-affinity-{a.fingerprint}-admitted-v1": []}}
    db = Connection([("SET TRANSACTION", []), ("SELECT TOP (3)", [record()]),
                     ("FROM dbo.pending_approvals", [("apr-one", "wf-one", "req-one", "cp-one", "pending")]),
                     ("FROM dbo.incident_affine_continuation_jobs", []),
                     ("FROM dbo.incident_continuation_jobs", [("apr-one", "claimed")]),
                     ("JSON_VALUE(payload_json", [("cp-one", json.dumps(checkpoint))]),
                     ("checkpoint_id = %(parent)s", [(json.dumps(root),)])])
    page = azure_sql_inventory_page(connection_factory=lambda: db, consumer=a, limit=2)
    execution, = page["executions"]
    assert execution["observed_state"] == "hitl_checkpoint" and execution["legacy_jobs"] == {"claimed": 1}
    assert page["legacy_queue"] == "correlated" and "opaque" not in json.dumps(page)
    sql, params = db.statements[1]
    assert "ORDER BY execution_id" in sql and "COLLATE Latin1_General_100_BIN2" in sql
    assert params == {"installation": a.installation_id, "after": ""}
    assert db.rollbacks == 1 and db.closed and all(c.closed for c in db.cursors)


@pytest.mark.parametrize("failure", ["snapshot", "admission", "corruption"])
def test_sql_faults_rollback_and_close_without_returning_partial_evidence(failure):
    replies = [("SET TRANSACTION", RuntimeError() if failure == "snapshot" else [])]
    if failure == "admission":
        replies.append(("SELECT TOP", RuntimeError()))
    if failure == "corruption":
        replies.append(("SELECT TOP", [("wf-one", "e"*64, "f"*64, record()[-1])]))
    db = Connection(replies)
    with pytest.raises((RuntimeError, ValueError)):
        azure_sql_inventory_page(connection_factory=lambda: db, consumer=affinity())
    assert db.closed and db.rollbacks == 1 and all(c.closed for c in db.cursors)


def test_sql_requires_transactional_connection():
    db = Connection([], autocommit=True)
    with pytest.raises(ValueError, match="autocommit"):
        azure_sql_inventory_page(connection_factory=lambda: db, consumer=affinity())
    assert db.closed and db.statements == []


def test_sql_historical_counts_are_store_wide_and_paginate_checkpoint_rows():
    doc = json.dumps({"workflow_name": "incident-resolution", "version": "1.0",
                      "state": {}, "previous_checkpoint_id": "prior"})
    db = Connection([("SET TRANSACTION", []), ("SELECT TOP (64)", [("last", doc)]),
                     ("SELECT TOP (64)", []), ("FROM dbo.incident_continuation_jobs j", [(1,)]),
                     ("FROM dbo.pending_approvals record", [(2,)]),
                     ("FROM dbo.incident_affine_continuation_jobs record", [(0,)])])
    result = azure_sql_store_residuals(connection_factory=lambda: db)
    assert db.statements[2][1] == {"after": "last"}
    assert result["legacy_jobs_without_attributed_approval"] == 1
    assert result["approvals_without_admission"] == 2 and result["checkpoints"] == {"other_without_execution_id": 1}
    assert db.closed and db.rollbacks == 1 and all(c.closed for c in db.cursors)
