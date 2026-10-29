"""F27-B05-T05/T06: OFFLINE evidence replay prototype; NOT product wired.

Two ES256 signatures are verified by the existing independent bridge before
preparing a logical replay claim. The SQLite storage model is test-only and
MUST NOT be substituted for Azure SQL or operation_dispatch_claims. Neither a
positive insert nor a signed bridge authorizes dispatch or certifies G4/G5.

Do not run against live databases. No Azure, Foundry, MCP, Key Vault, network,
credential, or real database connection is configured or imported here.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Any

from .mcp_authenticated_backend_bridge import (
    PinnedOperationLink,
    verify_offline_backend_association,
)
from .mcp_backend_evidence_contract import validate_evidence_envelope
from .mcp_receipt_trust import IndependentReceiptVerifier, canonical_subject_v1

_LOGICAL_DOMAIN = b"AI-SUPPORT-F27-B05-ATTESTED-EVIDENCE-V2-LOGICAL\x00"
_SUBJECT_DOMAIN = b"AI-SUPPORT-F27-B05-ATTESTED-EVIDENCE-V2-SUBJECT\x00"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_PROOF = re.compile(r"es256:v1:([0-9a-f]{64}):[A-Za-z0-9_-]{86}\Z", re.ASCII)


class EvidencePreparationRejected(ValueError):
    """OFFLINE inputs do not establish even a signed association."""


class EvidenceStorageUnavailable(RuntimeError):
    """No reliable SQLite decision. Never retry dispatch."""


class OfflineEvidenceResult(StrEnum):
    NEW_OFFLINE_NO_AUTHORITY = "NEW_OFFLINE_NO_AUTHORITY"
    DUPLICATE_OFFLINE_NO_AUTHORITY = "DUPLICATE_OFFLINE_NO_AUTHORITY"
    CONFLICT_REJECTED = "CONFLICT_REJECTED"
    COMMIT_OUTCOME_UNKNOWN = "COMMIT_OUTCOME_UNKNOWN"
    CONFIRMED_PRESENT_NO_AUTHORITY = "CONFIRMED_PRESENT_NO_AUTHORITY"
    ABSENT_UNCERTAIN_NO_RETRY = "ABSENT_UNCERTAIN_NO_RETRY"


@dataclass(frozen=True)
class OfflinePreparedEvidenceV2:
    """Only content digest and identifiers. NOT a LIVE attestation capability.

    This dataclass is not an unforgeable security token. LIVE consumers must
    perform cryptographic verification again at their own trust boundary.
    """
    scope: str
    issuer: str
    domain: str
    operation_id: str
    workflow_id: str
    backend_event_id: str
    backend_request_id: str
    bridge_id: str
    approval_state: str
    logical_sha256: str
    subject_sha256: str
    backend_kid: str
    attestor_kid: str
    schema_version: str = "2.0-offline"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not str or self.schema_version != "2.0-offline":
            raise EvidencePreparationRejected("Unsupported evidence version")
        for name in ("scope", "issuer", "domain", "operation_id", "workflow_id",
                     "backend_event_id", "backend_request_id", "bridge_id"):
            item = getattr(self, name)
            if type(item) is not str or not item or len(item) > 256 or "\x00" in item:
                raise EvidencePreparationRejected("Invalid evidence identity field")
        if self.approval_state not in ("PENDING", "APPROVED", "DENIED"):
            raise EvidencePreparationRejected("Invalid approval state")
        for name in ("logical_sha256", "subject_sha256", "backend_kid", "attestor_kid"):
            if type(getattr(self, name)) is not str or not _DIGEST.fullmatch(getattr(self, name)):
                raise EvidencePreparationRejected("Invalid hash/fingerprint")
        if self.backend_kid == self.attestor_kid:
            raise EvidencePreparationRejected("Independent keys required")


def _copy_signed_record(raw: Mapping[str, object]) -> dict[str, object]:
    """Snapshot the only allowed nested structure before external callbacks."""
    if not isinstance(raw, Mapping):
        raise EvidencePreparationRejected("Signed record must be mapping")
    snapshot = dict(raw)
    receipt = snapshot.get("source_receipt")
    if not isinstance(receipt, Mapping):
        raise EvidencePreparationRejected("Missing receipt")
    snapshot["source_receipt"] = dict(receipt)
    return snapshot


def prepare_offline_backend_evidence_v2(
    *, pinned: PinnedOperationLink, signed_bridge: Mapping[str, object],
    backend_event: Mapping[str, object],
    bridge_verifier: IndependentReceiptVerifier,
    backend_verifier: IndependentReceiptVerifier,
) -> OfflinePreparedEvidenceV2:
    """Validate exact signed association and derive signature-independent IDs.

    This is an independent v2 *candidate*, not a new entrypoint for v1's
    verify_backend_evidence. It never returns a G4/G5 or authorization claim.
    """
    try:
        bridge = _copy_signed_record(signed_bridge)
        event = _copy_signed_record(backend_event)
        association = verify_offline_backend_association(
            pinned=pinned, signed_bridge=bridge, backend_event=event,
            bridge_verifier=bridge_verifier, backend_verifier=backend_verifier,
        )
        checked_event = validate_evidence_envelope(event)
        unsigned_bridge = {k: v for k, v in bridge.items() if k != "source_receipt"}
        unsigned_event = {k: v for k, v in checked_event.items() if k != "source_receipt"}
        # Signed payloads are canonicalized separately. The P1363 signature
        # representation and Key Vault key version do not enter these hashes.
        canonical_subject_v1(unsigned_bridge)
        canonical_subject_v1(unsigned_event)
        logical = canonical_subject_v1({
            "schema": "2.0-offline", "scope": pinned.trusted_scope,
            "issuer": "mcp_backend", "domain": "event:" + association.backend_event_type,
            "operation_id": pinned.operation_id,
            "event_id": association.backend_event_id,
        })
        subject = canonical_subject_v1({
            "bridge": unsigned_bridge, "backend_event": unsigned_event,
        })
        backend_proof = event["source_receipt"]["proof_id"]
        attestor_proof = bridge["source_receipt"]["proof_id"]
        bk = _PROOF.fullmatch(backend_proof)
        ak = _PROOF.fullmatch(attestor_proof)
        if not bk or not ak:
            raise EvidencePreparationRejected("Invalid signed key references")
        return OfflinePreparedEvidenceV2(
            scope=pinned.trusted_scope, issuer="mcp_backend",
            domain="event:" + association.backend_event_type,
            operation_id=pinned.operation_id, workflow_id=pinned.workflow_id,
            backend_event_id=association.backend_event_id,
            backend_request_id=association.backend_request_id,
            bridge_id=association.bridge_id,
            approval_state=association.approval_state,
            logical_sha256=hashlib.sha256(_LOGICAL_DOMAIN + logical).hexdigest(),
            subject_sha256=hashlib.sha256(_SUBJECT_DOMAIN + subject).hexdigest(),
            backend_kid=bk.group(1), attestor_kid=ak.group(1),
        )
    except EvidencePreparationRejected:
        raise
    except Exception as exc:
        raise EvidencePreparationRejected("Signed backend association not established") from exc


# SQLite is deliberately restricted to a local OFFLINE fixture. The actual
# Azure SQL schema/driver/cross-worker behavior has NOT been tested by it.
_CREATE_OFFLINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS offline_attested_evidence_claims (
    scope TEXT NOT NULL,
    issuer TEXT NOT NULL,
    domain TEXT NOT NULL,
    logical_sha256 TEXT NOT NULL,
    subject_sha256 TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    backend_event_id TEXT NOT NULL,
    backend_request_id TEXT NOT NULL,
    bridge_id TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    backend_kid TEXT NOT NULL,
    attestor_kid TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    PRIMARY KEY (scope, issuer, domain, logical_sha256),
    CHECK (length(logical_sha256) = 64),
    CHECK (length(subject_sha256) = 64)
)
"""
_INSERT = """
INSERT INTO offline_attested_evidence_claims
(scope, issuer, domain, logical_sha256, subject_sha256, operation_id,
 workflow_id, backend_event_id, backend_request_id, bridge_id, approval_state,
 backend_kid, attestor_kid, schema_version)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""
_SELECT = """
SELECT subject_sha256, operation_id, workflow_id, backend_event_id,
       backend_request_id, bridge_id, approval_state,
       backend_kid, attestor_kid, schema_version
FROM offline_attested_evidence_claims
WHERE scope=? AND issuer=? AND domain=? AND logical_sha256=?
"""


class SqliteOfflineEvidenceLedger:
    """Local deterministic model ONLY; not an Azure SQL adapter.

    Its record is *observational*. No method grants permission to dispatch or
    repeats external effects. Callers must independently verify the claim and
    its provenance before every storage operation in LIVE implementations.
    """

    def __init__(self, path: Path, *, connection_factory: Callable[[], Any] | None = None):
        if not isinstance(path, Path) or not path.is_absolute() or path.name in ("", ":memory:"):
            raise ValueError("Explicit absolute local SQLite fixture path required")
        self._path = path
        self._factory = connection_factory or (
            lambda: sqlite3.connect(str(path), timeout=10, isolation_level=None)
        )
        if not callable(self._factory):
            raise ValueError("Invalid connection factory")

    def initialize_offline_fixture(self) -> None:
        """Explicit DB creation. Never called by the constructor."""
        with sqlite3.connect(str(self._path), timeout=10) as conn:
            conn.execute(_CREATE_OFFLINE_SCHEMA)

    @staticmethod
    def _key(claim: OfflinePreparedEvidenceV2) -> tuple[str, ...]:
        return claim.scope, claim.issuer, claim.domain, claim.logical_sha256

    @staticmethod
    def _details(claim: OfflinePreparedEvidenceV2) -> tuple[str, ...]:
        return (claim.subject_sha256, claim.operation_id, claim.workflow_id,
                claim.backend_event_id, claim.backend_request_id,
                claim.bridge_id, claim.approval_state, claim.backend_kid,
                claim.attestor_kid, claim.schema_version)

    @staticmethod
    def _require_claim(claim: OfflinePreparedEvidenceV2) -> None:
        if type(claim) is not OfflinePreparedEvidenceV2:
            raise EvidencePreparationRejected("Explicit OFFLINE prepared claim required")
        # Re-check the shape; dataclass instance is not a trust certificate.
        claim.__post_init__()

    def _open(self):
        try:
            return self._factory()
        except Exception as exc:
            raise EvidenceStorageUnavailable("Cannot open OFFLINE evidence store") from exc

    def observe(self, claim: OfflinePreparedEvidenceV2) -> OfflineEvidenceResult:
        """One atomic unique INSERT. No I/O other than local SQLite fixture.

        Any exception during COMMIT is conservatively UNKNOWN, even if SQLite
        actually committed; call reconcile_unknown on a *fresh connection*.
        No blind retry, UPDATE, deletion, dispatch, or approval is allowed.
        """
        self._require_claim(claim)
        conn = self._open()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(_INSERT, (*self._key(claim), *self._details(claim)))
            except sqlite3.IntegrityError as exc:
                # Never equate any generic CHECK violation with a duplicate.
                if getattr(exc, "sqlite_errorcode", None) not in (
                    sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
                    sqlite3.SQLITE_CONSTRAINT_UNIQUE,
                ):
                    raise
                row = conn.execute(_SELECT, self._key(claim)).fetchone()
                if row is None:
                    raise EvidenceStorageUnavailable("Unique conflict without matching key") from exc
                decision = (OfflineEvidenceResult.DUPLICATE_OFFLINE_NO_AUTHORITY
                            if tuple(row) == self._details(claim)
                            else OfflineEvidenceResult.CONFLICT_REJECTED)
                try:
                    conn.commit()
                except Exception:
                    return OfflineEvidenceResult.COMMIT_OUTCOME_UNKNOWN
                return decision
            try:
                conn.commit()
            except Exception:
                return OfflineEvidenceResult.COMMIT_OUTCOME_UNKNOWN
            return OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY
        except EvidenceStorageUnavailable:
            raise
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            raise EvidenceStorageUnavailable("No reliable OFFLINE insert decision") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def reconcile_unknown(self, claim: OfflinePreparedEvidenceV2) -> OfflineEvidenceResult:
        """Separate fresh read. Missing row means UNKNOWN, never permission to retry."""
        self._require_claim(claim)
        conn = self._open()
        try:
            row = conn.execute(_SELECT, self._key(claim)).fetchone()
            if row is None:
                return OfflineEvidenceResult.ABSENT_UNCERTAIN_NO_RETRY
            if tuple(row) != self._details(claim):
                return OfflineEvidenceResult.CONFLICT_REJECTED
            return OfflineEvidenceResult.CONFIRMED_PRESENT_NO_AUTHORITY
        except Exception as exc:
            raise EvidenceStorageUnavailable("Uncertain outcome remains unresolved") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass
