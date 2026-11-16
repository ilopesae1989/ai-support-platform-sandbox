"""Join provider-read MCP output to three signed backend observations.

Internal worker, not an HTTP endpoint. All pins must come from the governor's
durable authorized state. This module cannot qualify the production sensor,
caller, key isolation or coverage. It never approves or dispatches a tool.
The wire field below is a NEW producer contract, not a claim that Microsoft's
unmodified MCP image emits or Foundry preserves these receipts today.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from threading import Lock

from src.agents.foundry_native_receipt_source import (
    FoundryNativeReceiptSource, NativeReceiptReadbackPin, NativeMcpReadback,
)
from src.azure_key_vault_receipt_signing import (
    KeyVaultReceiptPin, validate_independent_receipt_pins,
)
from src.persistence.receipt_custody import CustodyOutcome
from src.workflows.incident_resolution.mcp_authenticated_backend_bridge import (
    PinnedOperationLink, verify_offline_backend_association,
)
from src.workflows.incident_resolution.mcp_backend_evidence_contract import validate_evidence_envelope
from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier, canonical_subject_v1, parse_subject_json_v1,
)

KINDS = ("MCP_HTTP_AUTH_EVALUATED", "MCP_TOOL_DISPATCH_STARTED", "MCP_TOOL_DISPATCH_FINISHED")
LINK_DOMAIN = "correlation:authenticated_backend_request"
WIRE_FIELD = "f27_backend_receipts_v1"


class AttestationStopped(RuntimeError):
    """No automatic retry or new execution authority."""


def require(value, code):
    if not value:
        raise AttestationStopped(code)


def digest(value):
    return hashlib.sha256(canonical_subject_v1(value)).hexdigest()


def stamp(value):
    require(type(value) is str and value.endswith("Z"), "INVALID_UTC")
    result = datetime.fromisoformat(value[:-1] + "+00:00")
    require(result.tzinfo == timezone.utc, "INVALID_UTC")
    return result


@dataclass(frozen=True)
class AttestationJob:
    operation: PinnedOperationLink
    native: NativeReceiptReadbackPin
    backend: KeyVaultReceiptPin
    attestor: KeyVaultReceiptPin

    def __post_init__(self):
        p, n = self.operation, self.native
        require(type(p) is PinnedOperationLink and type(n) is NativeReceiptReadbackPin,
                "TRUSTED_GOVERNOR_PINS_REQUIRED")
        validate_independent_receipt_pins(self.backend, self.attestor)
        require(p.trusted_scope == self.backend.scope, "SCOPE_MISMATCH")
        require(p.approval_state == "APPROVED" and p.technical_approval is True,
                "APPROVED_JOB_REQUIRED")
        require((p.response_id, p.approval_request_id, p.server_label, p.tool_name) ==
                (n.execution_response_id, n.approval_request_id, n.server_label, n.tool_name),
                "NATIVE_PIN_MISMATCH")
        require(n.identity == self.attestor.managed_identity, "ATTESTOR_IDENTITY_MISMATCH")
        require({"event:" + k for k in KINDS}.issubset(self.backend.public_key.domains),
                "BACKEND_DOMAINS_REQUIRED")
        require(LINK_DOMAIN in self.attestor.public_key.domains, "ATTESTOR_DOMAIN_REQUIRED")

    @property
    def owner(self):
        return digest({"domain": "f27-attestation-operation-v1", "scope": self.operation.trusted_scope,
                       "operation_id": self.operation.operation_id})

    @property
    def record(self):
        # No arguments or credentials in the claim, only their canonical digest.
        return canonical_subject_v1({"operation": asdict(self.operation),
            "project": self.native.project_endpoint,
            "approval_prompt_response_id": self.native.approval_prompt_response_id,
            "arguments_sha256": hashlib.sha256(self.native.expected_arguments_json).hexdigest(),
            "backend_kid": self.backend.public_key.kid, "attestor_kid": self.attestor.public_key.kid,
            "backend_identity": asdict(self.backend.managed_identity),
            "attestor_identity": asdict(self.attestor.managed_identity)})

    @property
    def claims(self):
        return (self.owner,) + tuple(digest({"domain": domain,
            "project": self.native.project_endpoint, "id": value}) for domain, value in (
            ("f27-native-response-v1", self.operation.response_id),
            ("f27-native-approval-v1", self.operation.approval_request_id)))


@dataclass(frozen=True)
class AttestationResult:
    outcome: str
    owner_sha256: str
    signed_pairs: int = 0
    stored_pairs: int = 0
    stop_code: str | None = None
    # No success/resolved/dispatch_allowed field: custody is not technical acceptance.


def provider_events(readback, job, verifier):
    require(type(readback) is NativeMcpReadback, "NATIVE_READBACK_REQUIRED")
    n = job.native
    require((readback.approval_prompt_response_id, readback.execution_response_id,
             readback.approval_request_id, readback.server_label, readback.tool_name) ==
            (n.approval_prompt_response_id, n.execution_response_id,
             n.approval_request_id, n.server_label, n.tool_name), "READBACK_IDENTITY_MISMATCH")

    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "DUPLICATE_PROVIDER_OUTPUT_KEY")
            obj[key] = value
        return obj

    def invalid(_):
        raise AttestationStopped("NONFINITE_PROVIDER_OUTPUT")

    require(len(readback.provider_output.encode("utf-8")) <= 1048576, "OUTPUT_TOO_LARGE")
    output = json.loads(readback.provider_output, object_pairs_hook=unique, parse_constant=invalid)
    require(type(output) is dict and WIRE_FIELD in output, "BACKEND_RECEIPTS_NOT_IN_NATIVE_OUTPUT")
    events = output[WIRE_FIELD]
    require(type(events) is list and len(events) == 3, "EXACT_THREE_BACKEND_EVENTS_REQUIRED")
    # Receipt JSON is reserialized without binary-float canonicalization: the
    # envelope contains only strings, booleans and maps, never numeric fields.
    plain = [parse_subject_json_v1(canonical_subject_v1(e)) for e in events]
    require(tuple(e.get("event_type") for e in plain) == KINDS, "BACKEND_EVENT_ORDER")
    p = job.operation
    reference = plain[0]
    require(len({e.get("event_id") for e in plain}) == 3, "DUPLICATE_BACKEND_EVENT")
    captured = []
    for event in plain:
        valid = validate_evidence_envelope(event)
        require(valid["source_component"] == "mcp_backend", "BACKEND_ISSUER")
        require(all(event[k] == reference[k] for k in ("producer_instance_id", "backend_request_id")),
                "BACKEND_REQUEST_OR_PRODUCER_MISMATCH")
        require(all(event[k] == getattr(p, k) for k in ("tool_name", "arguments_fingerprint",
                "backend_revision_fingerprint", "image_fingerprint")), "BACKEND_PIN_MISMATCH")
        t = stamp(event["captured_at_utc"])
        require(stamp(p.window_start_utc) <= t <= stamp(p.window_end_utc), "BACKEND_TIME_OUTSIDE_WINDOW")
        captured.append(t)
        receipt = event["source_receipt"]
        require(receipt["proof_id"].split(":")[2] == job.backend.public_key.kid, "BACKEND_KEY_MISMATCH")
        require(verifier(receipt, subject_kind="event:" + event["event_type"],
                         subject={k: v for k, v in event.items() if k != "source_receipt"}) is True,
                "BACKEND_SIGNATURE_INVALID")
    require(captured == sorted(captured), "BACKEND_TIME_ORDER")
    require(reference["auth_result"] == "ACCEPT" and all(reference[k] is True for k in (
        "issuer_valid", "tenant_valid", "audience_valid", "lifetime_valid", "role_or_scope_valid")),
        "BACKEND_AUTH_NOT_ACCEPTED")
    return tuple(plain)


def bridge_subject(job, event, observed):
    p = job.operation
    require(stamp(p.window_start_utc) <= stamp(observed) <= stamp(p.window_end_utc),
            "ATTESTATION_TIME_OUTSIDE_WINDOW")
    return dict(schema_version="1.0", bridge_id="bridge-" + digest({"owner": job.owner,
        "event_id": event["event_id"]}), method="authenticated_provider_link",
        exact_operation_id=p.operation_id, workflow_id=p.workflow_id,
        approval_state=p.approval_state, human_approval_id=p.human_approval_id,
        technical_approval=p.technical_approval, linked_response_id=p.response_id,
        linked_approval_request_id=p.approval_request_id,
        linked_backend_request_id=event["backend_request_id"], linked_backend_event_id=event["event_id"],
        agent_name=p.agent_name, agent_version=p.agent_version, server_label=p.server_label,
        tool_name=p.tool_name, capability_id=p.capability_id,
        arguments_fingerprint=p.arguments_fingerprint,
        backend_revision_fingerprint=p.backend_revision_fingerprint, image_fingerprint=p.image_fingerprint,
        observed_at_utc=observed)


class FoundryBackendAttestor:
    """One worker attempt; fresh processes are excluded by the durable journal.

    reserve/put must return True only after acknowledged commit and independent
    readback. Existing/unknown records never grant ownership. Recovery only
    reads the original bytes and reconciles storage, never signs again.
    """
    def __init__(self, *, job, source, journal, signer_factory, custodian, clock):
        require(type(job) is AttestationJob and type(source) is FoundryNativeReceiptSource,
                "EXPLICIT_JOB_AND_SOURCE_REQUIRED")
        require(source.pin == job.native, "SOURCE_PIN_MISMATCH")
        self.job, self.source, self.journal = job, source, journal
        self.signer_factory, self.custodian, self.clock = signer_factory, custodian, clock
        self.backend_verifier = IndependentReceiptVerifier(scope=job.operation.trusted_scope,
                                                          keys=(job.backend.public_key,))
        self.bridge_verifier = IndependentReceiptVerifier(scope=job.operation.trusted_scope,
                                                         keys=(job.attestor.public_key,))
        self._lock, self._consumed = Lock(), False

    def run_once(self):
        with self._lock:
            require(not self._consumed, "WORKER_ALREADY_CONSUMED")
            self._consumed = True
        j, owner = self.job, self.job.owner
        signed = stored = 0
        try:
            require(self.journal.reserve(j.claims, owner, j.record) is True, "OPERATION_CLAIM_UNAVAILABLE")
            readback = self.source.read_once()
            events = provider_events(readback, j, self.backend_verifier)
            claims = tuple(digest({"domain": domain, "scope": j.operation.trusted_scope,
                "principal": j.backend.managed_identity.principal_id, "id": value}) for domain, value in
                [("f27-backend-request-v1", events[0]["backend_request_id"])] +
                [("f27-backend-event-v1", event["event_id"]) for event in events])
            require(self.journal.reserve(claims, owner, j.record) is True, "BACKEND_REPLAY_OR_UNKNOWN")
            for stage, raw in zip(("NATIVE_APPROVAL", "NATIVE_EXECUTION", "NATIVE_INPUT"), (
                    readback.approval_response_bytes, readback.execution_response_bytes, readback.execution_input_bytes)):
                require(self.journal.put(owner, stage, raw) is True, "NATIVE_CUSTODY_UNCERTAIN")
            observed = self.clock()
            for number, event in enumerate(events):
                bridge = bridge_subject(j, event, observed)
                signer = self.signer_factory(j.attestor)
                require(signer.pin == j.attestor, "SIGNER_PIN_MISMATCH")
                try:
                    receipt = signer.sign(subject_json=canonical_subject_v1(bridge), domain=LINK_DOMAIN)
                finally:
                    signer.close()
                bridge["source_receipt"] = receipt.receipt
                verify_offline_backend_association(pinned=j.operation, signed_bridge=bridge,
                    backend_event=event, bridge_verifier=self.bridge_verifier, backend_verifier=self.backend_verifier)
                signed += 1
                pair = canonical_subject_v1({"signed_bridge": bridge, "backend_event": event})
                require(self.journal.put(owner, "PAIR_" + str(number), pair) is True, "PAIR_CUSTODY_UNCERTAIN")
                result = self.custodian.store(pinned=j.operation, signed_bridge=bridge, backend_event=event)
                require(result.outcome == CustodyOutcome.STORED_VERIFIED_NO_AUTHORITY, "PAIR_STORE_UNCERTAIN")
                stored += 1
            require(self.journal.put(owner, "COMPLETE", canonical_subject_v1({"stored_pairs": stored,
                    "authority": False})) is True, "COMPLETION_RECORD_UNCERTAIN")
            return AttestationResult("RECEIPTS_STORED_VERIFIED_NO_AUTHORITY", owner, signed, stored)
        except Exception as exc:
            code = str(exc) if type(exc) is AttestationStopped else "ATTESTATION_UNAVAILABLE_NO_RETRY"
            return AttestationResult("ATTESTATION_STOP_NO_RETRY", owner, signed, stored, code)

    def reconcile(self):
        """Read-only reconciliation; never resumes an interrupted worker."""
        owner, count = self.job.owner, 0
        try:
            require(self.journal.read_claim(owner) == self.job.record, "RECOVERY_PIN_MISMATCH")
            for number in range(3):
                raw = self.journal.get(owner, "PAIR_" + str(number))
                require(raw is not None, "RECOVERY_PAIR_MISSING")
                pair = parse_subject_json_v1(raw)
                require(set(pair) == {"signed_bridge", "backend_event"}, "RECOVERY_PAIR_SCHEMA")
                result = self.custodian.reconcile(pinned=self.job.operation, **pair)
                require(result.outcome == CustodyOutcome.PRESENT_VERIFIED_NO_AUTHORITY,
                        "RECOVERY_CUSTODY_NOT_VERIFIED")
                count += 1
            return AttestationResult("RECOVERY_READBACK_VERIFIED_NO_AUTHORITY", owner, 0, count)
        except Exception as exc:
            code = str(exc) if type(exc) is AttestationStopped else "RECOVERY_UNAVAILABLE"
            return AttestationResult("RECOVERY_INCOMPLETE_NO_WRITES", owner, 0, count, code)
