"""F27-B05-T05: purely OFFLINE authenticated backend-event association.

Not product-wired. Verifies two independently pinned ES256 receipt issuers:
  1) a correlation attestor which asserts a provider-authenticated join; and
  2) the backend which signs its observed handler-entry/auth event.

It does not authenticate the real provider transport, establish runtime signer
isolation, provide durable replay protection, authorize dispatch, assert
technical success, or certify G4/G5. Those require independent LIVE evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import re

from .mcp_backend_evidence_contract import validate_evidence_envelope
from .mcp_receipt_trust import IndependentReceiptVerifier, canonical_subject_v1

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,255}\Z", re.ASCII)
_FP = re.compile(r"hmac:[A-Za-z0-9][A-Za-z0-9._:\-]{0,255}\Z", re.ASCII)
_UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z\Z", re.ASCII)
_BRIDGE_ISSUER = "correlation_attestor"
_BACKEND_ISSUER = "mcp_backend"
_BRIDGE_DOMAIN = "correlation:authenticated_backend_request"
_BACKEND_KINDS = frozenset({"MCP_HTTP_AUTH_EVALUATED", "MCP_TOOL_DISPATCH_STARTED", "MCP_TOOL_DISPATCH_FINISHED"})
_LINK_FIELDS = frozenset({
    "schema_version", "bridge_id", "method", "exact_operation_id", "workflow_id",
    "approval_state", "human_approval_id", "technical_approval", "linked_response_id",
    "linked_approval_request_id", "linked_backend_request_id", "linked_backend_event_id",
    "agent_name", "agent_version", "server_label", "tool_name", "capability_id",
    "arguments_fingerprint", "backend_revision_fingerprint", "image_fingerprint",
    "observed_at_utc", "source_receipt",
})


class BackendBridgeNotCertified(ValueError):
    """A signed pair cannot establish the claimed OFFLINE association."""


def _id(value: object, *, fingerprint: bool = False) -> bool:
    return type(value) is str and bool((_FP if fingerprint else _ID).fullmatch(value))


def _utc(value: object) -> datetime:
    if type(value) is not str or not _UTC.fullmatch(value):
        raise BackendBridgeNotCertified("Time must be canonical UTC with Z")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise BackendBridgeNotCertified("Invalid UTC time") from exc
    if result.tzinfo != timezone.utc:
        raise BackendBridgeNotCertified("Non-UTC time")
    return result


@dataclass(frozen=True)
class PinnedOperationLink:
    """Expected values supplied by an external governor, NEVER from the link."""

    trusted_scope: str
    operation_id: str
    workflow_id: str
    approval_state: str
    human_approval_id: str | None
    technical_approval: bool | None
    response_id: str
    approval_request_id: str
    agent_name: str
    agent_version: str
    server_label: str
    tool_name: str
    capability_id: str
    arguments_fingerprint: str
    backend_revision_fingerprint: str
    image_fingerprint: str
    window_start_utc: str
    window_end_utc: str

    def __post_init__(self) -> None:
        try:
            keys = (
                self.operation_id, self.workflow_id, self.response_id,
                self.approval_request_id, self.agent_name, self.agent_version,
                self.server_label, self.tool_name, self.capability_id,
            )
            if any(not _id(item) for item in keys):
                raise BackendBridgeNotCertified("Invalid governor-owned operation identity")
            if any(not _id(item, fingerprint=True) for item in (
                self.arguments_fingerprint, self.backend_revision_fingerprint,
                self.image_fingerprint,
            )):
                raise BackendBridgeNotCertified("Invalid pinned fingerprint")
            if self.approval_state not in ("PENDING", "APPROVED", "DENIED"):
                raise BackendBridgeNotCertified("Invalid approval state")
            if self.human_approval_id is not None and not _id(self.human_approval_id):
                raise BackendBridgeNotCertified("Invalid human approval ID")
            if self.approval_state == "APPROVED" and (self.human_approval_id is None or self.technical_approval is not True):
                raise BackendBridgeNotCertified("Approved state requires separate human and MCP approvals")
            if self.approval_state == "PENDING" and self.technical_approval is not None:
                raise BackendBridgeNotCertified("PENDING cannot carry an MCP decision")
            if self.approval_state == "DENIED" and self.technical_approval is not False:
                raise BackendBridgeNotCertified("DENIED must carry a negative MCP decision")
            if (not isinstance(self.trusted_scope, str)
                    or len(self.trusted_scope) < 8):
                raise BackendBridgeNotCertified("Missing independently pinned scope")
            # Validate scope under the actual restrictive ES256 profile.
            from .mcp_receipt_trust import signature_preimage_v1
            signature_preimage_v1(
                scope=self.trusted_scope, issuer=_BRIDGE_ISSUER,
                domain=_BRIDGE_DOMAIN, kid="0" * 64, subject={"check": True},
            )
            if _utc(self.window_start_utc) >= _utc(self.window_end_utc):
                raise BackendBridgeNotCertified("Invalid observation window")
        except BackendBridgeNotCertified:
            raise
        except (TypeError, ValueError) as exc:
            raise BackendBridgeNotCertified("Invalid pinned operation") from exc


@dataclass(frozen=True)
class OfflineBackendAssociation:
    """Signed association only. NO approval/dispatch/coverage certification."""

    operation_id: str
    workflow_id: str
    approval_state: str
    human_approval_id: str | None
    technical_approval: bool | None
    approval_request_id: str
    response_id: str
    backend_request_id: str
    backend_event_id: str
    backend_event_type: str
    bridge_id: str
    tool_name: str
    arguments_fingerprint: str
    backend_revision_fingerprint: str
    image_fingerprint: str


def verify_offline_backend_association(
    *,
    pinned: PinnedOperationLink,
    signed_bridge: Mapping[str, object],
    backend_event: Mapping[str, object],
    bridge_verifier: IndependentReceiptVerifier,
    backend_verifier: IndependentReceiptVerifier,
) -> OfflineBackendAssociation:
    """Check exact, separately signed bridge and backend event (no I/O).

    Bridge signature attests that its signer claims an authenticated linkage;
    only independent LIVE provenance can establish the claim's truth.
    A PENDING link with a handler event may indicate an unauthorized dispatch;
    it is NEVER silently interpreted as approval.
    """
    try:
        if type(pinned) is not PinnedOperationLink:
            raise BackendBridgeNotCertified("Pinned operation required")
        if (type(bridge_verifier) is not IndependentReceiptVerifier
                or type(backend_verifier) is not IndependentReceiptVerifier):
            raise BackendBridgeNotCertified("Explicit ES256 trust verifiers required")
        if (getattr(bridge_verifier, "_scope", None) != pinned.trusted_scope
                or getattr(backend_verifier, "_scope", None) != pinned.trusted_scope):
            raise BackendBridgeNotCertified("Untrusted verifier scope")
        if not isinstance(signed_bridge, Mapping) or set(signed_bridge) != _LINK_FIELDS:
            raise BackendBridgeNotCertified("Bridge schema is not exact")
        if (signed_bridge["schema_version"] != "1.0"
                or signed_bridge["method"] != "authenticated_provider_link"):
            raise BackendBridgeNotCertified("Unsupported link contract")
        if not _id(signed_bridge["bridge_id"]):
            raise BackendBridgeNotCertified("Invalid bridge ID")
        receipt = signed_bridge["source_receipt"]
        if (not isinstance(receipt, Mapping)
                or set(receipt) != {"issuer", "proof_id"}
                or receipt.get("issuer") != _BRIDGE_ISSUER):
            raise BackendBridgeNotCertified("Not an independent attestor receipt")
        b = validate_evidence_envelope(backend_event)
        if (b["event_type"] not in _BACKEND_KINDS
                or b["source_component"] != _BACKEND_ISSUER):
            raise BackendBridgeNotCertified("Not an MCP backend observation")
        backend_receipt = b["source_receipt"]
        if backend_receipt["issuer"] != _BACKEND_ISSUER:
            raise BackendBridgeNotCertified("Unexpected backend receipt issuer")
        # The two owners must have different public key fingerprints. Same key
        # under different labels is not independence even in this OFFLINE model.
        proof_a = receipt.get("proof_id")
        proof_b = backend_receipt.get("proof_id")
        if not (isinstance(proof_a, str) and isinstance(proof_b, str)
                and proof_a.startswith("es256:v1:")
                and proof_b.startswith("es256:v1:")
                and proof_a.split(":")[2] != proof_b.split(":")[2]):
            raise BackendBridgeNotCertified("Key separation not demonstrated")
        linked = {
            "exact_operation_id": pinned.operation_id,
            "workflow_id": pinned.workflow_id,
            "approval_state": pinned.approval_state,
            "human_approval_id": pinned.human_approval_id,
            "technical_approval": pinned.technical_approval,
            "linked_response_id": pinned.response_id,
            "linked_approval_request_id": pinned.approval_request_id,
            "agent_name": pinned.agent_name,
            "agent_version": pinned.agent_version,
            "server_label": pinned.server_label,
            "tool_name": pinned.tool_name,
            "capability_id": pinned.capability_id,
            "arguments_fingerprint": pinned.arguments_fingerprint,
            "backend_revision_fingerprint": pinned.backend_revision_fingerprint,
            "image_fingerprint": pinned.image_fingerprint,
        }
        if any(signed_bridge.get(k) != v or type(signed_bridge.get(k)) is not type(v)
               for k, v in linked.items()):
            raise BackendBridgeNotCertified("Bridge conflicts with pinned governor")
        if (signed_bridge["linked_backend_request_id"] != b["backend_request_id"]
                or signed_bridge["linked_backend_event_id"] != b["event_id"]
                or signed_bridge["tool_name"] != b["tool_name"]
                or signed_bridge["arguments_fingerprint"] != b["arguments_fingerprint"]
                or signed_bridge["backend_revision_fingerprint"] != b["backend_revision_fingerprint"]
                or signed_bridge["image_fingerprint"] != b["image_fingerprint"]):
            raise BackendBridgeNotCertified("Bridge/backend identity mismatch")
        start = _utc(pinned.window_start_utc)
        end = _utc(pinned.window_end_utc)
        if (not start <= _utc(b["captured_at_utc"]) <= end
                or not start <= _utc(signed_bridge["observed_at_utc"]) <= end):
            raise BackendBridgeNotCertified("Observation outside pinned window")
        # Reconstruct fresh ordinary dictionaries to avoid trusting mutable
        # input after normalization. Never read private keys from the receipt.
        link_subject = {k: v for k, v in signed_bridge.items() if k != "source_receipt"}
        canonical_subject_v1(link_subject)
        if bridge_verifier(dict(receipt), subject_kind=_BRIDGE_DOMAIN,
                           subject=link_subject) is not True:
            raise BackendBridgeNotCertified("Attestor signature invalid")
        backend_subject = {k: v for k, v in b.items() if k != "source_receipt"}
        canonical_subject_v1(backend_subject)
        if backend_verifier(dict(backend_receipt),
                            subject_kind="event:" + b["event_type"],
                            subject=backend_subject) is not True:
            raise BackendBridgeNotCertified("Backend signature invalid")
        return OfflineBackendAssociation(
            operation_id=pinned.operation_id,
            workflow_id=pinned.workflow_id,
            approval_state=pinned.approval_state,
            human_approval_id=pinned.human_approval_id,
            technical_approval=pinned.technical_approval,
            approval_request_id=pinned.approval_request_id,
            response_id=pinned.response_id,
            backend_request_id=b["backend_request_id"],
            backend_event_id=b["event_id"],
            backend_event_type=b["event_type"],
            bridge_id=signed_bridge["bridge_id"],
            tool_name=pinned.tool_name,
            arguments_fingerprint=pinned.arguments_fingerprint,
            backend_revision_fingerprint=pinned.backend_revision_fingerprint,
            image_fingerprint=pinned.image_fingerprint,
        )
    except BackendBridgeNotCertified:
        raise
    except Exception as exc:  # Fail closed on input/verifier errors.
        raise BackendBridgeNotCertified("Uncertified backend association") from exc
