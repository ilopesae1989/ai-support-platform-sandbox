"""F27.3-R16I: offline validation of independent MCP backend evidence.

Pure contract/verifier.  It does not produce attestations, acquire credentials,
call an agent, contact Azure/MCP, or authorize any operation.  Its injected
``verify_receipt`` function MUST be independently trusted by the caller; an
untrusted Boolean adapter is insufficient to certify a LIVE backend.

Positive results describe only the supplied, *externally attested* evidence.
A synthetic receipt checker can exercise this code, never establish LIVE facts.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from types import MappingProxyType
import re
from typing import Any


NOT_CERTIFIED = "NOT_CERTIFIED"
CONTRADICTION = "CONTRADICTION"
DISPATCH_OBSERVED = "DISPATCH_OBSERVED"
VERIFIED_NO_GROUP_LIST_DISPATCH_DURING_PENDING = (
    "VERIFIED_NO_GROUP_LIST_DISPATCH_DURING_PENDING"
)

_SCHEMA = "1.0"
_EVENT_OWNERS: dict[str, frozenset[str]] = {
    "OPERATION_AUTHORITY_VALIDATED": frozenset({"python_governor"}),
    "MCP_APPROVAL_PENDING": frozenset({"foundry_adapter", "python_governor"}),
    "MCP_APPROVAL_DECIDED": frozenset({"python_governor", "foundry_adapter"}),
    "MCP_HTTP_AUTH_EVALUATED": frozenset({"mcp_backend"}),
    "MCP_TOOL_DISPATCH_STARTED": frozenset({"mcp_backend"}),
    "MCP_TOOL_DISPATCH_FINISHED": frozenset({"mcp_backend"}),
    "OPERATION_EVIDENCE_COMMITTED": frozenset({"evidence_store", "python_governor"}),
}
_COMMON_FIELDS = frozenset({
    "schema_version", "event_type", "event_id", "source_component",
    "producer_instance_id", "captured_at_utc", "ingested_at_utc", "source_receipt",
})
_TOOL_FIELDS = frozenset({
    "backend_revision_fingerprint", "image_fingerprint", "backend_request_id",
    "tool_name", "arguments_fingerprint",
})
_OPERATION_ID_FIELDS = frozenset({
    "operation_id", "workflow_id", "capability_id", "agent_name",
    "agent_version", "server_label", "tool_name", "arguments_fingerprint",
    "response_id", "approval_request_id", "approved", "human_approval_id",
})
_AUTH_FIELDS = frozenset({
    "auth_result", "issuer_valid", "tenant_valid", "audience_valid",
    "lifetime_valid", "role_or_scope_valid", "principal_fingerprint",
})
_DISPATCH_FIELDS = frozenset({"dispatch_stage", "status"})
_ALLOWED_FIELDS = {
    "OPERATION_AUTHORITY_VALIDATED": _COMMON_FIELDS | _OPERATION_ID_FIELDS,
    "MCP_APPROVAL_PENDING": _COMMON_FIELDS | _OPERATION_ID_FIELDS,
    "MCP_APPROVAL_DECIDED": _COMMON_FIELDS | _OPERATION_ID_FIELDS,
    "MCP_HTTP_AUTH_EVALUATED": _COMMON_FIELDS | _TOOL_FIELDS | _AUTH_FIELDS,
    "MCP_TOOL_DISPATCH_STARTED": _COMMON_FIELDS | _TOOL_FIELDS | _DISPATCH_FIELDS,
    "MCP_TOOL_DISPATCH_FINISHED": _COMMON_FIELDS | _TOOL_FIELDS | _DISPATCH_FIELDS,
    "OPERATION_EVIDENCE_COMMITTED": _COMMON_FIELDS | _OPERATION_ID_FIELDS,
}
_HMAC = re.compile(r"hmac:[A-Za-z0-9][A-Za-z0-9._:\-]{0,255}\Z", re.ASCII)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,255}\Z", re.ASCII)
_UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z\Z", re.ASCII)


def _string(value: object, *, fingerprint: bool = False) -> bool:
    return isinstance(value, str) and bool((_HMAC if fingerprint else _ID).fullmatch(value))


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        raise ValueError("Timestamp must be an explicit UTC ISO-8601 timestamp")
    try:
        stamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid UTC timestamp") from exc
    if stamp.tzinfo != timezone.utc:
        raise ValueError("Timestamp is not UTC")
    return stamp


def _receipt_shape(receipt: object) -> bool:
    return (
        isinstance(receipt, Mapping)
        and set(receipt) == {"proof_id", "issuer"}
        and _string(receipt.get("proof_id"))
        and _string(receipt.get("issuer"))
    )


def _immutable_copy(value: Any) -> Any:
    """Return an immutable snapshot to prevent post-validation mutation."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _immutable_copy(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_immutable_copy(item) for item in value)
    return value


def validate_evidence_envelope(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Validate a single opaque, privacy-restricted event, not its authenticity.

    Unknown keys are rejected to avoid inadvertently persisting raw JWTs,
    arguments, results, HTTP headers, or signed URLs.  This is a *shape* check,
    not a signature check.  The separate receipt verifier establishes trust.
    """
    if not isinstance(raw, Mapping):
        raise ValueError("Evidence event must be a mapping")
    kind = raw.get("event_type")
    if not isinstance(kind, str) or kind not in _EVENT_OWNERS:
        raise ValueError("Unknown event type")
    if raw.get("schema_version") != _SCHEMA:
        raise ValueError("Unsupported evidence schema")
    if not set(raw).issubset(_ALLOWED_FIELDS[kind]) or not _COMMON_FIELDS.issubset(raw):
        raise ValueError("Unknown or missing event fields")
    owner = raw.get("source_component")
    if not isinstance(owner, str) or owner not in _EVENT_OWNERS[kind]:
        raise ValueError("Invalid event producer")
    for field in ("event_id", "producer_instance_id"):
        if not _string(raw.get(field)):
            raise ValueError("Invalid event identity")
    if not _receipt_shape(raw.get("source_receipt")):
        raise ValueError("Invalid receipt shape")
    if raw["source_receipt"]["issuer"] != owner:
        raise ValueError("Receipt/producer mismatch")
    if _utc(raw.get("ingested_at_utc")) < _utc(raw.get("captured_at_utc")):
        raise ValueError("Ingestion precedes capture")

    for key in _OPERATION_ID_FIELDS & raw.keys():
        if key == "approved":
            if type(raw[key]) is not bool:
                raise ValueError("Approval decision must be Boolean")
        elif not _string(raw[key], fingerprint=(key == "arguments_fingerprint")):
            raise ValueError("Invalid operation identity")
    if kind in {"MCP_HTTP_AUTH_EVALUATED", "MCP_TOOL_DISPATCH_STARTED", "MCP_TOOL_DISPATCH_FINISHED"}:
        if not _TOOL_FIELDS.issubset(raw):
            raise ValueError("Missing backend command identity")
        for key in _TOOL_FIELDS:
            if not _string(raw[key], fingerprint=key.endswith("fingerprint")):
                raise ValueError("Invalid backend command identity")
    if kind == "MCP_HTTP_AUTH_EVALUATED":
        if not _AUTH_FIELDS.issubset(raw):
            raise ValueError("Missing JWT evaluation fields")
        if not isinstance(raw.get("auth_result"), str) or raw["auth_result"] not in {"ACCEPT", "DENY"}:
            raise ValueError("Unknown JWT decision")
        for field in _AUTH_FIELDS - {"auth_result", "principal_fingerprint"}:
            if type(raw[field]) is not bool:
                raise ValueError("JWT evaluation flag must be Boolean")
        if not _string(raw["principal_fingerprint"], fingerprint=True):
            raise ValueError("Principal fingerprint must be keyed")
    elif kind in {"MCP_TOOL_DISPATCH_STARTED", "MCP_TOOL_DISPATCH_FINISHED"}:
        expected = "HANDLER_ENTERED" if kind.endswith("STARTED") else "HANDLER_FINISHED"
        if raw.get("dispatch_stage") != expected:
            raise ValueError("Invalid handler dispatch stage")
        if kind.endswith("FINISHED") and raw.get("status") not in {"SUCCESS", "ERROR"}:
            raise ValueError("Missing or invalid completion status")
        if kind.endswith("STARTED") and "status" in raw:
            raise ValueError("Started event cannot declare completion")
    return _immutable_copy(raw)


def _plain(value: Any) -> Any:
    """Copy an already validated snapshot to basic Python values for signing."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _trusted(
    record: Mapping[str, Any], verifier: Callable[..., object],
    issuer: str, domain: str,
) -> bool:
    """Verify an *external* domain-bound attestation over the whole record.

    The injected verifier MUST bind issuer, domain, and every byte of the
    canonicalized subject, and MUST be independent of the claim producer.
    No legacy receipt-only positional verifier is accepted.  Returning True
    is a caller responsibility, NOT evidence of an actual trusted sensor.
    """
    receipt = record.get("source_receipt")
    if not _receipt_shape(receipt) or receipt["issuer"] != issuer:
        return False
    subject = {key: _plain(val) for key, val in record.items()
               if key != "source_receipt"}
    try:
        return verifier(dict(receipt), subject_kind=domain, subject=subject) is True
    except Exception:  # Fail closed on verifier mismatch, timeout or error.
        return False


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _events(value: object, verifier: Callable[..., object]) -> list[Mapping[str, Any]] | None:
    if not isinstance(value, (list, tuple)) or len(value) > 1000:
        return None
    result: list[Mapping[str, Any]] = []
    for item in value:
        try:
            event = validate_evidence_envelope(item)
        except (ValueError, TypeError):
            return None
        # Verify precisely the validated snapshot, never a mutable raw object.
        if not _trusted(event, verifier, event["source_component"],
                        "event:" + event["event_type"]):
            return None
        result.append(event)
    return result


def _matching_operation_fields(
    event: Mapping[str, Any], operation: Mapping[str, Any]
) -> bool:
    for field in ("operation_id", "workflow_id", "capability_id", "agent_name",
                  "agent_version", "server_label", "tool_name", "arguments_fingerprint",
                  "response_id", "approval_request_id"):
        if field in event and event[field] != operation.get(field):
            return False
    return True


def _integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _covered(
    coverage: Mapping[str, Any], operation: Mapping[str, Any],
    provenance: Mapping[str, Any], verifier: Callable[..., object],
) -> bool:
    if not _trusted(coverage, verifier, "coverage_sensor", "coverage"):
        return False
    if (coverage.get("sensor_enabled") is not True
            or coverage.get("calibration_positive") is not True
            or coverage.get("store_immutable") is not True
            or coverage.get("sampling_ratio") != 1.0
            or type(coverage.get("sampling_ratio")) not in (float, int)
            or coverage.get("hook") != "GroupListCommand.ExecuteAsync"):
        return False
    for key in ("emitted_count", "ingested_count", "dropped_count", "gap_count"):
        if not _integer(coverage.get(key)):
            return False
    if any(coverage[k] != 0 for k in ("emitted_count", "ingested_count", "dropped_count", "gap_count")):
        return False
    replicas = coverage.get("replica_ids")
    expected = coverage.get("expected_replica_ids")
    if (not isinstance(replicas, (list, tuple)) or not isinstance(expected, (list, tuple))
            or not replicas or any(not _string(x) for x in replicas + expected)
            or len(replicas) != len(set(replicas))
            or len(expected) != len(set(expected)) or set(replicas) != set(expected)):
        return False
    if (coverage.get("calibration_revision_fingerprint") != provenance.get("revision_fingerprint")
            or coverage.get("backend_revision_fingerprint") != provenance.get("revision_fingerprint")
            or coverage.get("image_fingerprint") != provenance.get("image_fingerprint")):
        return False
    try:
        w_start = _utc(operation.get("window_start_utc"))
        w_end = _utc(operation.get("window_end_utc"))
        start = _utc(coverage.get("start_utc"))
        end = _utc(coverage.get("end_utc"))
        watermark = _utc(coverage.get("watermark_utc"))
    except ValueError:
        return False
    return w_start < w_end and start <= w_start and end >= w_end and watermark > w_end


def verify_backend_evidence(
    bundle: Mapping[str, object], *, verify_receipt: Callable[..., object]
) -> str:
    """Classify *attested* offline evidence; never grant technical/human approval.

    A successful result is conditional on an injected, independent trust
    verifier and on externally produced coverage attestations.  In particular,
    a synthetic verifier never proves a live server did (or did not) dispatch.
    """
    if not isinstance(bundle, Mapping) or not callable(verify_receipt):
        return NOT_CERTIFIED
    # Defensive snapshot before an injected verifier can mutate caller input.
    op = _mapping(_immutable_copy(bundle.get("operation")))
    corr = _mapping(_immutable_copy(bundle.get("correlation")))
    provenance = _mapping(_immutable_copy(bundle.get("backend_provenance")))
    coverage = _mapping(_immutable_copy(bundle.get("coverage")))
    if op is None or not _trusted(op, verify_receipt, "python_governor", "operation"):
        return NOT_CERTIFIED
    if not all(_string(op.get(x), fingerprint=x == "arguments_fingerprint") for x in (
        "operation_id", "workflow_id", "capability_id", "agent_name", "agent_version",
        "server_label", "tool_name", "arguments_fingerprint", "response_id", "approval_request_id"
    )):
        return NOT_CERTIFIED
    if op["response_id"] == op["approval_request_id"]:
        return CONTRADICTION
    if op["tool_name"] != "group_list" or op["capability_id"] != "azure.resource_group.list":
        return NOT_CERTIFIED
    if op.get("approval_state") not in {"PENDING", "APPROVED", "DENIED", "TIMEOUT_UNCERTAIN"}:
        return NOT_CERTIFIED
    try:
        window_start = _utc(op.get("window_start_utc"))
        window_end = _utc(op.get("window_end_utc"))
    except ValueError:
        return NOT_CERTIFIED
    if window_start >= window_end:
        return NOT_CERTIFIED
    if op.get("outgoing_identity") is not None or "outgoing_identity" in bundle:
        # A declaration is not an effective JWT or a trusted signer attestation.
        return NOT_CERTIFIED

    # Never infer trust from issuer labels or the mere existence of a receipt.
    consumers = _events(bundle.get("consumer_events"), verify_receipt)
    backends = _events(bundle.get("backend_events"), verify_receipt)
    if consumers is None or backends is None:
        return NOT_CERTIFIED
    # Receipt-backed events may not be repurposed from another time window.
    # Ingestion can lag; only the source capture time is bounded here.
    for event in consumers + backends:
        if not window_start <= _utc(event["captured_at_utc"]) <= window_end:
            return NOT_CERTIFIED
    if not any(e["event_type"] == "OPERATION_AUTHORITY_VALIDATED" for e in consumers):
        return NOT_CERTIFIED
    pending = [e for e in consumers if e["event_type"] == "MCP_APPROVAL_PENDING"]
    if len(pending) != 1:
        return NOT_CERTIFIED
    if any(not _matching_operation_fields(e, op) for e in consumers):
        return CONTRADICTION
    decided = [e for e in consumers if e["event_type"] == "MCP_APPROVAL_DECIDED"]
    if op.get("approval_state") == "TIMEOUT_UNCERTAIN":
        return NOT_CERTIFIED
    if op.get("approval_state") == "APPROVED":
        if op.get("technical_approval") is not True or not _string(op.get("human_approval_id")):
            return NOT_CERTIFIED
        if len(decided) != 1 or decided[0].get("approved") is not True:
            return NOT_CERTIFIED
    elif op.get("approval_state") == "PENDING":
        if decided:
            return CONTRADICTION
        if op.get("technical_approval") is not None or op.get("human_approval_id") is not None:
            return NOT_CERTIFIED
    elif op.get("approval_state") == "DENIED":
        if op.get("technical_approval") is not False:
            return NOT_CERTIFIED

    if corr is None or provenance is None or coverage is None:
        return NOT_CERTIFIED
    if corr.get("method") != "authenticated_provider_link" or corr.get("replay_protected") is not True:
        return NOT_CERTIFIED
    if not _trusted(corr, verify_receipt, "mcp_backend", "correlation"):
        return NOT_CERTIFIED
    if (corr.get("exact_operation_id") != op["operation_id"]
            or corr.get("linked_approval_request_id") != op["approval_request_id"]
            or corr.get("linked_response_id") != op["response_id"]):
        return CONTRADICTION
    if (provenance.get("attested_release") is not True
            or provenance.get("attested_handler_hook") is not True
            or not _trusted(provenance, verify_receipt, "mcp_backend", "backend_provenance")):
        return NOT_CERTIFIED
    rev = provenance.get("revision_fingerprint")
    img = provenance.get("image_fingerprint")
    if not _string(rev, fingerprint=True) or not _string(img, fingerprint=True):
        return NOT_CERTIFIED
    if corr.get("backend_revision_fingerprint") != rev:
        return CONTRADICTION
    if (coverage.get("backend_revision_fingerprint") != rev
            or coverage.get("image_fingerprint") != img):
        return NOT_CERTIFIED

    # Discriminate actual backend handler-entry events from SDK diagnostic spans.
    # A ToolExecuted span alone is NOT evidence that ExecuteAsync was entered.
    unique: dict[str, Mapping[str, Any]] = {}
    for event in backends:
        eid = event["event_id"]
        if eid in unique:
            if unique[eid] != event:
                return CONTRADICTION
        else:
            unique[eid] = event
    starts: list[Mapping[str, Any]] = []
    finishes: list[Mapping[str, Any]] = []
    denies: set[str] = set()
    for event in unique.values():
        if (event.get("backend_revision_fingerprint") != rev
                or event.get("image_fingerprint") != img
                or event.get("arguments_fingerprint") != op["arguments_fingerprint"]
                or event.get("tool_name") != op["tool_name"]):
            return CONTRADICTION
        kind = event["event_type"]
        if kind == "MCP_HTTP_AUTH_EVALUATED":
            if event["auth_result"] == "ACCEPT" and not all(
                event[f] for f in ("issuer_valid", "tenant_valid", "audience_valid",
                                   "lifetime_valid", "role_or_scope_valid")
            ):
                return CONTRADICTION
            if event["auth_result"] == "DENY":
                denies.add(event["backend_request_id"])
        elif kind == "MCP_TOOL_DISPATCH_STARTED":
            starts.append(event)
        elif kind == "MCP_TOOL_DISPATCH_FINISHED":
            finishes.append(event)
    if len(starts) > 1:
        # One approval may not silently contain two independently emitted starts.
        return CONTRADICTION
    if finishes:
        start_requests = {event["backend_request_id"] for event in starts}
        if len(finishes) > len(starts) or any(e["backend_request_id"] not in start_requests for e in finishes):
            return CONTRADICTION
    if any(event["backend_request_id"] in denies for event in starts):
        return CONTRADICTION
    # The backend request identity MUST be linked by the separately attested
    # correlation record. A matching timestamp, tool or operation label alone
    # cannot join Foundry approval with a backend execution.
    linked_request = corr.get("linked_backend_request_id")
    if backends and not _string(linked_request):
        return NOT_CERTIFIED
    if backends and any(e.get("backend_request_id") != linked_request for e in backends):
        return NOT_CERTIFIED
    if linked_request is not None and not _string(linked_request):
        return NOT_CERTIFIED

    if starts and op["approval_state"] == "DENIED":
        return CONTRADICTION
    if starts:
        # Only an observed event, not proof of safe/authorized dispatch or Azure effects.
        return DISPATCH_OBSERVED
    if op["approval_state"] != "PENDING":
        return NOT_CERTIFIED
    if not _covered(coverage, op, provenance, verify_receipt):
        return NOT_CERTIFIED
    return VERIFIED_NO_GROUP_LIST_DISPATCH_DURING_PENDING
