"""Operator diagnostics on a scoped inventory page, using only durable stores."""
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import sqlite3

import pytest

from src.config.foundry_deployment import build_foundry_deployment_configuration
from src.persistence.execution_inventory import azure_sql_inventory_page, sqlite_inventory_page
from src.review.execution_inventory import main
from src.runtime.execution_affinity import AFFINITY_STATE_KEY
from src.runtime.procedure.identity import create_operation_id
from src.runtime.procedure.models import ProcedureRuntimeState
from src.workflows.incident_resolution.operation_dispatch_ledger import SqliteOperationDispatchLedger
from tests.config.test_foundry_deployment import deployment_document, environment
from tests.persistence.azure_sql.test_execution_inventory import Connection, record
from tests.review.test_execution_inventory import document, write_cp
from tests.runtime.test_incident_execution_queue import affinity, prepare, stores


@pytest.fixture
def deployment():
    return build_foundry_deployment_configuration(environment(deployment_document("a")))


def evidence(deployment):
    scope = replace(affinity(), foundry_sha256=deployment.fingerprint)
    parameters = {"subscription_id": "sub", "resource_group": "group", "vm_name": "vm"}
    state = ProcedureRuntimeState(
        workflow_id="wf-one", approval_id="apr-one", alert_id="alert", procedure={"id": "VM", "name": "Start"},
        current_step=1, total_steps=1, step_status="waiting_approval", workflow_status="waiting_human",
        vm_start_binding_fingerprint=deployment.write_binding.fingerprint,
        step={"id": "1", "description": "Start", "step_type": "operation", "operation_domain": "azure",
              "operation_kind": "write", "operation_action": "vm_start", "capability_id": "azure.vm.start",
              "hitl_required": True, "required_parameters": list(parameters),
              "target_resource": "/subscriptions/sub/resourceGroups/group/providers/Microsoft.Compute/virtualMachines/vm"},
        resolved_parameters=[{"name": name, "value": value, "source": "test"} for name, value in parameters.items()])
    cp = document("cp-one", requests={"req-one": None})
    cp["state"].update({AFFINITY_STATE_KEY: scope.to_document(), "procedure_runtime_state": state.model_dump(mode="json")})
    root = document("entry", None, messages={f"internal:classification-affinity-{scope.fingerprint}-admitted-v1": []})
    root["state"] = {}
    op = create_operation_id(workflow_id="wf-one", approval_id="apr-one", alert_id="alert",
                             procedure_id="VM", current_step=1, step_id="1")
    return scope, root, cp, op


@pytest.fixture
def local(tmp_path, deployment):
    scope, root, cp, op = evidence(deployment)
    (tmp_path / "checkpoints").mkdir()
    queue, approvals, db = stores(tmp_path, scope)
    prepare(queue, approvals, decision="approve")
    job = queue.claim_next(worker_id="worker")
    queue.claim_approval(approval_id=job.approval_id, worker_id="worker", expected_attempt_count=1,
                         approval_store=approvals, approved=True)
    SqliteOperationDispatchLedger(db).claim(op)
    write_cp(tmp_path, root)
    write_cp(tmp_path, cp)
    return dict(database=db, checkpoints=tmp_path / "checkpoints", consumer=scope), cp, op, queue


def test_cli_page_exposes_scoped_operation_without_changing_sources(tmp_path, monkeypatch, deployment, local):
    args, cp, op, queue = local
    queue.admit(execution_id="wf-first", input_sha256="f" * 64)
    first = sqlite_inventory_page(**args, vm_start_deployment=deployment, limit=1)
    assert first["executions"][0]["vm_start_dispatch"] == {"status": "no_open_claimed_pair"}
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps(args["consumer"].to_document()), encoding="utf-8")
    report = tmp_path / "page.json"
    for key, value in environment(deployment_document("a")).items():
        monkeypatch.setenv(key, value)
    files = [args["database"], *args["checkpoints"].glob("*.json")]
    before = [file.read_bytes() for file in files]
    flags = ["--database", str(args["database"]), "--checkpoints", str(args["checkpoints"]),
             "--output", str(report), "--after", first["next_after"], "--consumer-affinity", str(scope)]
    main(flags + ["--vm-start-dispatch"])
    row, = json.loads(report.read_bytes())["executions"]
    baseline, = sqlite_inventory_page(**args, after=first["next_after"])["executions"]
    assert row.pop("vm_start_dispatch") == {
        "status": "dispatch_attributed_effect_unconfirmed", "operation_id": op,
        "approval_sha256": hashlib.sha256(b"apr-one").hexdigest(), "procedure_id": "VM", "step_id": "1"}
    assert row == baseline and [file.read_bytes() for file in files] == before
    assert all(value not in report.read_text(encoding="utf-8") for value in ("apr-one", "req-one", "/subscriptions/"))
    other = replace(args["consumer"], release=replace(args["consumer"].release, release_id="next"))
    page = sqlite_inventory_page(**{**args, "consumer": other}, vm_start_deployment=deployment)
    assert all(r["vm_start_dispatch"] == {"status": "out_of_scope"} for r in page["executions"])
    assert not sqlite_inventory_page(**{**args, "consumer": replace(other, installation_id="b")},
                                     vm_start_deployment=deployment)["executions"]


@pytest.mark.parametrize("fault", ["missing_checkpoint", "missing_claim", "historical_schema", "approval",
                                   "step", "binding", "negative_decision", "multiple_claims", "unavailable_receipts"])
def test_incomplete_evidence_does_not_disclose_operation(tmp_path, deployment, local, fault):
    args, cp, op, _ = local
    with closing(sqlite3.connect(args["database"])) as db, db:
        if fault == "missing_checkpoint":
            (args["checkpoints"] / "cp-one.json").unlink()
        elif fault == "missing_claim":
            db.execute("DELETE FROM operation_dispatch_claims")
        elif fault == "historical_schema":
            db.execute("DROP TABLE operation_dispatch_claims")
        elif fault == "unavailable_receipts":
            db.execute("DROP TABLE incident_resolution_closures")
        elif fault == "negative_decision":
            db.execute("UPDATE pending_approvals SET approved_decision=0")
        elif fault == "multiple_claims":
            db.execute("INSERT INTO pending_approvals SELECT 'apr-2',workflow_id,'req-2',checkpoint_id,"
                       "consumption_status,approved_decision FROM pending_approvals")
        else:
            state = cp["state"]["procedure_runtime_state"]
            if fault == "step":
                state["step"]["id"] = "2"
            elif fault == "approval":
                state["approval_id"] = "someone-else"
            else:
                state["vm_start_binding_fingerprint"] = "0" * 64
            write_cp(tmp_path, cp)
    row, = sqlite_inventory_page(**args, vm_start_deployment=deployment)["executions"]
    assert row["vm_start_dispatch"] == {"status": "review_required"} and op not in json.dumps(row)


def test_wrong_deployment_rejected_before_db_access(deployment):
    with pytest.raises(ValueError, match="affinity"):
        azure_sql_inventory_page(connection_factory=lambda: pytest.fail("opened"), consumer=affinity(),
                                 vm_start_deployment=deployment)


@pytest.mark.parametrize("claim", ["exact", "case", "space", "absent"])
def test_sql_dispatch_uses_one_snapshot_and_exact_ledger_identity(deployment, claim):
    scope, root, cp, op = evidence(deployment)
    values = {"exact": [(op,)], "case": [(op.upper(),)], "space": [(op + " ",)], "absent": []}
    db = Connection([
        ("SET TRANSACTION", []), ("SELECT TOP", [record(scope)]),
        ("SELECT OBJECT_ID", [(1,)]), ("FROM dbo.incident_rejection_closures", []),
        ("SELECT OBJECT_ID", [(1,)]), ("FROM dbo.incident_resolution_closures", []),
        ("FROM dbo.pending_approvals", [("apr-one", "wf-one", "req-one", "cp-one", "claimed")]),
        ("FROM dbo.incident_affine_continuation_jobs", [("apr-one", "wf-one", "claimed")]),
        ("FROM dbo.incident_continuation_jobs", []), ("JSON_VALUE(payload_json", [("cp-one", json.dumps(cp))]),
        ("checkpoint_id = %(parent)s", [(json.dumps(root),)]),
        ("JOIN dbo.incident_affine_continuation_jobs", [("wf-one", "wf-one", "apr-one", "apr-one", "req-one", "cp-one", True)]),
        ("checkpoint_id = %(parent)s", [(json.dumps(cp),)]),
        ("OBJECT_ID", [(1,)]), ("FROM dbo.operation_dispatch_claims", values[claim])])
    page = azure_sql_inventory_page(connection_factory=lambda: db, consumer=scope, vm_start_deployment=deployment)
    diag = page["executions"][0]["vm_start_dispatch"]
    if claim == "exact":
        assert diag["operation_id"] == op and diag["status"] == "dispatch_attributed_effect_unconfirmed"
    else:
        assert diag == {"status": "review_required"}
    assert db.statements[-1][1] == {"operation": op} and db.closed and db.rollbacks == 2
