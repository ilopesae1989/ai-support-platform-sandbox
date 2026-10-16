"""F27.3-R16L strengthened R16K adversarial attestation tests.

These tests document verified fail-open situations in the existing R16I OFFLINE
contract: a receipt-only Boolean is insufficient to attest the covered payload,
request identity, calibration or immutable evidence. Synthetic only: no LIVE claim.
No subprocess, HTTP, cloud, filesystem writes, containers or agent invocations.

RED cases A01..A24 assert security behavior; they MUST fail by assertion against
R16I, not by import/collection errors, artificial failures or xfail markers.
G01..G04 retain fail-closed guards. A25..A26 are positive compatibility anchors
for the proposed payload-bound receipt verifier, not LIVE trust implementations.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import hmac
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_NAME = "src.workflows.incident_resolution.mcp_backend_evidence_contract"
PRODUCT_FILE = ROOT / "src/workflows/incident_resolution/mcp_backend_evidence_contract.py"
UNCERTIFIED = "NOT_CERTIFIED"
CONTRADICTION = "CONTRADICTION"
PASS_NO_CALL = "VERIFIED_NO_GROUP_LIST_DISPATCH_DURING_PENDING"
DISPATCH = "DISPATCH_OBSERVED"


def _contract():
    return importlib.import_module(MODULE_NAME)


def _evt(kind, *, event_id="ev-001", owner=None, request_id=None, **extra):
    owner = owner or ("mcp_backend" if kind.startswith("MCP_HTTP_") or
                     kind.startswith("MCP_TOOL_") else "python_governor")
    e = {
        "schema_version": "1.0",
        "event_type": kind,
        "event_id": event_id,
        "source_component": owner,
        "producer_instance_id": "synthetic-producer-1",
        "captured_at_utc": "2026-10-14T12:00:01Z",
        "ingested_at_utc": "2026-10-14T12:00:02Z",
        "source_receipt": {"proof_id": "SYNTHETIC-TRUSTED-PRODUCER", "issuer": owner},
    }
    if owner == "mcp_backend":
        e.update({
            "backend_revision_fingerprint": "hmac:synthetic-revision-1",
            "image_fingerprint": "hmac:synthetic-image-1",
            "backend_request_id": request_id or "backend-request-1",
            "tool_name": "group_list",
            "arguments_fingerprint": "hmac:synthetic-args-1",
        })
        if kind == "MCP_HTTP_AUTH_EVALUATED":
            e.update(auth_result="ACCEPT", issuer_valid=True, tenant_valid=True,
                     audience_valid=True, lifetime_valid=True,
                     role_or_scope_valid=True,
                     principal_fingerprint="hmac:synthetic-principal")
        elif kind == "MCP_TOOL_DISPATCH_STARTED":
            e["dispatch_stage"] = "HANDLER_ENTERED"
        elif kind == "MCP_TOOL_DISPATCH_FINISHED":
            e.update(dispatch_stage="HANDLER_FINISHED", status="SUCCESS")
    e.update(extra)
    return e


# TEST-ONLY keyed evidence builder; never a product trust implementation.
_TEST_ATTESTATION_KEY = b"TEST-ONLY-R16L-CONTENT-ATTESTATION-NOT-LIVE"
_ALLOWED_TEST_ISSUERS = frozenset({
    "python_governor", "foundry_adapter", "mcp_backend", "evidence_store", "coverage_sensor"
})


def _subject_digest(domain, issuer, subject):
    packed = json.dumps(subject, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=True)
    return hmac.new(_TEST_ATTESTATION_KEY,
                    (domain + "\0" + issuer + "\0" + packed).encode("ascii"),
                    hashlib.sha256).hexdigest()


def _seal_one(record, domain):
    if not isinstance(record, dict):
        return
    receipt = record.get("source_receipt")
    if not isinstance(receipt, dict):
        return
    proof = receipt.get("proof_id")
    issuer = receipt.get("issuer")
    if (issuer not in _ALLOWED_TEST_ISSUERS or
            not isinstance(proof, str) or
            (proof != "SYNTHETIC-TRUSTED-PRODUCER" and
             not proof.startswith("test-bound-"))):
        return  # Deliberately untrusted receipts stay untrusted.
    subject = {key: val for key, val in record.items() if key != "source_receipt"}
    record["source_receipt"] = {
        "issuer": issuer,
        "proof_id": "test-bound-" + _subject_digest(domain, issuer, subject),
    }


def _seal_bundle(bundle):
    if (bundle["backend_events"] and isinstance(bundle.get("correlation"), dict) and
            "linked_backend_request_id" not in bundle["correlation"]):
        bundle["correlation"]["linked_backend_request_id"] = bundle["backend_events"][0]["backend_request_id"]
    _seal_one(bundle["operation"], "operation")
    for section in ("consumer_events", "backend_events"):
        for record in bundle[section]:
            _seal_one(record, "event:" + record["event_type"])
    for section in ("correlation", "backend_provenance", "coverage"):
        _seal_one(bundle[section], section)
    return bundle


def _trust(receipt, *, subject_kind, subject):
    """Content- and domain-bound synthetic signature; NEVER production trust."""
    if (not isinstance(receipt, dict) or not isinstance(subject, dict) or
            "source_receipt" in subject or
            set(receipt) != {"issuer", "proof_id"} or
            receipt.get("issuer") not in _ALLOWED_TEST_ISSUERS or
            not isinstance(receipt.get("proof_id"), str)):
        return False
    expected = "test-bound-" + _subject_digest(
        subject_kind, receipt["issuer"], subject)
    return hmac.compare_digest(receipt["proof_id"], expected)


def _ready():
    bundle = {
        "operation": {
            "source_receipt": {"proof_id": "SYNTHETIC-TRUSTED-PRODUCER", "issuer": "python_governor"},
            "operation_id": "synthetic-op-001",
            "workflow_id": "synthetic-workflow-001",
            "capability_id": "azure.resource_group.list",
            "agent_name": "agent-f27-rg-list-pause-probe-sbx",
            "agent_version": "2",
            "server_label": "azure-mcp-operations-sbx",
            "tool_name": "group_list",
            "arguments_fingerprint": "hmac:synthetic-args-1",
            "response_id": "synthetic-response-1",
            "approval_request_id": "synthetic-approval-1",
            "approval_state": "PENDING",
            "technical_approval": None,
            "human_approval_id": None,
            "window_start_utc": "2026-10-14T12:00:00Z",
            "window_end_utc": "2026-10-14T12:01:00Z",
        },
        "consumer_events": [
            _evt("OPERATION_AUTHORITY_VALIDATED", event_id="consumer-1"),
            _evt("MCP_APPROVAL_PENDING", event_id="consumer-2", owner="foundry_adapter",
                 response_id="synthetic-response-1", approval_request_id="synthetic-approval-1"),
        ],
        "backend_events": [],
        "diagnostic_events": [],
        "coverage": {
            "sensor_id": "synthetic-handler-entry-sensor",
            "backend_revision_fingerprint": "hmac:synthetic-revision-1",
            "image_fingerprint": "hmac:synthetic-image-1",
            "hook": "GroupListCommand.ExecuteAsync",
            "replica_ids": ["replica-1"],
            "expected_replica_ids": ["replica-1"],
            "start_utc": "2026-10-14T12:00:00Z",
            "end_utc": "2026-10-14T12:01:00Z",
            "watermark_utc": "2026-10-14T12:02:00Z",
            "sensor_enabled": True,
            "sampling_ratio": 1.0,
            "emitted_count": 0,
            "ingested_count": 0,
            "dropped_count": 0,
            "gap_count": 0,
            "calibration_positive": True,
            "calibration_revision_fingerprint": "hmac:synthetic-revision-1",
            "store_immutable": True,
            "source_receipt": {"proof_id": "SYNTHETIC-TRUSTED-PRODUCER", "issuer": "coverage_sensor"},
        },
        "correlation": {
            "method": "authenticated_provider_link",
            "exact_operation_id": "synthetic-op-001",
            "backend_revision_fingerprint": "hmac:synthetic-revision-1",
            "linked_approval_request_id": "synthetic-approval-1",
            "linked_response_id": "synthetic-response-1",
            "replay_protected": True,
            "source_receipt": {"proof_id": "SYNTHETIC-TRUSTED-PRODUCER", "issuer": "mcp_backend"},
        },
        "backend_provenance": {
            "attested_release": True,
            "attested_handler_hook": True,
            "revision_fingerprint": "hmac:synthetic-revision-1",
            "image_fingerprint": "hmac:synthetic-image-1",
            "source_receipt": {"proof_id": "SYNTHETIC-TRUSTED-PRODUCER", "issuer": "mcp_backend"},
        },
    }
    return _seal_bundle(bundle)


def _dispatch_start(*, event_id="backend-dispatch-1", request_id="backend-request-1", **extra):
    return _evt("MCP_TOOL_DISPATCH_STARTED", event_id=event_id,
                request_id=request_id, dispatch_stage="HANDLER_ENTERED", **extra)




def _verify(bundle, verifier=_trust):
    return _contract().verify_backend_evidence(bundle, verify_receipt=verifier)


def _with_dispatch():
    bundle = _ready()
    bundle["backend_events"] = [_dispatch_start()]
    bundle["coverage"].update(emitted_count=1, ingested_count=1)
    return _seal_bundle(bundle)


def _require_uncertified(bundle):
    # A malformed or unsupported attestation must never certify a LIVE fact.
    assert _verify(bundle) == UNCERTIFIED


def test_A01_coverage_start_tamper_same_receipt():
    b = _ready()
    b["coverage"]["start_utc"] = "2026-10-14T11:59:00Z"
    _require_uncertified(b)


def test_A02_coverage_end_tamper_same_receipt():
    b = _ready()
    b["coverage"]["end_utc"] = "2026-10-14T12:01:30Z"
    _require_uncertified(b)


def test_A03_coverage_watermark_tamper_same_receipt():
    b = _ready()
    b["coverage"]["watermark_utc"] = "2026-10-14T12:10:00Z"
    _require_uncertified(b)


def test_A04_sensor_id_substitution_same_receipt():
    b = _ready()
    b["coverage"]["sensor_id"] = "another-synthetic-sensor"
    _require_uncertified(b)


def test_A05_replica_set_substitution_same_receipt():
    b = _ready()
    b["coverage"]["replica_ids"] = ["different-replica"]
    b["coverage"]["expected_replica_ids"] = ["different-replica"]
    _require_uncertified(b)


def test_A06_calibration_false_attestation_forged_as_true():
    b = _ready()
    b["coverage"]["calibration_positive"] = False
    _seal_bundle(b)
    assert _verify(b) == UNCERTIFIED
    b["coverage"]["calibration_positive"] = True
    # Synthetic receipt remains identical; the claimed calibration was edited.
    _require_uncertified(b)


def test_A07_unreconciled_emitted_count_edited_to_zero():
    b = _ready()
    b["coverage"]["emitted_count"] = 1
    _seal_bundle(b)
    assert _verify(b) == UNCERTIFIED
    b["coverage"]["emitted_count"] = 0
    _require_uncertified(b)


def test_A08_unauthenticated_method_edited_to_authenticated():
    b = _ready()
    b["correlation"]["method"] = "timestamp_guess"
    _seal_bundle(b)
    assert _verify(b) == UNCERTIFIED
    b["correlation"]["method"] = "authenticated_provider_link"
    _require_uncertified(b)


def test_A09_replay_protection_flag_edited_to_true():
    b = _ready()
    b["correlation"]["replay_protected"] = False
    _seal_bundle(b)
    assert _verify(b) == UNCERTIFIED
    b["correlation"]["replay_protected"] = True
    _require_uncertified(b)


def test_A10_operation_and_link_substituted_with_same_receipts():
    b = _ready()
    b["operation"]["operation_id"] = "synthetic-op-substituted"
    b["correlation"]["exact_operation_id"] = "synthetic-op-substituted"
    _require_uncertified(b)


def test_A11_handler_hook_attestation_false_edited_true():
    b = _ready()
    b["backend_provenance"]["attested_handler_hook"] = False
    _seal_bundle(b)
    assert _verify(b) == UNCERTIFIED
    b["backend_provenance"]["attested_handler_hook"] = True
    _require_uncertified(b)


def test_A12_release_attestation_false_edited_true():
    b = _ready()
    b["backend_provenance"]["attested_release"] = False
    _seal_bundle(b)
    assert _verify(b) == UNCERTIFIED
    b["backend_provenance"]["attested_release"] = True
    _require_uncertified(b)


def test_A13_dispatch_backend_request_id_not_bound_to_link():
    b = _with_dispatch()
    b["backend_events"][0]["backend_request_id"] = "unlinked-backend-request"
    _seal_one(b["backend_events"][0], "event:MCP_TOOL_DISPATCH_STARTED")
    # Event is newly authentic but correlation is still bound to the old request.
    _require_uncertified(b)


def test_A14_dispatch_capture_time_changed_same_receipt():
    b = _with_dispatch()
    b["backend_events"][0]["captured_at_utc"] = "2026-10-14T12:00:40Z"
    b["backend_events"][0]["ingested_at_utc"] = "2026-10-14T12:00:42Z"
    _require_uncertified(b)


def test_A15_shared_receipt_reused_for_distinct_backend_events():
    b = _with_dispatch()
    b["backend_events"].insert(0, _evt(
        "MCP_HTTP_AUTH_EVALUATED", event_id="separate-auth-event"))
    # A generic proof_id cannot attest two different event payloads.
    _require_uncertified(b)


def test_A16_dispatch_event_id_relabelled_same_receipt():
    b = _with_dispatch()
    b["backend_events"][0]["event_id"] = "substituted-event-id"
    _require_uncertified(b)


def test_A17_consumer_approval_pending_event_reused():
    b = _ready()
    b["consumer_events"][1]["event_id"] = "another-pending-event-id"
    _require_uncertified(b)


def test_A18_revision_and_coverage_claims_changed_in_lockstep():
    b = _ready()
    new = "hmac:synthetic-revision-replacement"
    b["backend_provenance"]["revision_fingerprint"] = new
    b["correlation"]["backend_revision_fingerprint"] = new
    b["coverage"]["backend_revision_fingerprint"] = new
    b["coverage"]["calibration_revision_fingerprint"] = new
    _require_uncertified(b)


def test_A19_app_only_identity_replayed_across_new_approval_ids():
    b = _with_dispatch()
    b["operation"].update(
        approval_request_id="synthetic-approval-replay",
        response_id="synthetic-response-replay",
        operation_id="synthetic-op-replay",
    )
    b["consumer_events"][1].update(
        approval_request_id="synthetic-approval-replay",
        response_id="synthetic-response-replay",
    )
    b["correlation"].update(
        exact_operation_id="synthetic-op-replay",
        linked_approval_request_id="synthetic-approval-replay",
        linked_response_id="synthetic-response-replay",
    )
    _require_uncertified(b)


def test_A20_dispatch_deleted_and_counters_reset_without_new_receipts():
    b = _with_dispatch()
    assert _verify(b) == DISPATCH
    b["backend_events"].clear()
    b["coverage"].update(emitted_count=0, ingested_count=0)
    _require_uncertified(b)


def test_A21_authentication_acceptance_event_can_be_relabelled():
    b = _ready()
    event = _evt("MCP_HTTP_AUTH_EVALUATED", event_id="auth-acceptance-proof")
    b["backend_events"] = [event]
    _seal_bundle(b)
    assert _verify(b) == PASS_NO_CALL
    b["backend_events"][0]["backend_request_id"] = "other-backend-request"
    _require_uncertified(b)


def test_A22_correlation_pinned_response_changed_with_same_proof():
    b = _ready()
    b["operation"]["response_id"] = "synthetic-response-replacement"
    b["consumer_events"][1]["response_id"] = "synthetic-response-replacement"
    b["correlation"]["linked_response_id"] = "synthetic-response-replacement"
    _require_uncertified(b)


def test_A23_forged_calibration_timestamp_unbound_to_coverage():
    b = _ready()
    b["coverage"]["calibration_revision_fingerprint"] = "hmac:another-release"
    assert _verify(b) == UNCERTIFIED
    # A claimant can re-align both fields without updating the old proof.
    b["backend_provenance"]["revision_fingerprint"] = "hmac:another-release"
    b["correlation"]["backend_revision_fingerprint"] = "hmac:another-release"
    b["coverage"]["backend_revision_fingerprint"] = "hmac:another-release"
    _require_uncertified(b)


def test_A24_approval_response_and_operation_swapped_no_proof_refresh():
    b = _with_dispatch()
    b["operation"].update(
        approval_request_id="another-approval",
        response_id="another-response",
        operation_id="another-operation",
    )
    b["correlation"].update(
        exact_operation_id="another-operation",
        linked_approval_request_id="another-approval",
        linked_response_id="another-response",
    )
    b["consumer_events"][1].update(
        approval_request_id="another-approval", response_id="another-response")
    assert _verify(b) == UNCERTIFIED


class _SyntheticContentBoundAuthority:
    """Test-only HMAC proof ledger: modeled verified *payload*, not just proof_id.

    Contract expectation for future GREEN: verify_receipt(
        receipt, *, subject_kind=<domain>, subject=<snapshot without receipt>) -> bool.
    This is a proposed domain-bound adapter, not a Microsoft/Azure signer.
    """
    _key = b"TEST-ONLY-R16K-NEVER-PRODUCTION-NO-LIVE"

    def __init__(self, bundle):
        self._sealed = {}
        serial = 0
        for name in ("consumer_events", "backend_events"):
            for item in bundle[name]:
                serial += 1
                self._seal(item, "event:" + item["event_type"], serial)
        for name in ("operation", "correlation", "backend_provenance", "coverage"):
            serial += 1
            self._seal(bundle[name], name, serial)

    def _seal(self, record, domain, counter):
        issuer = record["source_receipt"]["issuer"]
        proof_id = f"test-bound-{counter:04d}"
        record["source_receipt"] = {"issuer": issuer, "proof_id": proof_id}
        payload = {k: v for k, v in record.items() if k != "source_receipt"}
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hmac.new(self._key, (domain + "\0" + content).encode("ascii"), hashlib.sha256).hexdigest()
        self._sealed[proof_id] = (issuer, domain, digest)

    def __call__(self, receipt, *, subject_kind, subject):
        if not isinstance(receipt, dict):
            return False
        entry = self._sealed.get(receipt.get("proof_id"))
        if entry is None or receipt.get("issuer") != entry[0] or subject_kind != entry[1]:
            return False
        if not isinstance(subject, dict) or "source_receipt" in subject:
            return False
        content = json.dumps(subject, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hmac.new(self._key, (subject_kind + "\0" + content).encode("ascii"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, entry[2])


def test_A25_payload_bound_positive_pending_coverage_anchor():
    b = _ready()
    authority = _SyntheticContentBoundAuthority(b)
    assert _verify(b, authority) == PASS_NO_CALL


def test_A26_payload_bound_positive_dispatch_anchor():
    b = _with_dispatch()
    authority = _SyntheticContentBoundAuthority(b)
    assert _verify(b, authority) == DISPATCH


def test_G01_receipt_verifier_false_fails_closed():
    assert _verify(_ready(), lambda receipt: False) == UNCERTIFIED


def test_G02_receipt_verifier_raises_fails_closed():
    def unavailable(receipt):
        raise ConnectionError("synthetic trust service unavailable")
    assert _verify(_ready(), unavailable) == UNCERTIFIED


def test_G03_truthy_non_boolean_verifier_is_not_accepted():
    assert _verify(_ready(), lambda receipt: 1) == UNCERTIFIED


def test_G04_schema_guard_and_no_live_api_usage():
    bad = _evt("MCP_TOOL_DISPATCH_STARTED")
    bad["authorization_header"] = "synthetic-bearer"
    with pytest.raises(ValueError):
        _contract().validate_evidence_envelope(bad)
    code = Path(__file__).read_text(encoding="ascii")
    tree = ast.parse(code)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
    assert modules <= {"__future__", "ast", "copy", "hashlib", "hmac", "importlib", "json", "pathlib", "pytest"}
    forbidden = {"system", "popen", "run", "check_output", "urlopen", "post",
                 "write_text", "write_bytes", "open", "unlink", "mkdir", "rmdir", "rename", "replace"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in forbidden for node in ast.walk(tree))
