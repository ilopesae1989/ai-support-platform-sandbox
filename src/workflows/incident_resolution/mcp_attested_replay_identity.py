"""F27-B05-T05/T06: OFFLINE-only logical event identity from an ES256 receipt.

No credential acquisition, remote sign, Azure/MCP/Foundry invocation, I/O,
operation authorization, replay claim, persistence or G4/G5 certification.

The returned digest can be used as a UNIQUE candidate for a future atomic
persisted replay claim, but only after independently trusted signing roots,
producer isolation and capture of actual events have been established.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from types import MappingProxyType

from .mcp_backend_evidence_contract import validate_evidence_envelope
from .mcp_receipt_trust import (
    IndependentReceiptVerifier,
    UnsupportedEvidence,
    canonical_subject_v1,
    signature_preimage_v1,
)

_REPLAY_DOMAIN = b"AI-SUPPORT-F27-B05-LOGICAL-EVENT-V1\x00"


class ReplayIdentityNotCertified(ValueError):
    """Evidence is insufficient to derive a verified logical identity."""


@dataclass(frozen=True)
class OfflineReplayIdentity:
    """Immutable logical identity; NOT a durable replay claim or LIVE proof."""

    issuer: str
    domain: str
    operation_id: str
    event_id: str
    logical_sha256: str
    subject_sha256: str


def derive_offline_replay_identity(
    raw_event: Mapping[str, object],
    *,
    trusted_scope: str,
    expected_issuer: str,
    expected_event_type: str,
    expected_operation_id: str,
    verifier: IndependentReceiptVerifier,
) -> OfflineReplayIdentity:
    """Verify a signed event and derive identity independent of ECDSA signature.

    Expected values MUST come from the independent governor/approved config,
    not from the supplied event.  Events without an operation_id fail closed;
    an MCP handler event today only carries backend_request_id and must FIRST
    get an authenticated bridge before it can be mapped to an operation.

    This is an OFFLINE predicate. It does NOT attest the runtime isolation or
    enrollment of the verifier's public keys, nor persist the returned key.
    """
    if type(verifier) is not IndependentReceiptVerifier:
        raise ReplayIdentityNotCertified("IndependentReceiptVerifier required")
    # The verifier's pinned scope is part of the signature preimage. A caller
    # cannot derive a replay key for scope B from evidence signed in scope A.
    if getattr(verifier, "_scope", None) != trusted_scope:
        raise ReplayIdentityNotCertified("Trusted scope differs from verifier scope")
    if not isinstance(raw_event, Mapping):
        raise ReplayIdentityNotCertified("Event must be mapping")
    for name, value in (
        ("scope", trusted_scope), ("issuer", expected_issuer),
        ("kind", expected_event_type), ("operation", expected_operation_id),
    ):
        if type(value) is not str or not value:
            raise ReplayIdentityNotCertified(f"Missing expected {name}")
    try:
        # Immutable snapshot avoids callback-induced mutation of original input.
        snapshot = validate_evidence_envelope(raw_event)
        if (snapshot["source_component"] != expected_issuer
                or snapshot["event_type"] != expected_event_type
                or snapshot.get("operation_id") != expected_operation_id):
            raise ReplayIdentityNotCertified("Event identity conflicts with expected authority")
        domain = "event:" + expected_event_type
        issuer = snapshot["source_receipt"]["issuer"]
        if issuer != expected_issuer:
            raise ReplayIdentityNotCertified("Receipt/producer disagreement")
        subject = MappingProxyType({
            key: value for key, value in snapshot.items() if key != "source_receipt"
        })
        canonical = canonical_subject_v1(subject)
        # Reuse the existing signing context strict validator. Its output is
        # discarded: this module does not sign or create a receipt.
        signature_preimage_v1(
            scope=trusted_scope, issuer=expected_issuer, domain=domain,
            kid="0" * 64, subject=subject,
        )
        original_receipt = snapshot["source_receipt"]
        # Explicit copy, never input-owned mutable receipt.
        receipt = {
            "issuer": original_receipt["issuer"],
            "proof_id": original_receipt["proof_id"],
        }
        try:
            verified = verifier(receipt, subject_kind=domain, subject=subject)
        except Exception as exc:
            raise ReplayIdentityNotCertified("Verifier failed") from exc
        if verified is not True or canonical != canonical_subject_v1(subject):
            raise ReplayIdentityNotCertified("Untrusted or unstable event")
        logical = canonical_subject_v1({
            "scope": trusted_scope,
            "issuer": expected_issuer,
            "domain": domain,
            "operation_id": expected_operation_id,
            "event_id": snapshot["event_id"],
        })
    except ReplayIdentityNotCertified:
        raise
    except (ValueError, TypeError, KeyError, UnsupportedEvidence) as exc:
        raise ReplayIdentityNotCertified("Unsupported or malformed evidence") from exc

    return OfflineReplayIdentity(
        issuer=expected_issuer, domain=domain,
        operation_id=expected_operation_id, event_id=snapshot["event_id"],
        logical_sha256=hashlib.sha256(_REPLAY_DOMAIN + logical).hexdigest(),
        subject_sha256=hashlib.sha256(canonical).hexdigest(),
    )
