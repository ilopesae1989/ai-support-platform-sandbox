"""F27-B05-T05/T06 adversarial OFFLINE tests. No cloud, DB migrations or LIVE."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import copy
import hashlib
import sqlite3
import threading
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.workflows.incident_resolution.mcp_attested_replay_identity import (
    OfflineReplayIdentity,
    ReplayIdentityNotCertified,
    derive_offline_replay_identity,
)
from src.workflows.incident_resolution.mcp_digest_signing_contract import (
    DigestSigningResult, PinnedDigestSigningPlan, accept_digest_signature,
    prepare_digest_signing_intent,
)
from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier, TrustedPublicKey,
)

SCOPE = "tenant:0cb40b2b-6cfc-4c63-bf7b-da710ea390cb/project:icenter-sbx/f27"
KEY_ID = "https://kv-test-only.vault.azure.net/keys/attestation/0123456789abcdef0123456789abcdef"
OP = "synthetic-operation-01"
KIND = "MCP_APPROVAL_PENDING"
ISSUER = "foundry_adapter"
DOMAIN = "event:" + KIND


def setup():
    private = ec.generate_private_key(ec.SECP256R1())
    public = TrustedPublicKey(
        issuer=ISSUER,
        spki_der=private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        domains=frozenset({DOMAIN}),
    )
    plan = PinnedDigestSigningPlan(
        scope=SCOPE, issuer=ISSUER, domain=DOMAIN, key_id=KEY_ID,
        vault_host="kv-test-only.vault.azure.net", public_key=public,
    )
    verifier = IndependentReceiptVerifier(scope=SCOPE, keys=(public,))
    return private, plan, verifier


def record():
    return {
        "schema_version": "1.0",
        "event_type": KIND,
        "event_id": "event-01",
        "source_component": ISSUER,
        "producer_instance_id": "producer-01",
        "captured_at_utc": "2026-10-28T10:00:00Z",
        "ingested_at_utc": "2026-10-28T10:00:01Z",
        "operation_id": OP,
        "workflow_id": "workflow-01",
        "approval_request_id": "mcpr-01",
        "response_id": "resp-01",
        "source_receipt": {"issuer": ISSUER, "proof_id": "unsigned"},
    }


def seal(private, plan, data):
    unsigned = {k: v for k, v in data.items() if k != "source_receipt"}
    intent = prepare_digest_signing_intent(plan, subject=unsigned)
    der = private.sign(intent.digest_sha256,
                       ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    r, s = utils.decode_dss_signature(der)
    signed = DigestSigningResult(intent.key_id, "ES256",
                                 r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    data["source_receipt"] = accept_digest_signature(plan, intent, signed)
    return data


def derive(data, verifier, **kwargs):
    return derive_offline_replay_identity(
        data, trusted_scope=SCOPE, expected_issuer=ISSUER,
        expected_event_type=KIND, expected_operation_id=OP,
        verifier=verifier, **kwargs,
    )


def test_positive_offline_receipt_yields_identity_but_not_authority():
    private, plan, verifier = setup()
    value = derive(seal(private, plan, record()), verifier)
    assert isinstance(value, OfflineReplayIdentity)
    assert value.issuer == ISSUER
    assert value.operation_id == OP
    assert len(value.logical_sha256) == 64
    assert len(value.subject_sha256) == 64
    assert not hasattr(value, "certified_live")
    assert not hasattr(value, "authorized_dispatch")
    with pytest.raises(FrozenInstanceError):
        value.operation_id = "different"


def test_valid_signatures_for_same_event_share_logical_replay_key():
    private, plan, verifier = setup()
    original = record()
    first = derive(seal(private, plan, copy.deepcopy(original)), verifier)
    second = derive(seal(private, plan, copy.deepcopy(original)), verifier)
    assert first.logical_sha256 == second.logical_sha256
    assert first.subject_sha256 == second.subject_sha256


def test_same_event_key_with_changed_body_must_be_conflict_not_idempotent_success():
    private, plan, verifier = setup()
    a = seal(private, plan, record())
    b = record()
    b["response_id"] = "resp-changed"
    b = seal(private, plan, b)
    first, second = derive(a, verifier), derive(b, verifier)
    assert first.logical_sha256 == second.logical_sha256
    assert first.subject_sha256 != second.subject_sha256


@pytest.mark.parametrize("tamper", [
    ("operation_id", "synthetic-operation-other"),
    ("source_component", "python_governor"),
    ("event_type", "MCP_APPROVAL_DECIDED"),
    ("approval_request_id", "mcpr-changed"),
    ("response_id", "resp-changed"),
    ("event_id", "event-other"),
    ("producer_instance_id", "producer-other"),
])
def test_mutation_after_signature_fails_closed(tamper):
    private, plan, verifier = setup()
    event = seal(private, plan, record())
    event[tamper[0]] = tamper[1]
    with pytest.raises(ReplayIdentityNotCertified):
        derive(event, verifier)


@pytest.mark.parametrize("field", ["operation_id", "event_id", "source_receipt"])
def test_missing_required_field_denied(field):
    private, plan, verifier = setup()
    event = seal(private, plan, record())
    del event[field]
    with pytest.raises(ReplayIdentityNotCertified):
        derive(event, verifier)


def test_expected_operation_not_in_record_denied():
    private, plan, verifier = setup()
    event = seal(private, plan, record())
    with pytest.raises(ReplayIdentityNotCertified):
        derive_offline_replay_identity(
            event, trusted_scope=SCOPE, expected_issuer=ISSUER,
            expected_event_type=KIND,
            expected_operation_id="another-operation", verifier=verifier,
        )


def test_verifier_with_other_scope_cannot_make_positive_identity():
    private, plan, _ = setup()
    event = seal(private, plan, record())
    other = IndependentReceiptVerifier(
        scope="tenant:other/project:other/f27", keys=(plan.public_key,))
    with pytest.raises(ReplayIdentityNotCertified):
        derive(event, other)


def test_cannot_relabel_scope_while_reusing_a_valid_verifier():
    private, plan, verifier = setup()
    event = seal(private, plan, record())
    with pytest.raises(ReplayIdentityNotCertified, match="scope"):
        derive_offline_replay_identity(
            event, trusted_scope="tenant:different/project:other/f27",
            expected_issuer=ISSUER, expected_event_type=KIND,
            expected_operation_id=OP, verifier=verifier,
        )


def test_verifier_is_explicit_cryptographic_type_not_trust_me_boolean():
    with pytest.raises(ReplayIdentityNotCertified):
        derive_offline_replay_identity(
            record(), trusted_scope=SCOPE, expected_issuer=ISSUER,
            expected_event_type=KIND, expected_operation_id=OP,
            verifier=lambda *_a, **_kw: True,
        )


def test_backend_event_without_authenticated_operation_bridge_is_denied():
    private, plan, verifier = setup()
    event = record()
    del event["operation_id"]
    event = seal(private, plan, event)
    with pytest.raises(ReplayIdentityNotCertified):
        derive(event, verifier)


def test_receipt_proof_must_not_be_replay_key():
    private, plan, verifier = setup()
    event = seal(private, plan, record())
    value = derive(event, verifier)
    assert event["source_receipt"]["proof_id"] not in value.logical_sha256


def test_sqlite_fixture_atomic_replay_claim_across_connections(tmp_path):
    """Test-only SQLite fixture; SQL Azure migration/production store NOT implemented."""
    private, plan, verifier = setup()
    first = derive(seal(private, plan, record()), verifier)
    database = tmp_path / "offline-replay-test-only.db"
    with sqlite3.connect(database) as cx:
        cx.execute("CREATE TABLE used(logical_id TEXT PRIMARY KEY, subject_sha256 TEXT NOT NULL)")
        cx.execute("INSERT INTO used VALUES (?, ?)", (first.logical_sha256, first.subject_sha256))
    with sqlite3.connect(database) as cx:
        with pytest.raises(sqlite3.IntegrityError):
            cx.execute("INSERT INTO used VALUES (?, ?)", (first.logical_sha256, first.subject_sha256))


def test_source_contains_no_secret_or_remote_invocation_code():
    source = Path(__file__).resolve().parents[3] / "src/workflows/incident_resolution/mcp_attested_replay_identity.py"
    content = source.read_text(encoding="utf-8")
    for forbidden in (
        "DefaultAzureCredential", "KeyClient(", "CryptographyClient(",
        "az keyvault", "az storage", "subprocess.run(", "requests.get(",
        "INSERT INTO", "delete_record", "claim_dispatch(",
    ):
        assert forbidden not in content
