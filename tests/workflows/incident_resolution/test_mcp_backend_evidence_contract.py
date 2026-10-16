"""F27.3-R16L strengthened R16H contract tests, original 28 vectors/6 guards.

All data are synthetic.  No Foundry, Azure, MCP, HTTP, Docker, Git subprocess,
backend handler or approval is invoked.  These tests cannot certify LIVE no-call.

Future GREEN interface (not created here):
  src.workflows.incident_resolution.mcp_backend_evidence_contract
  validate_evidence_envelope(raw: Mapping[str, object]) -> object
  verify_backend_evidence(bundle: Mapping[str, object], *, verify_receipt: Callable) -> str

The verifier must not grant operation authority.  The injected trust checker is
synthetic and MUST NOT be shipped as a production trust implementation.
"""
from __future__ import annotations

import ast
import copy
import importlib
import hashlib
import hmac
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_FILE = ROOT / "src/workflows/incident_resolution/mcp_backend_evidence_contract.py"
MODULE_NAME = "src.workflows.incident_resolution.mcp_backend_evidence_contract"
EXPECTED_RED = "F27_3_EXPECTED_RED_MCP_BACKEND_EVIDENCE_CONTRACT_ABSENT"
PASS_NO_CALL = "VERIFIED_NO_GROUP_LIST_DISPATCH_DURING_PENDING"
DISPATCH = "DISPATCH_OBSERVED"
UNCERTIFIED = "NOT_CERTIFIED"
CONTRADICTION = "CONTRADICTION"


def _contract():
    # Not a missing-import error: each RED fails with one exact causal marker.
    if not MODULE_FILE.is_file():
        pytest.fail(EXPECTED_RED, pytrace=False)
    importlib.invalidate_caches()
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
    return {
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


def _verify(bundle):
    # Semantic fixtures are freshly signed after construction, so tests can
    # distinguish genuinely attested contradictions from tampering.
    _seal_bundle(bundle)
    return _contract().verify_backend_evidence(bundle, verify_receipt=_trust)


def _invalid(event):
    api = _contract()
    with pytest.raises(ValueError):
        api.validate_evidence_envelope(event)


def _dispatch_start(*, event_id="backend-dispatch-1", request_id="backend-request-1", **extra):
    return _evt("MCP_TOOL_DISPATCH_STARTED", event_id=event_id,
                request_id=request_id, dispatch_stage="HANDLER_ENTERED", **extra)


def test_E01_schema_and_closed_event_type():
    for key, value in (("schema_version", "9.9"), ("event_type", "arbitrary_event")):
        e = _evt("MCP_TOOL_DISPATCH_STARTED")
        e[key] = value
        _invalid(e)


def test_E02_nonempty_event_id_and_unique_delivery_identity():
    _invalid(_evt("MCP_TOOL_DISPATCH_STARTED", event_id=""))
    bundle = _ready()
    bundle["backend_events"] = [_dispatch_start(), _dispatch_start(request_id="different-backend-request")]
    assert _verify(bundle) == CONTRADICTION


def test_E03_utc_timestamps_and_causal_window():
    for k, v in (("captured_at_utc", "2026-10-14T12:00:01"),
                 ("ingested_at_utc", "2026-10-14T11:59:00Z")):
        e = _evt("MCP_TOOL_DISPATCH_STARTED")
        e[k] = v
        _invalid(e)
    b = _ready()
    b["coverage"]["watermark_utc"] = "2026-10-14T11:59:59Z"
    assert _verify(b) == UNCERTIFIED


def test_E04_consumer_cannot_self_certify_backend_source():
    b = _ready()
    b["backend_events"] = [_dispatch_start(source_receipt={
        "proof_id": "untrusted", "issuer": "python_governor"})]
    assert _verify(b) == UNCERTIFIED


def test_E05_unproven_backend_revision_and_provenance():
    b = _ready()
    b["backend_provenance"]["source_receipt"] = {"proof_id": "untrusted", "issuer": "mcp_backend"}
    assert _verify(b) == UNCERTIFIED


def test_E06_forbidden_raw_secrets_and_args_rejected():
    for field, value in (("jwt", "synthetic-bearer-value"),
                         ("authorization_header", "Bearer synthetic-value"),
                         ("client_secret", "synthetic-secret"),
                         ("signed_url", "https://example.invalid/?sig=synthetic"),
                         ("raw_arguments", {"subscription": "synthetic-id"}),
                         ("raw_result", {"groups": ["sensitive"]})):
        e = _evt("MCP_TOOL_DISPATCH_STARTED")
        e[field] = value
        _invalid(e)


def test_E07_unkeyed_fingerprint_rejected_for_identity():
    e = _evt("MCP_HTTP_AUTH_EVALUATED", principal_fingerprint="sha256:unencrypted-identity")
    _invalid(e)


def test_E08_jwt_validation_flags_typed_and_distinct():
    e = _evt("MCP_HTTP_AUTH_EVALUATED", auth_result="ACCEPT",
             issuer_valid=True, tenant_valid=True, audience_valid=True,
             lifetime_valid=True, role_or_scope_valid=True,
             principal_fingerprint="hmac:synthetic-principal")
    api = _contract()
    assert api.validate_evidence_envelope(e) is not None
    bad = copy.deepcopy(e)
    bad["audience_valid"] = "yes"
    with pytest.raises(ValueError):
        api.validate_evidence_envelope(bad)


def test_E09_denied_jwt_and_same_request_dispatch_contradiction():
    b = _ready()
    b["backend_events"] = [
        _evt("MCP_HTTP_AUTH_EVALUATED", event_id="auth-denied", auth_result="DENY",
             issuer_valid=True, tenant_valid=True, audience_valid=False,
             lifetime_valid=True, role_or_scope_valid=True),
        _dispatch_start(),
    ]
    assert _verify(b) == CONTRADICTION


def test_E10_outgoing_principal_not_inferred_from_declared_mi():
    b = _ready()
    b["outgoing_identity"] = {"strategy": "UseHostingEnvironmentIdentity",
                               "principal_equals_project_mi": True, "actual_token_proof": None}
    assert _verify(b) == UNCERTIFIED


def test_E11_runtime_tool_executed_diagnostic_not_handler_dispatch():
    b = _ready()
    b["diagnostic_events"] = [{"name": "ToolExecuted", "request_id": "backend-request-1"}]
    assert _verify(b) == PASS_NO_CALL


def test_E12_other_tool_is_not_group_list_dispatch():
    b = _ready()
    b["backend_events"] = [_dispatch_start(tool_name="group_resource_list")]
    assert _verify(b) == CONTRADICTION


def test_E13_handler_entered_vs_azure_attempt_vs_completion():
    b = _ready()
    b["backend_events"] = [_dispatch_start()]
    assert _verify(b) == DISPATCH
    b["backend_events"] = [
        _evt("MCP_TOOL_DISPATCH_FINISHED", event_id="finish-without-start",
             dispatch_stage="HANDLER_FINISHED")]
    assert _verify(b) == CONTRADICTION


def test_E14_finished_request_must_match_started_request():
    b = _ready()
    b["backend_events"] = [_dispatch_start(), _evt(
        "MCP_TOOL_DISPATCH_FINISHED", event_id="finish", request_id="different-request",
        dispatch_stage="HANDLER_FINISHED", status="SUCCESS")]
    assert _verify(b) == CONTRADICTION


def test_E15_approval_request_distinct_from_response_and_consumer_owned():
    b = _ready()
    b["operation"]["approval_request_id"] = "synthetic-response-1"
    assert _verify(b) == CONTRADICTION


def test_E16_technical_approval_cannot_derive_human_hitl():
    b = _ready()
    b["operation"].update(approval_state="APPROVED", technical_approval=True,
                          human_approval_id=None)
    assert _verify(b) == UNCERTIFIED


def test_E17_exact_authenticated_correlation_required():
    b = _ready()
    b["correlation"] = None
    assert _verify(b) == UNCERTIFIED


def test_E18_timestamp_or_attacker_traceparent_not_join_authority():
    b = _ready()
    b["correlation"] = {"method": "approximate_timestamp_and_traceparent",
                        "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"}
    assert _verify(b) == UNCERTIFIED


def test_E19_substituted_operation_identity_is_contradiction():
    for key, wrong in (("server_label", "another-server"),
                       ("tool_name", "group_resource_list"),
                       ("arguments_fingerprint", "hmac:other-args"),
                       ("agent_version", "14")):
        b = _ready()
        b["consumer_events"][1][key] = wrong
        assert _verify(b) == CONTRADICTION


def test_E20_closed_positive_coverage_with_zero_dispatch():
    assert _verify(_ready()) == PASS_NO_CALL


def test_E21_sensor_off_uncalibrated_or_counters_inconsistent():
    for key, value in (("sensor_enabled", False), ("calibration_positive", False),
                       ("ingested_count", 1)):
        b = _ready()
        b["coverage"][key] = value
        assert _verify(b) == UNCERTIFIED


def test_E22_missing_replica_sampling_loss_or_open_watermark():
    for key, value in (("expected_replica_ids", ["replica-1", "replica-2"]),
                       ("sampling_ratio", 0.1), ("dropped_count", 1),
                       ("gap_count", 1), ("watermark_utc", "2026-10-14T12:00:30Z")):
        b = _ready()
        b["coverage"][key] = value
        assert _verify(b) == UNCERTIFIED


def test_E23_calibration_matches_same_version_and_handler():
    b = _ready()
    b["coverage"]["calibration_revision_fingerprint"] = "hmac:different-revision"
    assert _verify(b) == UNCERTIFIED
    assert _verify(_ready()) == PASS_NO_CALL


def test_E24_denied_approval_followed_by_dispatch_is_contradiction():
    b = _ready()
    b["operation"]["approval_state"] = "DENIED"
    b["operation"]["technical_approval"] = False
    b["backend_events"] = [_dispatch_start()]
    assert _verify(b) == CONTRADICTION


def test_E25_exact_human_and_technical_approval_one_dispatch():
    b = _ready()
    b["operation"].update(approval_state="APPROVED", technical_approval=True,
                          human_approval_id="synthetic-human-approval-1")
    b["consumer_events"].append(_evt("MCP_APPROVAL_DECIDED", event_id="consumer-3",
                                     approval_request_id="synthetic-approval-1",
                                     response_id="synthetic-response-1", approved=True))
    b["backend_events"] = [_dispatch_start()]
    b["coverage"].update(emitted_count=1, ingested_count=1)
    assert _verify(b) == DISPATCH


def test_E26_idempotent_delivery_does_not_hide_two_commands():
    b = _ready()
    d = _dispatch_start()
    b["backend_events"] = [d, copy.deepcopy(d)]
    b["coverage"].update(emitted_count=1, ingested_count=2)
    assert _verify(b) == DISPATCH
    b["backend_events"].append(_dispatch_start(event_id="backend-dispatch-2",
                                               request_id="backend-request-2"))
    assert _verify(b) == CONTRADICTION


def test_E27_timeout_unclosed_pending_window_not_certified():
    b = _ready()
    b["operation"]["approval_state"] = "TIMEOUT_UNCERTAIN"
    assert _verify(b) == UNCERTIFIED


def test_E28_unattested_deployed_binary_is_not_certified():
    b = _ready()
    b["backend_provenance"]["attested_handler_hook"] = False
    assert _verify(b) == UNCERTIFIED


# Six legacy guards remain GREEN in RED and must not run external services.
def test_G01_v13_default_catalog_probe_absent():
    text = (ROOT / "src/agents/catalog.py").read_text(encoding="utf-8")
    catalog = ast.parse(text)
    assert any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
               and t.id == "_DEFAULT_AGENT_CATALOG" for t in n.targets)
               or isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
               and n.target.id == "_DEFAULT_AGENT_CATALOG" for n in catalog.body)
    assert 'name="agent-azure-operations-sbx"' in text
    assert 'version="13"' in text
    assert "agent-f27-rg-list-pause-probe-sbx" not in text


def test_G02_default_procedure_manifest_vm_start_only():
    path = ROOT / "src/workflows/incident_resolution/procedure_capability_bindings.v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert len(manifest["bindings"]) == 3
    assert {r["capability_id"] for r in manifest["bindings"]} == {"azure.vm.start"}


def test_G03_foundry_binding_exact_pinned_and_always_policy():
    text = (ROOT / "src/workflows/incident_resolution/capability_foundry_agent_binding.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assert any(isinstance(n, ast.ClassDef) and n.name == "CapabilityFoundryAgentBinding" for n in tree.body)
    assert 'self.require_approval != "always"' in text
    assert "agent_definition.version" in text
    assert "capability.capability_id" in text


def test_G04_azure_read_authority_exact_tool_and_arguments():
    text = (ROOT / "src/workflows/incident_resolution/azure_read_tool_authority.py").read_text(encoding="utf-8")
    assert 'capability_id="azure.resource_group.list"' in text
    assert 'server_label="azure-mcp-operations-sbx"' in text
    assert 'tool_name="group_list"' in text
    assert '"subscription_id"' in text and '"subscription"' in text
    assert "validate_pending_approval" in text


def test_G05_consumer_evidence_not_backend_sensor():
    mcp = (ROOT / "src/workflows/incident_resolution/mcp_evidence.py").read_text(encoding="utf-8")
    executor = (ROOT / "src/workflows/incident_resolution/executors/azure_operations.py").read_text(encoding="utf-8")
    assert "class McpCallEvidence" in mcp
    assert "OperationEvidence" in executor
    assert "_extract_mcp_approval_requests" in executor
    assert "backend_request_id" not in mcp  # no new independent producer silently added


def test_G06_test_source_is_offline_and_read_only():
    text = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                for alias in n.names}
    assert imports <= {"__future__", "ast", "copy", "hashlib", "hmac", "importlib", "json", "pathlib", "pytest"}
    assert not any(isinstance(n, (ast.AsyncFunctionDef, ast.Await)) for n in ast.walk(tree))
    forbidden = {"write_text", "write_bytes", "unlink", "mkdir", "rmdir", "rename",
                 "replace", "system", "popen", "run", "check_output", "urlopen", "post"}
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in forbidden for n in ast.walk(tree))
