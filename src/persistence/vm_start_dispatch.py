"""Read a VM Start dispatch claim in the inventory reader's existing transaction."""
import hashlib

from src.runtime.execution_affinity import AFFINITY_STATE_KEY, require_identifier
from src.runtime.incident_execution import EXECUTION_ID_STATE_KEY
from src.runtime.procedure.workflow_state import PROCEDURE_RUNTIME_STATE_KEY
from src.workflows.incident_resolution.vm_start_approval_binding import vm_start_snapshot_from_payload


def vm_start_dispatch(reader, execution, row, lookup, binding):
    if not row["compatible"]:
        return {"status": "out_of_scope"}
    review = {"status": "review_required"}
    if row["issues"]:
        return review
    approvals = row["approvals"].get("claimed", 0)
    jobs = row["candidate_jobs"].get("claimed", 0)
    if not (approvals or jobs):
        return {"status": "no_open_claimed_pair"}
    if (approvals != 1 or jobs != 1 or row["legacy_jobs"].get("claimed", 0)
            or any(row[key]["status"] != "absent" for key in ("resolution_receipt", "rejection_receipt"))):
        return review

    # Compare the identifiers returned by both tables in Python as well. A SQL
    # Server collation may treat case or trailing spaces as equivalent.
    tables, param = reader.prefix, reader.bind("execution")
    pairs = list(reader.rows(
        f"SELECT a.workflow_id, j.execution_id, a.approval_id, j.approval_id, a.request_id, "
        f"a.checkpoint_id, a.approved_decision FROM {tables}pending_approvals a "
        f"JOIN {tables}incident_affine_continuation_jobs j ON j.approval_id = a.approval_id "
        f"WHERE a.workflow_id = {param} AND j.execution_id = {param} "
        "AND a.consumption_status = 'claimed' AND j.status = 'claimed'",
        {"execution": execution.execution_id}))
    if len(pairs) != 1:
        return review
    workflow, owner, approval, job_approval, request, checkpoint_id, decision = pairs[0]
    if (workflow != execution.execution_id or owner != workflow or approval != job_approval or decision != 1
            or execution.approvals.get(request) != (checkpoint_id, "claimed")
            or checkpoint_id not in execution.checkpoints):
        return review

    doc = lookup(checkpoint_id)
    if (not doc or doc.get("workflow_name") != "incident-resolution" or doc.get("checkpoint_id") != checkpoint_id
            or doc["state"].get(EXECUTION_ID_STATE_KEY) != workflow
            or doc["state"].get(AFFINITY_STATE_KEY) != execution.affinity.to_document()
            or set(doc["pending_request_info_events"]) != {request}):
        return review
    payload = doc["state"].get(PROCEDURE_RUNTIME_STATE_KEY)
    try:
        snapshot = vm_start_snapshot_from_payload(payload, workflow_id=workflow, approval_id=approval)
        procedure = require_identifier(payload["procedure"]["id"], "procedure")
        step = require_identifier(payload["step"]["id"], "step")
    except ValueError:
        return review
    if snapshot.binding_fingerprint != binding:
        return review

    exists = ("SELECT OBJECT_ID(N'dbo.operation_dispatch_claims', N'U')" if reader.sql_server else
              "SELECT name FROM sqlite_master WHERE type='table' AND name='operation_dispatch_claims'")
    if not any(entry[0] for entry in reader.rows(exists)):
        return review
    claims = [entry[0] for entry in reader.rows(
        f"SELECT operation_id FROM {tables}operation_dispatch_claims WHERE operation_id = {reader.bind('operation')}",
        {"operation": snapshot.operation_id})]
    if claims != [snapshot.operation_id]:
        return review
    return {"status": "dispatch_attributed_effect_unconfirmed", "operation_id": snapshot.operation_id,
            "approval_sha256": hashlib.sha256(approval.encode("utf-8")).hexdigest(),
            "procedure_id": procedure, "step_id": step}
