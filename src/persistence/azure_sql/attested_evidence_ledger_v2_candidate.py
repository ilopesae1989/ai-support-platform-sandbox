"""F27-B05-T06: Azure SQL DB-API transaction CONTRACT, offline candidate.

NEVER wired into production. The only entry points take complete signed
backend+attestor inputs and re-run the OFFLINE trust predicate at each call.
Passing a forged OfflinePreparedEvidenceV2 instance is not supported.

No Azure, SQL driver, Key Vault, Foundry or MCP call is made by importing this
module. The injected connection factory is tested with fakes ONLY. Passing a
real Azure SQL factory requires a later explicit authorization and adapter
qualification. No dispatch or approval authority is produced by this code.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
import re
from typing import Any

from src.workflows.incident_resolution.mcp_attested_evidence_store_offline import (
    OfflinePreparedEvidenceV2, prepare_offline_backend_evidence_v2,
)
from src.workflows.incident_resolution.mcp_authenticated_backend_bridge import PinnedOperationLink
from src.workflows.incident_resolution.mcp_receipt_trust import IndependentReceiptVerifier


_EXPECTED_UNIQUE = "UQ_attested_evidence_logical_v2"
_DUPLICATE_NUMBER = re.compile(r"(?<![0-9])(?:2627|2601)(?![0-9])", re.ASCII)

# Exact table name and parameter set, never interpolated from untrusted input.
_INSERT = """
INSERT INTO dbo.attested_evidence_claims
(scope_id, issuer, evidence_domain, logical_sha256, subject_sha256,
 operation_id, workflow_id, backend_event_id, backend_request_id, bridge_id,
 approval_state, backend_kid, attestor_kid, schema_version)
VALUES
(%(scope_id)s, %(issuer)s, %(evidence_domain)s, %(logical_sha256)s,
 %(subject_sha256)s, %(operation_id)s, %(workflow_id)s, %(backend_event_id)s,
 %(backend_request_id)s, %(bridge_id)s, %(approval_state)s, %(backend_kid)s,
 %(attestor_kid)s, %(schema_version)s)
"""
_SELECT = """
SELECT subject_sha256, operation_id, workflow_id, backend_event_id,
       backend_request_id, bridge_id, approval_state,
       backend_kid, attestor_kid, schema_version
FROM dbo.attested_evidence_claims
WHERE scope_id = %(scope_id)s AND issuer = %(issuer)s
  AND evidence_domain = %(evidence_domain)s
  AND logical_sha256 = %(logical_sha256)s
"""


class CandidateSqlOutcome(StrEnum):
    NEW_OFFLINE_NO_AUTHORITY = "NEW_OFFLINE_NO_AUTHORITY"
    DUPLICATE_OFFLINE_NO_AUTHORITY = "DUPLICATE_OFFLINE_NO_AUTHORITY"
    PRESENT_OFFLINE_NO_AUTHORITY = "PRESENT_OFFLINE_NO_AUTHORITY"
    CONFLICT_FAIL_CLOSED = "CONFLICT_FAIL_CLOSED"
    COMMIT_OUTCOME_UNKNOWN = "COMMIT_OUTCOME_UNKNOWN"
    ABSENT_UNCERTAIN_NO_RETRY = "ABSENT_UNCERTAIN_NO_RETRY"
    STORAGE_FAILURE_NO_AUTHORITY = "STORAGE_FAILURE_NO_AUTHORITY"


def _params(claim: OfflinePreparedEvidenceV2) -> dict[str, Any]:
    if type(claim) is not OfflinePreparedEvidenceV2:
        raise TypeError("Only an internally regenerated verified claim is admissible")
    claim.__post_init__()
    # Convert SHA-256 and key fingerprints to BINARY(32), not locale-collated text.
    return {
        "scope_id": claim.scope,
        "issuer": claim.issuer,
        "evidence_domain": claim.domain,
        "logical_sha256": bytes.fromhex(claim.logical_sha256),
        "subject_sha256": bytes.fromhex(claim.subject_sha256),
        "operation_id": claim.operation_id,
        "workflow_id": claim.workflow_id,
        "backend_event_id": claim.backend_event_id,
        "backend_request_id": claim.backend_request_id,
        "bridge_id": claim.bridge_id,
        "approval_state": claim.approval_state,
        "backend_kid": bytes.fromhex(claim.backend_kid),
        "attestor_kid": bytes.fromhex(claim.attestor_kid),
        "schema_version": claim.schema_version,
    }


def _read_params(p: Mapping[str, object]) -> dict[str, object]:
    return {k: p[k] for k in (
        "scope_id", "issuer", "evidence_domain", "logical_sha256"
    )}


def _expected_row(p: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(p[k] for k in (
        "subject_sha256", "operation_id", "workflow_id", "backend_event_id",
        "backend_request_id", "bridge_id", "approval_state", "backend_kid",
        "attestor_kid", "schema_version"
    ))


def _specific_unique_violation(error: Exception) -> bool:
    """Defensive heuristic only; real driver/localization needs qualification.

    The native duplicate error must name this exact unique index/constraint.
    An arbitrary IntegrityError, CHECK error or deadlock is NEVER a duplicate.
    """
    parts = tuple(str(a) for a in getattr(error, "args", ()))
    if not parts:
        return False
    msg = " ".join(parts)
    return (
        bool(_DUPLICATE_NUMBER.search(msg))
        and _EXPECTED_UNIQUE in msg
        and ("23000" in msg or "2627" in msg or "2601" in msg)
    )


def _close_silently(cursor: object, connection: object) -> None:
    for item in (cursor, connection):
        if item is None:
            continue
        try:
            item.close()
        except Exception:
            pass


class AzureSqlAttestedEvidenceV2OfflineCandidate:
    """Experimental DB-API semantic adapter; not runtime-integrated.

    The key properties are: independent re-verification before connection,
    exactly one INSERT attempt, conservative failed-commit classification and
    a fresh-connection read that never authorizes dispatch or retries INSERT.
    """

    def __init__(self, *, connection_factory: Callable[[], Any]) -> None:
        if not callable(connection_factory):
            raise TypeError("Explicit connection_factory required")
        self._factory = connection_factory

    @staticmethod
    def _prepare(
        *, pinned: PinnedOperationLink, signed_bridge: Mapping[str, object],
        backend_event: Mapping[str, object], bridge_verifier: IndependentReceiptVerifier,
        backend_verifier: IndependentReceiptVerifier,
    ) -> dict[str, Any]:
        # Cryptographic predicate, source provenance and exact pinned IDs are
        # re-evaluated; a caller cannot supply an arbitrary claim dataclass.
        return _params(prepare_offline_backend_evidence_v2(
            pinned=pinned, signed_bridge=signed_bridge,
            backend_event=backend_event, bridge_verifier=bridge_verifier,
            backend_verifier=backend_verifier,
        ))

    def _lookup(self, params: Mapping[str, object]) -> CandidateSqlOutcome:
        """Separate connection + read only; absence is ALWAYS uncertain."""
        connection = None
        cursor = None
        try:
            connection = self._factory()
            cursor = connection.cursor()
            cursor.execute(_SELECT, _read_params(params))
            first = cursor.fetchone()
            if first is None:
                return CandidateSqlOutcome.ABSENT_UNCERTAIN_NO_RETRY
            # A second row is impossible under the proposed SQL UNIQUE index.
            # Reject an inconsistent driver/schema rather than guessing.
            second = cursor.fetchone()
            if second is not None:
                return CandidateSqlOutcome.CONFLICT_FAIL_CLOSED
            return (
                CandidateSqlOutcome.PRESENT_OFFLINE_NO_AUTHORITY
                if tuple(first) == _expected_row(params)
                else CandidateSqlOutcome.CONFLICT_FAIL_CLOSED
            )
        except Exception:
            return CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY
        finally:
            _close_silently(cursor, connection)

    def observe_signed(
        self, *, pinned: PinnedOperationLink, signed_bridge: Mapping[str, object],
        backend_event: Mapping[str, object], bridge_verifier: IndependentReceiptVerifier,
        backend_verifier: IndependentReceiptVerifier,
    ) -> CandidateSqlOutcome:
        params = self._prepare(
            pinned=pinned, signed_bridge=signed_bridge,
            backend_event=backend_event, bridge_verifier=bridge_verifier,
            backend_verifier=backend_verifier,
        )
        connection = None
        cursor = None
        try:
            connection = self._factory()
            cursor = connection.cursor()
            try:
                cursor.execute(_INSERT, params)
            except Exception as error:
                try:
                    connection.rollback()
                except Exception:
                    return CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY
                if not _specific_unique_violation(error):
                    return CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY
                found = self._lookup(params)
                if found == CandidateSqlOutcome.PRESENT_OFFLINE_NO_AUTHORITY:
                    return CandidateSqlOutcome.DUPLICATE_OFFLINE_NO_AUTHORITY
                return found
            # Once COMMIT begins, even a rollback result cannot prove it failed.
            try:
                connection.commit()
            except Exception:
                return CandidateSqlOutcome.COMMIT_OUTCOME_UNKNOWN
            return CandidateSqlOutcome.NEW_OFFLINE_NO_AUTHORITY
        except Exception:
            return CandidateSqlOutcome.STORAGE_FAILURE_NO_AUTHORITY
        finally:
            _close_silently(cursor, connection)

    def reconcile_signed(
        self, *, pinned: PinnedOperationLink, signed_bridge: Mapping[str, object],
        backend_event: Mapping[str, object], bridge_verifier: IndependentReceiptVerifier,
        backend_verifier: IndependentReceiptVerifier,
    ) -> CandidateSqlOutcome:
        """After an unknown commit, ONE fresh SELECT; never retry INSERT."""
        return self._lookup(self._prepare(
            pinned=pinned, signed_bridge=signed_bridge,
            backend_event=backend_event, bridge_verifier=bridge_verifier,
            backend_verifier=backend_verifier,
        ))
