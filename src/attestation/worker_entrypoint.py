"""Independent, non-HTTP Container Apps job. No approval or MCP dispatch capability.

Input is only an outbox hash. Key pins, permissions and approved state are never
taken from command-line JSON. Reconciliation reads original journal/Blob bytes
and cannot acquire write/sign authority or resume an uncertain attempt.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os

from src.attestation.governor_outbox import AzureSqlGovernorOutbox, operation_key, restore_job
from src.config.f27_attestation import load_attestation_configuration, sql_settings
from src.persistence.azure_blob_receipt_objects import LockedContainerPolicy
from src.persistence.azure_sql.connection_provider import build_mssql_python_connection_factory
from src.production_attestation import build_independent_attestation_worker
from src.workflows.incident_resolution.mcp_receipt_trust import parse_subject_json_v1


def run_owned_work(environment, operation_sha256, *, recovery=False, outbox_factory=AzureSqlGovernorOutbox,
                   worker_factory=build_independent_attestation_worker):
    cfg = load_attestation_configuration(environment)
    if cfg is None:
        raise ValueError("Independent attestor not enabled")
    attestor = cfg["pins"]["attestor"]
    if environment.get("AZURE_CLIENT_ID") != attestor.managed_identity.client_id:
        raise ValueError("Attestor UAMI selector mismatch")
    writer, reader = sql_settings(cfg, "attestor_writer"), sql_settings(cfg, "custody_reader")
    outbox = outbox_factory(read_factory=build_mssql_python_connection_factory(writer))
    raw = outbox.read(operation_sha256)
    if raw is None:
        raise ValueError("Governor-owned work not present")
    row = parse_subject_json_v1(raw)
    tool = row["operation"]["tool_name"]
    if tool not in {"group_list", "compute_vm_power-state"}:
        raise ValueError("Unregistered producer")
    job = restore_job(raw, project_endpoint=cfg["project_endpoint"], backend=cfg["pins"][tool], attestor=attestor)
    if operation_key(job.operation.trusted_scope, job.operation.operation_id) != operation_sha256:
        raise ValueError("Outbox operation identity mismatch")
    deployment = cfg["deployments"][tool]
    if (job.operation.agent_name, job.operation.agent_version, job.operation.server_label) != (
            deployment["agent_name"], deployment["agent_version"], deployment["server_label"]):
        raise ValueError("Work publication differs from deployed registry")
    blob = cfg["blob"]
    worker, close = worker_factory(job=job, sql_writer=writer, sql_reader=reader,
        account_url=blob["account_url"], container=blob["container"], policy=LockedContainerPolicy(**blob["policy"]),
        retain_until=datetime.fromisoformat(blob["retain_until"].replace("Z", "+00:00")),
        clock=lambda: datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"))
    try:
        return worker.reconcile() if recovery else worker.run_once()
    finally:
        close()


def main():
    parser = argparse.ArgumentParser(description="One governor-owned attestation or read-only reconciliation")
    parser.add_argument("--operation-sha256", required=True)
    parser.add_argument("--read-only-recovery", action="store_true")
    args = parser.parse_args()
    try:
        result = run_owned_work(os.environ, args.operation_sha256, recovery=args.read_only_recovery)
        print(json.dumps(asdict(result), sort_keys=True))
        return 0 if result.stop_code is None else 2
    except Exception:
        # Native payloads, SQL details, tokens and private paths stay local.
        print('{"outcome":"ATTESTOR_HOST_STOP_NO_RETRY","stop_code":"HOST_BOUNDARY_UNAVAILABLE"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
