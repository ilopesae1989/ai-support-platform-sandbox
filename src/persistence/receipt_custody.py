"""Store a verified receipt pair before indexing it; never authorize dispatch.

This component performs storage I/O when called. Signature verification proves
the signed association, not the truth of its producer or sensor coverage.
The caller must obtain PinnedOperationLink from its trusted governor and must
qualify the deployed producer, independent attestor and storage identities.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import hashlib
from typing import Protocol

from src.workflows.incident_resolution.mcp_authenticated_backend_bridge import (
    PinnedOperationLink, verify_offline_backend_association,
)
from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier, canonical_subject_v1, parse_subject_json_v1,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CustodyOutcome(StrEnum):
    STORED_VERIFIED_NO_AUTHORITY = "STORED_VERIFIED_NO_AUTHORITY"
    PRESENT_VERIFIED_NO_AUTHORITY = "PRESENT_VERIFIED_NO_AUTHORITY"
    REJECTED_BEFORE_IO = "REJECTED_BEFORE_IO"
    STORAGE_UNCERTAIN_NO_RETRY = "STORAGE_UNCERTAIN_NO_RETRY"
    INDEX_UNCERTAIN_NO_RETRY = "INDEX_UNCERTAIN_NO_RETRY"
    CONFLICT_NO_AUTHORITY = "CONFLICT_NO_AUTHORITY"


class IndexOutcome(StrEnum):
    COMMITTED = "COMMITTED"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CustodyResult:
    outcome: CustodyOutcome
    logical_sha256: str | None = None
    record_sha256: str | None = None
    # Diagnostic counts, NOT evidence of absence after transport errors.
    object_create_attempts: int = 0
    index_insert_attempts: int = 0


class ReceiptObjects(Protocol):
    def create_and_verify(self, name: str, data: bytes) -> Mapping[str, object]: ...
    def read_and_verify(self, name: str, data: bytes) -> Mapping[str, object]: ...


class ReceiptIndex(Protocol):
    def insert_once(self, logical_sha256: str, record: bytes) -> IndexOutcome: ...
    def read(self, logical_sha256: str, record: bytes) -> IndexOutcome: ...


class ReceiptCustodian:
    """Explicit custody service. No cleanup, retry, signing or execution API.

    On any partial failure the caller retains the original signed pair and
    calls reconcile() on a later explicit recovery action. Reconciliation
    only reads; it never fills a missing object or repeats an INSERT.
    """

    def __init__(self, *, objects: ReceiptObjects, index: ReceiptIndex,
                 bridge_verifier: IndependentReceiptVerifier,
                 backend_verifier: IndependentReceiptVerifier):
        self._objects, self._index = objects, index
        self._bridge, self._backend = bridge_verifier, backend_verifier

    def _prepare(self, pinned, signed_bridge, backend_event):
        # Snapshot canonical bytes before verification, defeating later input
        # mutation. These complete signed bytes, not just their subjects, persist.
        bridge_bytes = canonical_subject_v1(signed_bridge)
        event_bytes = canonical_subject_v1(backend_event)
        bridge = parse_subject_json_v1(bridge_bytes)
        event = parse_subject_json_v1(event_bytes)
        association = verify_offline_backend_association(
            pinned=pinned, signed_bridge=bridge, backend_event=event,
            bridge_verifier=self._bridge, backend_verifier=self._backend,
        )
        identity = {
            "schema": "f27-receipt-custody-v1", "scope": pinned.trusted_scope,
            "issuer": "mcp_backend", "domain": "event:" + association.backend_event_type,
            "operation_id": pinned.operation_id, "event_id": association.backend_event_id,
        }
        logical = sha256(b"F27-CUSTODY-IDENTITY-V1\x00" + canonical_subject_v1(identity))
        record = dict(identity, workflow_id=pinned.workflow_id,
                      backend_request_id=association.backend_request_id,
                      bridge_id=association.bridge_id, approval_state=pinned.approval_state,
                      response_id=pinned.response_id, approval_request_id=pinned.approval_request_id,
                      backend_kid=event["source_receipt"]["proof_id"].split(":")[2],
                      attestor_kid=bridge["source_receipt"]["proof_id"].split(":")[2])
        objects = tuple((role, f"v1/{logical}/{role}-{sha256(data)}.json", data)
                        for role, data in (("backend", event_bytes), ("attestor", bridge_bytes)))
        return logical, record, objects

    def _run(self, *, reconcile: bool, pinned: PinnedOperationLink,
             signed_bridge: Mapping[str, object], backend_event: Mapping[str, object]):
        try:
            logical, record, objects = self._prepare(pinned, signed_bridge, backend_event)
        except Exception:
            return CustodyResult(CustodyOutcome.REJECTED_BEFORE_IO)
        attempts = 0
        try:
            for role, name, data in objects:
                if reconcile:
                    location = self._objects.read_and_verify(name, data)
                else:
                    attempts += 1
                    location = self._objects.create_and_verify(name, data)
                # Do not accept a storage adapter's mismatched object reference.
                if location.get("name") != name or location.get("sha256") != sha256(data):
                    raise ValueError("Object reference mismatch")
                record[role + "_object"] = dict(location)
            raw = canonical_subject_v1(record)
        except Exception:
            return CustodyResult(CustodyOutcome.STORAGE_UNCERTAIN_NO_RETRY, logical,
                                 object_create_attempts=attempts)
        digest = sha256(raw)
        try:
            if reconcile:
                indexed = self._index.read(logical, raw)
            else:
                indexed = self._index.insert_once(logical, raw)
                if indexed == IndexOutcome.COMMITTED:
                    # Acknowledged COMMIT alone is insufficient: fresh connection.
                    indexed = self._index.read(logical, raw)
        except Exception:
            indexed = IndexOutcome.UNKNOWN
        if indexed == IndexOutcome.CONFLICT:
            result = CustodyOutcome.CONFLICT_NO_AUTHORITY
        elif indexed == IndexOutcome.PRESENT:
            result = (CustodyOutcome.PRESENT_VERIFIED_NO_AUTHORITY if reconcile
                      else CustodyOutcome.STORED_VERIFIED_NO_AUTHORITY)
        else:
            result = CustodyOutcome.INDEX_UNCERTAIN_NO_RETRY
        return CustodyResult(result, logical, digest, attempts, 0 if reconcile else 1)

    def store(self, *, pinned, signed_bridge, backend_event):
        return self._run(reconcile=False, pinned=pinned,
                         signed_bridge=signed_bridge, backend_event=backend_event)

    def reconcile(self, *, pinned, signed_bridge, backend_event):
        return self._run(reconcile=True, pinned=pinned,
                         signed_bridge=signed_bridge, backend_event=backend_event)
