"""Private insert-only handoff from the served governor to the independent worker.

The database principal boundary authenticates the source: only the core writer
may INSERT, and the attestor may only SELECT. No HTTP body supplies key pins,
approval flags, signing identity or deployment configuration. A commit timeout
stops and is never converted into retry authority by a subsequent read.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re

from src.agents.foundry_native_receipt_source import NativeReceiptReadbackPin
from src.attestation.foundry_backend_attestor import AttestationJob
from src.workflows.incident_resolution.mcp_authenticated_backend_bridge import PinnedOperationLink
from src.workflows.incident_resolution.mcp_receipt_trust import canonical_subject_v1, parse_subject_json_v1

_INSERT = """INSERT INTO dbo.f27_governor_outbox_v1
(operation_sha256, record_sha256, record_bytes) VALUES (%(operation)s, %(digest)s, %(record)s)"""
_SELECT = """SELECT record_sha256, record_bytes FROM dbo.f27_governor_outbox_v1
WHERE operation_sha256 = %(operation)s"""


def fingerprint(key: bytes, domain: str, value: bytes) -> str:
    if type(key) is not bytes or len(key) != 32 or domain not in {"arguments", "principal", "revision", "image"}:
        raise ValueError("F27_FINGERPRINT_CONFIGURATION")
    return "hmac:" + hmac.digest(key, b"AI-SUPPORT-F27-FINGERPRINT-V1\0" + domain.encode("ascii") + b"\0" + value, "sha256").hex()


def operation_key(scope, operation_id):
    return hashlib.sha256(canonical_subject_v1({"domain": "f27-governor-outbox-v1",
        "scope": scope, "operation_id": operation_id})).hexdigest()


def _close(*objects):
    for obj in objects:
        if obj is not None:
            try:
                obj.close()
            except Exception:
                pass


class AzureSqlGovernorOutbox:
    def __init__(self, *, read_factory, write_factory=None):
        if not callable(read_factory) or (write_factory is not None and not callable(write_factory)):
            raise TypeError("Explicit SQL factories required")
        self._read, self._write = read_factory, write_factory

    def read(self, key):
        if type(key) is not str or re.fullmatch(r"[a-f0-9]{64}", key) is None:
            raise ValueError("Exact operation hash required")
        conn = cur = None
        try:
            conn = self._read()
            cur = conn.cursor()
            cur.execute(_SELECT, {"operation": bytes.fromhex(key)})
            row = cur.fetchone()
            if row is None:
                return None
            if cur.fetchone() is not None:
                raise ValueError("Outbox uniqueness violated")
            digest, raw = bytes(row[0]), bytes(row[1])
            if not 0 < len(raw) <= 65536 or hashlib.sha256(raw).digest() != digest:
                raise ValueError("Outbox bytes differ from digest")
            return raw
        finally:
            _close(cur, conn)

    def insert_once(self, key, raw):
        if self._write is None:
            raise PermissionError("Read-only outbox")
        if (type(key) is not str or re.fullmatch(r"[a-f0-9]{64}", key) is None
                or type(raw) is not bytes or not 0 < len(raw) <= 65536):
            raise ValueError("Bounded exact outbox record required")
        conn = cur = None
        try:
            conn = self._write()
            if getattr(conn, "autocommit", None) is not False:
                raise ValueError("Explicit SQL transaction required")
            cur = conn.cursor()
            cur.execute(_INSERT, {"operation": bytes.fromhex(key), "digest": hashlib.sha256(raw).digest(), "record": raw})
            conn.commit()
        except Exception as exc:
            # Never infer committed/not-committed from a transport exception.
            raise RuntimeError("GOVERNOR_OUTBOX_UNCERTAIN_NO_RETRY") from exc
        finally:
            _close(cur, conn)
        if self.read(key) != raw:
            raise RuntimeError("GOVERNOR_OUTBOX_READBACK_MISMATCH_NO_RETRY")


def record_job(job):
    return canonical_subject_v1({"schema": "f27-governor-work-v1", "operation": asdict(job.operation),
        "approval_prompt_response_id": job.native.approval_prompt_response_id,
        "arguments": parse_subject_json_v1(job.native.expected_arguments_json)})


def restore_job(raw, *, project_endpoint, backend, attestor):
    """Only bytes obtained from the private SQL reader; keys never come from the row."""
    row = parse_subject_json_v1(raw)
    if set(row) != {"schema", "operation", "approval_prompt_response_id", "arguments"} or row["schema"] != "f27-governor-work-v1":
        raise ValueError("Exact governor work schema required")
    operation = PinnedOperationLink(**row["operation"])
    native = NativeReceiptReadbackPin(project_endpoint, attestor.managed_identity,
        row["approval_prompt_response_id"], operation.response_id, operation.approval_request_id,
        operation.server_label, operation.tool_name, canonical_subject_v1(row["arguments"]))
    return AttestationJob(operation, native, backend, attestor)


def native_response_id(response):
    """Resolve the same observed SDK wrappers as the executor, without guessing latest."""
    def get(obj, name):
        return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    representation = get(response, "raw_representation")
    source = get(response, "raw_response") or get(representation, "raw_representation") or representation or response
    native, framework = get(source, "id"), get(response, "response_id")
    if native and framework and native != framework:
        raise ValueError("Native/framework response mismatch")
    result = native or framework
    if type(result) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", result):
        raise ValueError("Native execution response ID missing")
    return result


class GovernorAttestationPublisher:
    """Called by AzureOperationsExecutor after its verified approval continuation."""
    def __init__(self, *, outbox, project_endpoint, backend_pins, attestor_pin,
                 deployment_pins, fingerprint_key, clock=None):
        self.outbox, self.project = outbox, project_endpoint
        self.backends, self.attestor, self.deployments = dict(backend_pins), attestor_pin, dict(deployment_pins)
        self.key = bytes(fingerprint_key)
        if len(self.key) != 32 or set(self.backends) != {"group_list", "compute_vm_power-state"} or set(self.deployments) != set(self.backends):
            raise ValueError("Exact READ/WRITE producer registry required")
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def publish(self, *, request, approval, response, agent_definition, dispatch_ledger, started_at):
        from src.workflows.incident_resolution.azure_operations_models import VerifiedAzureOperationRequest
        if not isinstance(request, VerifiedAzureOperationRequest) or not dispatch_ledger.contains(request.operation_id):
            raise ValueError("Verified governor request and consumed dispatch required")
        if agent_definition is None or not request.approval_id:
            raise ValueError("Pinned publication and separate human approval required")
        tool = approval.tool_name
        backend, deployment = self.backends[tool], self.deployments[tool]
        if (agent_definition.name, agent_definition.version, approval.server_label) != (
                deployment["agent_name"], deployment["agent_version"], deployment["server_label"]):
            raise ValueError("Governor publication differs from qualified deployment")
        now = self.clock()
        if started_at.tzinfo is None or now.tzinfo is None or not started_at <= now:
            raise ValueError("Governor observation window required")
        def stamp(t): return t.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        args = canonical_subject_v1(approval.arguments)
        operation = PinnedOperationLink(backend.scope, request.operation_id, request.workflow_id,
            "APPROVED", request.approval_id, True, native_response_id(response), approval.approval_request_id,
            agent_definition.name, agent_definition.version, approval.server_label, tool, request.capability_id,
            fingerprint(self.key, "arguments", args), fingerprint(self.key, "revision", deployment["revision"].encode("ascii")),
            fingerprint(self.key, "image", deployment["image"].encode("ascii")), stamp(started_at), stamp(now + timedelta(minutes=15)))
        native = NativeReceiptReadbackPin(self.project, self.attestor.managed_identity, approval.response_id,
            operation.response_id, approval.approval_request_id, approval.server_label, tool, args)
        job = AttestationJob(operation, native, backend, self.attestor)
        key = operation_key(operation.trusted_scope, operation.operation_id)
        self.outbox.insert_once(key, record_job(job))
        return key
