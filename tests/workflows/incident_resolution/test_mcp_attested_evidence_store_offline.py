"""F27 B05-T06 adversarial OFFLINE tests. No Azure, SQL migration or LIVE."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sqlite3

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.workflows.incident_resolution.mcp_authenticated_backend_bridge import PinnedOperationLink
from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier, TrustedPublicKey, signature_preimage_v1,
)
from src.workflows.incident_resolution.mcp_attested_evidence_store_offline import (
    EvidencePreparationRejected, EvidenceStorageUnavailable,
    OfflineEvidenceResult, OfflinePreparedEvidenceV2, SqliteOfflineEvidenceLedger,
    prepare_offline_backend_evidence_v2,
)

SCOPE = "tenant:0cb40b2b-6cfc-4c63-bf7b-da710ea390cb/project:icenter-sbx/f27"
DOMAIN_LINK = "correlation:authenticated_backend_request"
DOMAIN_EVENT = "event:MCP_TOOL_DISPATCH_STARTED"


def _keys(issuer, domain):
    private = ec.generate_private_key(ec.SECP256R1())
    public = TrustedPublicKey(
        issuer=issuer,
        spki_der=private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        domains=frozenset({domain}),
    )
    return private, public


def _sign(priv, pub, domain, subject):
    preimage = signature_preimage_v1(
        scope=SCOPE, issuer=pub.issuer, domain=domain,
        kid=pub.kid, subject=subject,
    )
    der = priv.sign(preimage, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return dict(issuer=pub.issuer, proof_id="es256:v1:" + pub.kid + ":" +
                base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"))


def _fixture(*, operation_id="operation-001", event_id="backend-event-001", bridge_id="bridge-001"):
    pinned = PinnedOperationLink(
        trusted_scope=SCOPE,
        operation_id=operation_id, workflow_id="workflow-001",
        approval_state="PENDING", human_approval_id=None, technical_approval=None,
        response_id="resp-001", approval_request_id="mcpr-001",
        agent_name="agent-f27-rg-list-pause-probe-sbx", agent_version="2",
        server_label="azure-mcp-operations-sbx", tool_name="group_list",
        capability_id="azure.resource_group.list",
        arguments_fingerprint="hmac:synthetic-args-001",
        backend_revision_fingerprint="hmac:synthetic-revision-0000006",
        image_fingerprint="hmac:synthetic-image-01",
        window_start_utc="2026-10-28T10:00:00Z",
        window_end_utc="2026-10-28T10:05:00Z",
    )
    backend_private, backend_public = _keys("mcp_backend", DOMAIN_EVENT)
    attestor_private, attestor_public = _keys("correlation_attestor", DOMAIN_LINK)
    event = dict(
        schema_version="1.0", event_type="MCP_TOOL_DISPATCH_STARTED",
        event_id=event_id, source_component="mcp_backend",
        producer_instance_id="replica-0000006",
        captured_at_utc="2026-10-28T10:00:02Z",
        ingested_at_utc="2026-10-28T10:00:03Z",
        backend_revision_fingerprint=pinned.backend_revision_fingerprint,
        image_fingerprint=pinned.image_fingerprint,
        backend_request_id="backend-request-001", tool_name=pinned.tool_name,
        arguments_fingerprint=pinned.arguments_fingerprint,
        dispatch_stage="HANDLER_ENTERED",
    )
    event["source_receipt"] = _sign(backend_private, backend_public, DOMAIN_EVENT, event)
    bridge = dict(
        schema_version="1.0", bridge_id=bridge_id,
        method="authenticated_provider_link", exact_operation_id=pinned.operation_id,
        workflow_id=pinned.workflow_id,
        approval_state=pinned.approval_state,
        human_approval_id=None, technical_approval=None,
        linked_response_id=pinned.response_id,
        linked_approval_request_id=pinned.approval_request_id,
        linked_backend_request_id=event["backend_request_id"],
        linked_backend_event_id=event["event_id"],
        agent_name=pinned.agent_name, agent_version=pinned.agent_version,
        server_label=pinned.server_label, tool_name=pinned.tool_name,
        capability_id=pinned.capability_id,
        arguments_fingerprint=pinned.arguments_fingerprint,
        backend_revision_fingerprint=pinned.backend_revision_fingerprint,
        image_fingerprint=pinned.image_fingerprint,
        observed_at_utc="2026-10-28T10:00:04Z",
    )
    bridge["source_receipt"] = _sign(attestor_private, attestor_public, DOMAIN_LINK, bridge)
    return dict(
        pinned=pinned, signed_bridge=bridge, backend_event=event,
        bridge_verifier=IndependentReceiptVerifier(scope=SCOPE, keys=(attestor_public,)),
        backend_verifier=IndependentReceiptVerifier(scope=SCOPE, keys=(backend_public,)),
        backend_private=backend_private, backend_public=backend_public,
        attestor_private=attestor_private, attestor_public=attestor_public,
    )


def _prepare(f):
    return prepare_offline_backend_evidence_v2(**{key: f[key] for key in (
        "pinned", "signed_bridge", "backend_event", "bridge_verifier", "backend_verifier",
    )})


def _resign(f):
    b = f["signed_bridge"]
    b["source_receipt"] = _sign(f["attestor_private"], f["attestor_public"],
                                 DOMAIN_LINK, {k:v for k,v in b.items() if k != "source_receipt"})
    e = f["backend_event"]
    e["source_receipt"] = _sign(f["backend_private"], f["backend_public"],
                                 DOMAIN_EVENT, {k:v for k,v in e.items() if k != "source_receipt"})


def _store(tmp_path):
    store = SqliteOfflineEvidenceLedger(tmp_path / "isolated_fixture.db")
    store.initialize_offline_fixture()
    return store


def test_prepare_fails_closed_for_unsigned_backend():
    f = _fixture()
    f["backend_event"]["source_receipt"] = dict(issuer="mcp_backend", proof_id="invalid")
    with pytest.raises(EvidencePreparationRejected):
        _prepare(f)


def test_prepare_fails_closed_for_missing_independent_bridge():
    f = _fixture()
    f["signed_bridge"] = {}
    with pytest.raises(EvidencePreparationRejected):
        _prepare(f)


def test_prepare_pending_is_not_authorization_or_g4_certification():
    result = _prepare(_fixture())
    assert result.approval_state == "PENDING"
    assert result.schema_version == "2.0-offline"
    assert result.issuer == "mcp_backend"
    assert len(result.logical_sha256) == 64
    assert result.backend_kid != result.attestor_kid
    assert not hasattr(result, "g4_certified")
    assert not hasattr(result, "authorized_dispatch")
    with pytest.raises(FrozenInstanceError):
        result.operation_id = "forged"


def test_signature_variants_same_logical_and_subject():
    f = _fixture()
    a = _prepare(f)
    _resign(f)
    b = _prepare(f)
    assert a.logical_sha256 == b.logical_sha256
    assert a.subject_sha256 == b.subject_sha256
    assert a == b


def test_scope_is_external_and_cannot_be_relabelled():
    f = _fixture()
    f["pinned"] = replace(f["pinned"], trusted_scope="tenant:other/project:other/f27")
    with pytest.raises(EvidencePreparationRejected):
        _prepare(f)


def test_backend_request_id_change_validly_resigned_produces_conflict_same_logical():
    f = _fixture()
    a = _prepare(f)
    f["backend_event"]["backend_request_id"] = "backend-request-002"
    f["signed_bridge"]["linked_backend_request_id"] = "backend-request-002"
    _resign(f)
    b = _prepare(f)
    assert a.logical_sha256 == b.logical_sha256
    assert a.subject_sha256 != b.subject_sha256


def test_different_event_id_changes_logical_identity():
    f = _fixture(event_id="backend-event-001")
    a = _prepare(f)
    f["backend_event"]["event_id"] = "backend-event-002"
    f["signed_bridge"]["linked_backend_event_id"] = "backend-event-002"
    _resign(f)
    b = _prepare(f)
    assert a.logical_sha256 != b.logical_sha256


def test_offline_store_requires_explicit_schema(tmp_path):
    store = SqliteOfflineEvidenceLedger(tmp_path / "missing.db")
    with pytest.raises(EvidenceStorageUnavailable):
        store.observe(_prepare(_fixture()))


def test_atomic_new_duplicate_and_restart(tmp_path):
    claim = _prepare(_fixture())
    store = _store(tmp_path)
    assert store.observe(claim) is OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY
    assert store.observe(claim) is OfflineEvidenceResult.DUPLICATE_OFFLINE_NO_AUTHORITY
    restarted = SqliteOfflineEvidenceLedger(tmp_path / "isolated_fixture.db")
    assert restarted.observe(claim) is OfflineEvidenceResult.DUPLICATE_OFFLINE_NO_AUTHORITY
    assert restarted.reconcile_unknown(claim) is OfflineEvidenceResult.CONFIRMED_PRESENT_NO_AUTHORITY


def test_changed_payload_same_identity_is_conflict_and_never_overwrites(tmp_path):
    store = _store(tmp_path)
    f = _fixture()
    first = _prepare(f)
    assert store.observe(first) is OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY
    f["backend_event"]["backend_request_id"] = "backend-request-002"
    f["signed_bridge"]["linked_backend_request_id"] = "backend-request-002"
    _resign(f)
    conflict = _prepare(f)
    assert store.observe(conflict) is OfflineEvidenceResult.CONFLICT_REJECTED
    assert store.reconcile_unknown(first) is OfflineEvidenceResult.CONFIRMED_PRESENT_NO_AUTHORITY
    assert store.reconcile_unknown(conflict) is OfflineEvidenceResult.CONFLICT_REJECTED


def test_new_event_does_not_collide_with_existing(tmp_path):
    store = _store(tmp_path)
    a = _prepare(_fixture(event_id="event-a"))
    b = _prepare(_fixture(event_id="event-b"))
    assert store.observe(a) is OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY
    assert store.observe(b) is OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY


def test_parallel_workers_cannot_insert_twice(tmp_path):
    store = _store(tmp_path)
    claim = _prepare(_fixture())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(store.observe, [claim] * 8))
    assert results.count(OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY) == 1
    assert results.count(OfflineEvidenceResult.DUPLICATE_OFFLINE_NO_AUTHORITY) == 7


class _UncertainConnection:
    def __init__(self, path, *, commit_on_server):
        self.conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.commit_on_server = commit_on_server

    def execute(self, *args, **kwargs):
        return self.conn.execute(*args, **kwargs)

    def commit(self):
        if self.commit_on_server:
            self.conn.commit()
        raise ConnectionError("offline simulated lost commit acknowledgment")

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def test_lost_ack_after_commit_stays_unknown_until_fresh_read(tmp_path):
    store = _store(tmp_path)
    claim = _prepare(_fixture())
    injected = SqliteOfflineEvidenceLedger(
        tmp_path / "isolated_fixture.db",
        connection_factory=lambda: _UncertainConnection(tmp_path / "isolated_fixture.db", commit_on_server=True),
    )
    assert injected.observe(claim) is OfflineEvidenceResult.COMMIT_OUTCOME_UNKNOWN
    assert store.reconcile_unknown(claim) is OfflineEvidenceResult.CONFIRMED_PRESENT_NO_AUTHORITY
    assert store.observe(claim) is OfflineEvidenceResult.DUPLICATE_OFFLINE_NO_AUTHORITY


def test_lost_ack_without_commit_stays_unknown_and_never_auto_retries(tmp_path):
    store = _store(tmp_path)
    claim = _prepare(_fixture())
    injected = SqliteOfflineEvidenceLedger(
        tmp_path / "isolated_fixture.db",
        connection_factory=lambda: _UncertainConnection(tmp_path / "isolated_fixture.db", commit_on_server=False),
    )
    assert injected.observe(claim) is OfflineEvidenceResult.COMMIT_OUTCOME_UNKNOWN
    assert store.reconcile_unknown(claim) is OfflineEvidenceResult.ABSENT_UNCERTAIN_NO_RETRY


def test_rejects_forged_or_incorrect_claim_type(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(EvidencePreparationRejected):
        store.observe({"proof_id": "fake"})
    x = _prepare(_fixture())
    with pytest.raises(EvidencePreparationRejected):
        store.observe(replace(x, logical_sha256="short"))


def test_storage_schema_separate_from_operational_dispatch(tmp_path):
    store = _store(tmp_path)
    connection = sqlite3.connect(str(tmp_path / "isolated_fixture.db"))
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"offline_attested_evidence_claims"}
    columns = {row[1] for row in connection.execute("PRAGMA table_info(offline_attested_evidence_claims)")}
    assert "proof_id" not in columns
    assert "approval_granted" not in columns
    assert "operation_dispatch_claims" not in tables
    connection.close()


def test_no_live_execution_imports_or_data_plane_calls():
    path = Path(__file__).resolve().parents[3] / "src/workflows/incident_resolution/mcp_attested_evidence_store_offline.py"
    content = path.read_text(encoding="utf-8")
    for forbidden in ("DefaultAzureCredential", "CryptographyClient", "az keyvault",
                      "mssql_python.connect", "CREATE ROLE", "CREATE USER",
                      "UPDATE operation_dispatch_claims", "from azure"):
        assert forbidden not in content

@pytest.mark.parametrize("changed_key", ("backend_kid", "attestor_kid"))
def test_same_logical_evidence_different_signer_is_conflict(tmp_path, changed_key):
    """A new signer fingerprint is a conflict, not a byte-identical replay.

    This exercises only SQLite comparison with synthetic values. It cannot
    prove that a new signature is authorized or that two LIVE keys are valid.
    """
    store = _store(tmp_path)
    original = OfflinePreparedEvidenceV2(
        scope="scope-long-enough", issuer="mcp_backend",
        domain="event:MCP_TOOL_DISPATCH_STARTED", operation_id="op-1",
        workflow_id="workflow-1", backend_event_id="event-1",
        backend_request_id="backend-request-1", bridge_id="bridge-1",
        approval_state="PENDING", logical_sha256="a" * 64,
        subject_sha256="b" * 64, backend_kid="c" * 64,
        attestor_kid="d" * 64,
    )
    changed = replace(original, **{changed_key: "e" * 64})
    assert store.observe(original) is OfflineEvidenceResult.NEW_OFFLINE_NO_AUTHORITY
    assert store.observe(changed) is OfflineEvidenceResult.CONFLICT_REJECTED
    assert store.reconcile_unknown(changed) is OfflineEvidenceResult.CONFLICT_REJECTED
    assert store.reconcile_unknown(original) is OfflineEvidenceResult.CONFIRMED_PRESENT_NO_AUTHORITY
