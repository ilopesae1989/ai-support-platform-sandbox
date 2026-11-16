"""Non-live source authentication boundary, immutable outbox and recovery dispatch tests."""
import base64
from dataclasses import replace, asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.attestation.governor_outbox import (
    AzureSqlGovernorOutbox, GovernorAttestationPublisher, fingerprint, native_response_id,
    operation_key, record_job, restore_job,
)
from src.attestation.worker_entrypoint import run_owned_work
from src.config.f27_attestation import load_attestation_configuration

spec = importlib.util.spec_from_file_location("outbox_worker_fixture", Path(__file__).with_name("test_foundry_backend_attestor.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def configuration(tmp_path):
    f = fixture.setup()
    _, write_key = fixture.crypto._key("mcp_backend", "event:MCP_HTTP_AUTH_EVALUATED")
    write_key = replace(write_key, domains=f.job.backend.public_key.domains)
    write = replace(f.job.backend, key_id="https://f27synthetic.vault.azure.net/keys/write/" + "c" * 32,
        public_key=write_key, managed_identity=fixture.ReceiptManagedIdentity("user_assigned",
            "00000000-0000-0000-0000-000000000005", "00000000-0000-0000-0000-000000000006"))
    keys = {}
    for name, pin in {"group_list": f.job.backend, "compute_vm_power-state": write, "attestor": f.job.attestor}.items():
        keys[name] = {"key_id": pin.key_id, "identity": asdict(pin.managed_identity),
            "public_spki_base64": base64.b64encode(pin.public_key.spki_der).decode(), "spki_sha256": pin.public_key.kid}
    deployment = dict(revision="synthetic--r1", image="sha256:" + "a" * 64,
        agent_name=f.job.operation.agent_name, agent_version=f.job.operation.agent_version,
        server_label=f.job.operation.server_label)
    cfg = dict(schema="f27-runtime-attestation-v1", scope=f.job.operation.trusted_scope,
        project_endpoint=f.job.native.project_endpoint, keys=keys,
        deployments={"group_list": deployment, "compute_vm_power-state": dict(deployment)},
        sql=dict(server="synthetic.database.windows.net", database="syntheticdb",
            core_writer_client_id="00000000-0000-0000-0000-000000000007",
            attestor_writer_client_id=f.job.attestor.managed_identity.client_id,
            custody_reader_client_id="00000000-0000-0000-0000-000000000004"),
        blob=dict(account_url="https://f27synthetic.blob.core.windows.net", container="receipts",
            retain_until="2026-10-29T10:00:00Z", policy=dict(resource_id=
                "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/synthetic/providers/"
                "Microsoft.Storage/storageAccounts/f27synthetic/blobServices/default/containers/receipts/immutabilityPolicies/default",
                etag='"etag"', retention_days=2)))
    raw = json.dumps(cfg).encode()
    path = tmp_path / "runtime.json"
    path.write_bytes(raw)
    env = {"F27_ATTESTATION_ENABLED": "true", "F27_ATTESTATION_CONFIG_PATH": str(path),
        "F27_ATTESTATION_CONFIG_SHA256": hashlib.sha256(raw).hexdigest(),
        "AZURE_CLIENT_ID": f.job.attestor.managed_identity.client_id}
    return f, cfg, env


def test_roundtrip_job_uses_independently_pinned_keys():
    f = fixture.setup()
    raw = record_job(f.job)
    restored = restore_job(raw, project_endpoint=f.job.native.project_endpoint, backend=f.job.backend, attestor=f.job.attestor)
    assert restored == f.job
    assert f.job.backend.key_id.encode() not in raw
    assert f.job.attestor.managed_identity.client_id.encode() not in raw
    forged = json.loads(raw)
    forged["keys"] = {"attestor": "injected"}
    with pytest.raises(ValueError):
        restore_job(json.dumps(forged).encode(), project_endpoint=f.job.native.project_endpoint,
            backend=f.job.backend, attestor=f.job.attestor)


def test_ambiguous_commit_never_reads_or_retries():
    calls = []
    class Connection:
        autocommit = False
        def cursor(self): return self
        def execute(self, sql, args): calls.append("INSERT")
        def commit(self): calls.append("COMMIT"); raise TimeoutError("uncertain")
        def close(self): calls.append("CLOSE")
    box = AzureSqlGovernorOutbox(write_factory=Connection, read_factory=lambda: pytest.fail("No read after uncertain commit"))
    with pytest.raises(RuntimeError, match="UNCERTAIN_NO_RETRY"):
        box.insert_once("a" * 64, b'{"synthetic":true}')
    assert calls.count("INSERT") == calls.count("COMMIT") == 1


def test_read_only_outbox_cannot_insert():
    box = AzureSqlGovernorOutbox(read_factory=lambda: None)
    with pytest.raises(PermissionError): box.insert_once("a" * 64, b"{}")


@pytest.mark.parametrize("fault", ["digest", "extra", "same_key", "identity", "missing"])
def test_config_rejects_drift_before_credentials(tmp_path, fault):
    f, cfg, env = configuration(tmp_path)
    if fault == "digest": env["F27_ATTESTATION_CONFIG_SHA256"] = "0" * 64
    elif fault == "extra": cfg["approved"] = True
    elif fault == "same_key": cfg["keys"]["compute_vm_power-state"] = cfg["keys"]["group_list"]
    elif fault == "identity": cfg["keys"]["attestor"]["identity"] = cfg["keys"]["group_list"]["identity"]
    else: cfg["keys"].pop("attestor")
    if fault != "digest":
        raw = json.dumps(cfg).encode(); Path(env["F27_ATTESTATION_CONFIG_PATH"]).write_bytes(raw)
        env["F27_ATTESTATION_CONFIG_SHA256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises((ValueError, KeyError)): load_attestation_configuration(env)


@pytest.mark.parametrize("recovery", [False, True])
def test_independent_host_only_accepts_sql_owned_hash_and_selects_recovery(tmp_path, recovery):
    f, cfg, env = configuration(tmp_path)
    key = operation_key(f.job.operation.trusted_scope, f.job.operation.operation_id)
    calls = []
    class Box:
        def __init__(self, *, read_factory): calls.append("reader")
        def read(self, given): assert given == key; calls.append("SQL_READ"); return record_job(f.job)
    class Worker:
        def reconcile(self): calls.append("RECONCILE_NO_WRITES"); return "recovered"
        def run_once(self): calls.append("ONE_ATTEMPT"); return "attempted"
    def build(**kw):
        assert kw["job"] == f.job
        return Worker(), lambda: calls.append("close")
    result = run_owned_work(env, key, recovery=recovery, outbox_factory=Box, worker_factory=build)
    assert result == ("recovered" if recovery else "attempted")
    assert calls == ["reader", "SQL_READ", "RECONCILE_NO_WRITES" if recovery else "ONE_ATTEMPT", "close"]


def test_host_does_not_accept_wrong_managed_identity(tmp_path):
    _, _, env = configuration(tmp_path)
    env["AZURE_CLIENT_ID"] = "00000000-0000-0000-0000-000000000099"
    with pytest.raises(ValueError, match="UAMI"):
        run_owned_work(env, "a" * 64, outbox_factory=lambda **kw: pytest.fail("No SQL"))


@pytest.mark.parametrize("response", [{}, {"id": ""}, {"id": "one", "response_id": "other"}])
def test_native_response_identity_cannot_be_guessed(response):
    with pytest.raises(ValueError): native_response_id(response)


def test_hmac_domain_separation_and_argument_canonicalization():
    key = bytes(range(32))
    assert fingerprint(key, "arguments", b"{}") != fingerprint(key, "revision", b"{}")
    assert fingerprint(key, "arguments", b"{}") != fingerprint(bytes(reversed(key)), "arguments", b"{}")
    with pytest.raises(ValueError): fingerprint(b"short", "arguments", b"{}")


def test_publisher_rejects_unclaimed_or_non_governor_work():
    f = fixture.setup()
    publisher = GovernorAttestationPublisher(outbox=None, project_endpoint=f.job.native.project_endpoint,
        backend_pins={"group_list": f.job.backend, "compute_vm_power-state": f.job.backend}, attestor_pin=f.job.attestor,
        deployment_pins={"group_list": {}, "compute_vm_power-state": {}}, fingerprint_key=bytes(range(32)))
    with pytest.raises(ValueError, match="Verified governor"):
        publisher.publish(request=SimpleNamespace(operation_id="forged"), approval=None, response=None,
            agent_definition=None, dispatch_ledger=None, started_at=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_served_governor_publishes_once_after_native_continuation():
    from agent_framework import WorkflowBuilder
    from src.workflows.incident_resolution.executors.azure_operations import AzureOperationsExecutor
    from tests.workflows.incident_resolution.test_configured_rg_list_binding_boundary import (
        _configured_registry, RecordingReadAgents, RecordingDispatchLedger, _run,
        first_approval_response, verified_read_request,
    )
    f = fixture.setup()
    from src.config.foundry_capability_bindings import build_capability_foundry_agent_binding_registry, SANDBOX_PROJECT_ENDPOINT
    registry = build_capability_foundry_agent_binding_registry({
        'FOUNDRY_CAPABILITY_BINDING_PROFILE': 'azure-resource-group-list-isolated-v1',
        'FOUNDRY_RG_LIST_AGENT_VERSION': '3', 'FOUNDRY_PROJECT_ENDPOINT': SANDBOX_PROJECT_ENDPOINT})
    binding = registry.get('azure.resource_group.list')
    deployment = dict(agent_name=binding.agent_definition.name, agent_version=binding.agent_definition.version,
        server_label=binding.read_tool_authority.server_label, revision='synthetic--r1', image='sha256:'+'a'*64)
    calls = []
    class Box:
        def insert_once(self, key, raw): calls.append((key, raw))
    publisher = GovernorAttestationPublisher(outbox=Box(), project_endpoint=f.job.native.project_endpoint,
        backend_pins={'group_list':f.job.backend,'compute_vm_power-state':f.job.backend}, attestor_pin=f.job.attestor,
        deployment_pins={'group_list':deployment,'compute_vm_power-state':deployment}, fingerprint_key=bytes(range(32)))
    agents, ledger = RecordingReadAgents(first_approval_response(raw_server_label='azure-mcp-rglist-read',
        native_server_label='azure-mcp-rglist-read')), RecordingDispatchLedger()
    executor = AzureOperationsExecutor(agents=agents, operation_dispatch_ledger=ledger,
        capability_foundry_agent_binding_registry=registry, attestation_publisher=publisher)
    workflow = WorkflowBuilder(start_executor=executor, output_from=[executor], name='f27-owned-work').build()
    request = verified_read_request()
    outputs = await _run(workflow, request)
    assert len(outputs) == 1 and outputs[0].error is None
    assert len(calls) == len(agents.continue_calls) == ledger.count() == 1
    key, raw = calls[0]
    restored = restore_job(raw, project_endpoint=f.job.native.project_endpoint, backend=f.job.backend, attestor=f.job.attestor)
    assert restored.operation.operation_id == request.operation_id
    assert restored.operation.response_id == 'resp-f27-read-final'
    assert restored.operation.human_approval_id == request.approval_id
    assert key == operation_key(restored.operation.trusted_scope, request.operation_id)
    with pytest.raises(Exception):
        await _run(workflow, request)
    assert len(calls) == len(agents.continue_calls) == 1


@pytest.mark.parametrize("role", ["core_writer_client_id", "custody_reader_client_id"])
def test_config_rejects_attestor_reusing_sql_authority(tmp_path, role):
    _, cfg, env = configuration(tmp_path)
    cfg["sql"][role] = cfg["sql"]["attestor_writer_client_id"]
    raw = json.dumps(cfg).encode()
    Path(env["F27_ATTESTATION_CONFIG_PATH"]).write_bytes(raw)
    env["F27_ATTESTATION_CONFIG_SHA256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="Separate core"):
        load_attestation_configuration(env)
