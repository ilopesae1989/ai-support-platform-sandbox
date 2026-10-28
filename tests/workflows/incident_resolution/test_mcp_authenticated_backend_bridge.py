"""B05-T05 synthetic-only ES256 backend-correlation negative tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from copy import deepcopy
from pathlib import Path
import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.workflows.incident_resolution.mcp_authenticated_backend_bridge import (
    BackendBridgeNotCertified,
    OfflineBackendAssociation,
    PinnedOperationLink,
    verify_offline_backend_association,
)
from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier,
    TrustedPublicKey,
    signature_preimage_v1,
)

SCOPE = "tenant:0cb40b2b-6cfc-4c63-bf7b-da710ea390cb/project:icenter-sbx/f27"
DOMAIN_LINK = "correlation:authenticated_backend_request"
DOMAIN_BACKEND = "event:MCP_TOOL_DISPATCH_STARTED"


def _key(issuer, domain, private=None):
    private = private or ec.generate_private_key(ec.SECP256R1())
    public = TrustedPublicKey(
        issuer=issuer,
        spki_der=private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        domains=frozenset({domain}),
    )
    return private, public


def _sign(private, public, domain, body):
    from src.workflows.incident_resolution.mcp_receipt_trust import signature_preimage_v1
    preimage = signature_preimage_v1(
        scope=SCOPE, issuer=public.issuer, domain=domain,
        kid=public.kid, subject=body,
    )
    der = private.sign(preimage, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return {
        "issuer": public.issuer,
        "proof_id": "es256:v1:" + public.kid + ":"
        + base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"),
    }


def _pinned(*, state="PENDING", human=None, technical=None, **overrides):
    if state == "APPROVED" and technical is None:
        technical = True
    elif state == "DENIED" and technical is None:
        technical = False
    settings = dict(
        trusted_scope=SCOPE, operation_id="operation-001", workflow_id="workflow-001",
        approval_state=state, human_approval_id=human, technical_approval=technical, response_id="resp-001",
        approval_request_id="mcpr-001", agent_name="agent-f27-rg-list-pause-probe-sbx",
        agent_version="2", server_label="azure-mcp-operations-sbx",
        tool_name="group_list", capability_id="azure.resource_group.list",
        arguments_fingerprint="hmac:synthetic-args-001",
        backend_revision_fingerprint="hmac:synthetic-revision-0000006",
        image_fingerprint="hmac:synthetic-image-01",
        window_start_utc="2026-10-28T10:00:00Z",
        window_end_utc="2026-10-28T10:05:00Z",
    )
    settings.update(overrides)
    return PinnedOperationLink(**settings)


def _backend_body(pinned, kind="MCP_TOOL_DISPATCH_STARTED"):
    body = dict(
        schema_version="1.0", event_type=kind, event_id="backend-event-001",
        source_component="mcp_backend", producer_instance_id="replica-0000006",
        captured_at_utc="2026-10-28T10:00:02Z",
        ingested_at_utc="2026-10-28T10:00:03Z",
        backend_revision_fingerprint=pinned.backend_revision_fingerprint,
        image_fingerprint=pinned.image_fingerprint,
        backend_request_id="backend-request-01", tool_name=pinned.tool_name,
        arguments_fingerprint=pinned.arguments_fingerprint,
    )
    if kind == "MCP_TOOL_DISPATCH_STARTED":
        body["dispatch_stage"] = "HANDLER_ENTERED"
    elif kind == "MCP_TOOL_DISPATCH_FINISHED":
        body.update(dispatch_stage="HANDLER_FINISHED", status="SUCCESS")
    elif kind == "MCP_HTTP_AUTH_EVALUATED":
        body.update(auth_result="ACCEPT", issuer_valid=True, tenant_valid=True,
                    audience_valid=True, lifetime_valid=True, role_or_scope_valid=True,
                    principal_fingerprint="hmac:synthetic-principal-01")
    return body


def _bridge_body(pinned, backend):
    return dict(
        schema_version="1.0", bridge_id="attested-bridge-01",
        method="authenticated_provider_link", exact_operation_id=pinned.operation_id,
        workflow_id=pinned.workflow_id, approval_state=pinned.approval_state,
        human_approval_id=pinned.human_approval_id, technical_approval=pinned.technical_approval,
        linked_response_id=pinned.response_id,
        linked_approval_request_id=pinned.approval_request_id,
        linked_backend_request_id=backend["backend_request_id"],
        linked_backend_event_id=backend["event_id"],
        agent_name=pinned.agent_name, agent_version=pinned.agent_version,
        server_label=pinned.server_label, tool_name=pinned.tool_name,
        capability_id=pinned.capability_id,
        arguments_fingerprint=pinned.arguments_fingerprint,
        backend_revision_fingerprint=pinned.backend_revision_fingerprint,
        image_fingerprint=pinned.image_fingerprint,
        observed_at_utc="2026-10-28T10:00:04Z",
    )


def _fixture(*, state="PENDING", human=None, kind="MCP_TOOL_DISPATCH_STARTED"):
    pinned = _pinned(state=state, human=human)
    backend_private, backend_public = _key("mcp_backend", "event:" + kind)
    attestor_private, attestor_public = _key("correlation_attestor", DOMAIN_LINK)
    backend = _backend_body(pinned, kind)
    backend["source_receipt"] = _sign(backend_private, backend_public,
                                      "event:" + kind, backend)
    bridge = _bridge_body(pinned, backend)
    bridge["source_receipt"] = _sign(attestor_private, attestor_public, DOMAIN_LINK, bridge)
    return dict(pinned=pinned, signed_bridge=bridge, backend_event=backend,
                bridge_verifier=IndependentReceiptVerifier(scope=SCOPE, keys=(attestor_public,)),
                backend_verifier=IndependentReceiptVerifier(scope=SCOPE, keys=(backend_public,)),
                attestor_private=attestor_private, attestor_public=attestor_public,
                backend_private=backend_private, backend_public=backend_public)


def _verify(f):
    return verify_offline_backend_association(**{k:f[k] for k in (
        "pinned", "signed_bridge", "backend_event", "bridge_verifier", "backend_verifier"
    )})


def _resign_bridge(f):
    bridge = f["signed_bridge"]
    bridge["source_receipt"] = _sign(f["attestor_private"], f["attestor_public"],
                                      DOMAIN_LINK, {k:v for k,v in bridge.items() if k!="source_receipt"})


def _resign_backend(f):
    event = f["backend_event"]
    event["source_receipt"] = _sign(f["backend_private"], f["backend_public"],
                                     "event:" + event["event_type"],
                                     {k:v for k,v in event.items() if k!="source_receipt"})


def test_pending_backend_start_is_association_not_approval():
    result = _verify(_fixture())
    assert isinstance(result, OfflineBackendAssociation)
    assert result.operation_id == "operation-001"
    assert result.approval_state == "PENDING"
    assert result.technical_approval is None
    assert result.backend_request_id == "backend-request-01"
    assert not hasattr(result, "g4_certified")
    assert not hasattr(result, "dispatch_authorized")
    with pytest.raises(FrozenInstanceError):
        result.operation_id = "forged"


def test_approved_with_human_anchor_remains_association_only():
    result = _verify(_fixture(state="APPROVED", human="human-approval-001"))
    assert result.approval_state == "APPROVED"
    assert result.human_approval_id == "human-approval-001"
    assert result.technical_approval is True
    assert not hasattr(result, "technical_success")


@pytest.mark.parametrize("kind", ["MCP_HTTP_AUTH_EVALUATED", "MCP_TOOL_DISPATCH_FINISHED"])
def test_other_backend_events_are_only_linked_events(kind):
    result = _verify(_fixture(kind=kind))
    assert result.backend_event_type == kind


@pytest.mark.parametrize("field, forged", [
    ("exact_operation_id", "operation-replacement"),
    ("workflow_id", "workflow-replacement"),
    ("linked_response_id", "resp-replacement"),
    ("linked_approval_request_id", "mcpr-replacement"),
    ("linked_backend_request_id", "backend-request-forged"),
    ("linked_backend_event_id", "backend-event-forged"),
    ("agent_name", "agent-wrong"),
    ("agent_version", "3"),
    ("server_label", "server-wrong"),
    ("tool_name", "compute_vm_start"),
    ("capability_id", "azure.vm.start"),
    ("arguments_fingerprint", "hmac:args-substituted"),
    ("backend_revision_fingerprint", "hmac:another-revision"),
    ("image_fingerprint", "hmac:another-image"),
    ("approval_state", "APPROVED"),
    ("human_approval_id", "fake-human-approval"),
    ("technical_approval", True),
])
def test_bridge_mutation_without_resign_is_rejected(field, forged):
    f = _fixture()
    f["signed_bridge"][field] = forged
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


@pytest.mark.parametrize("field, forged", [
    ("linked_response_id", "resp-other"),
    ("exact_operation_id", "operation-other"),
    ("approval_state", "APPROVED"),
    ("technical_approval", True),
    ("arguments_fingerprint", "hmac:args-other"),
    ("image_fingerprint", "hmac:image-other"),
])
def test_validly_resigned_bridge_conflicting_with_governor_denied(field, forged):
    f = _fixture()
    f["signed_bridge"][field] = forged
    _resign_bridge(f)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_validly_resigned_bridge_wrong_backend_request_denied():
    f = _fixture()
    f["signed_bridge"]["linked_backend_request_id"] = "other-request"
    _resign_bridge(f)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_validly_resigned_backend_wrong_arguments_denied():
    f = _fixture()
    f["backend_event"]["arguments_fingerprint"] = "hmac:other-args"
    _resign_backend(f)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_validly_resigned_backend_wrong_request_denied():
    f = _fixture()
    f["backend_event"]["backend_request_id"] = "other-request"
    _resign_backend(f)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_validly_resigned_backend_outside_window_denied():
    f = _fixture()
    f["backend_event"]["captured_at_utc"] = "2026-10-28T10:07:00Z"
    f["backend_event"]["ingested_at_utc"] = "2026-10-28T10:07:01Z"
    _resign_backend(f)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_validly_resigned_bridge_outside_window_denied():
    f = _fixture()
    f["signed_bridge"]["observed_at_utc"] = "2026-10-28T10:07:00Z"
    _resign_bridge(f)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_backend_event_not_signed_denied():
    f = _fixture()
    f["backend_event"]["source_receipt"] = {"issuer":"mcp_backend", "proof_id":"unsigned"}
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_same_crypto_key_cannot_impersonate_two_independent_issuers():
    f = _fixture()
    same_private = f["backend_private"]
    _, same_public = _key("correlation_attestor", DOMAIN_LINK, same_private)
    f["attestor_private"] = same_private
    f["attestor_public"] = same_public
    f["bridge_verifier"] = IndependentReceiptVerifier(scope=SCOPE, keys=(same_public,))
    _resign_bridge(f)
    with pytest.raises(BackendBridgeNotCertified, match="separation"):
        _verify(f)


def test_boolean_trust_callback_cannot_replace_crypto_verifier():
    f = _fixture()
    f["bridge_verifier"] = lambda *_args, **_kwargs: True
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_same_event_without_authenticated_bridge_is_denied():
    f = _fixture()
    f["signed_bridge"] = {}
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_backend_event_cannot_self_insert_operation_id():
    f = _fixture()
    f["backend_event"]["operation_id"] = f["pinned"].operation_id
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_unknown_jwt_field_in_backend_event_fails_closed():
    f = _fixture()
    f["backend_event"]["access_token"] = "test-should-never-persist"
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_unknown_auth_token_field_in_bridge_fails_closed():
    f = _fixture()
    f["signed_bridge"]["raw_authorization"] = "test-should-never-persist"
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_other_scope_in_verifier_denied():
    f = _fixture()
    f["bridge_verifier"] = IndependentReceiptVerifier(
        scope="tenant:other/project:other/f27", keys=(f["attestor_public"],))
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_governor_expected_approval_cannot_be_substituted():
    f = _fixture()
    f["pinned"] = replace(f["pinned"], approval_state="DENIED", technical_approval=False)
    with pytest.raises(BackendBridgeNotCertified):
        _verify(f)


def test_approved_governor_requires_human_approval_id():
    with pytest.raises(BackendBridgeNotCertified):
        _pinned(state="APPROVED", human=None)


def test_bad_window_or_fingerprint_rejected_at_pin_time():
    with pytest.raises(BackendBridgeNotCertified):
        _pinned(window_end_utc="2026-10-28T09:00:00Z")
    with pytest.raises(BackendBridgeNotCertified):
        _pinned(image_fingerprint="not-hmac")


def test_source_contains_no_cloud_or_database_calls():
    path = Path(__file__).resolve().parents[3] / "src/workflows/incident_resolution/mcp_authenticated_backend_bridge.py"
    source = path.read_text(encoding="utf-8")
    for fragment in ("DefaultAzureCredential", "CryptographyClient(", "sqlite3.connect(",
                     "subprocess.run(", "requests.get(", "az keyvault", "INSERT INTO", "claim_dispatch("):
        assert fragment not in source


def test_pending_governor_cannot_claim_mcp_approval():
    with pytest.raises(BackendBridgeNotCertified):
        _pinned(technical=True)


def test_denied_governor_requires_negative_mcp_decision():
    with pytest.raises(BackendBridgeNotCertified):
        _pinned(state="DENIED", technical=True)
