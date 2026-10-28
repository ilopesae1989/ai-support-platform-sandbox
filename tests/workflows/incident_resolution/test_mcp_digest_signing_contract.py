"""F27-B05-T03/T04 OFFLINE tests; ephemeral in-memory keys, NO Azure SDK.

The local signer simulates exactly Key Vault Sign(digest, algorithm=ES256).
It never calls Azure or proves any LIVE principal, role or sign capability.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier, TrustedPublicKey,
)
from src.workflows.incident_resolution.mcp_digest_signing_contract import (
    DigestSigningContractError,
    DigestSigningResult,
    PinnedDigestSigningPlan,
    accept_digest_signature,
    prepare_digest_signing_intent,
)

SCOPE = "tenant:0cb40b2b-6cfc-4c63-bf7b-da710ea390cb/project:icenter-sbx/f27"
URI = "https://kv-example-sandbox.vault.azure.net/keys/receipt-signing-test/0123456789abcdef0123456789abcdef"
ISSUER = "mcp_backend"
DOMAIN = "backend_provenance"
SUBJECT = {"attested_release": True, "revision_fingerprint": "hmac:offline-rev-1", "value": 1.0}


def fixture():
    private = ec.generate_private_key(ec.SECP256R1())  # TEST-ONLY
    spki = private.public_key().public_bytes(serialization.Encoding.DER,
                                              serialization.PublicFormat.SubjectPublicKeyInfo)
    public = TrustedPublicKey(issuer=ISSUER, spki_der=spki,
                              domains=frozenset({DOMAIN, "correlation"}))
    plan = PinnedDigestSigningPlan(scope=SCOPE, issuer=ISSUER, domain=DOMAIN,
                                   key_id=URI, vault_host="kv-example-sandbox.vault.azure.net",
                                   public_key=public)
    return private, public, plan


def mock_keyvault_sign(private, intent):
    # Key Vault Sign signs an already SHA-256 hashed digest; Prehashed prevents
    # accidentally hashing the digest a second time in this OFFLINE fixture.
    assert len(intent.digest_sha256) == 32
    der = private.sign(intent.digest_sha256,
                       ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    r, s = utils.decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return DigestSigningResult(key_id=intent.key_id, algorithm="ES256", signature=raw)


def test_offline_digest_is_preimage_sha256_exactly_once():
    private, public, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    from src.workflows.incident_resolution.mcp_receipt_trust import signature_preimage_v1
    expected = signature_preimage_v1(scope=SCOPE, issuer=ISSUER,
                                     domain=DOMAIN, kid=public.kid, subject=SUBJECT)
    assert intent.digest_sha256 == hashlib.sha256(expected).digest()
    assert intent.digest_sha256 != hashlib.sha256(hashlib.sha256(expected).digest()).digest()
    assert intent.subject_canonical_json == b'{"attested_release":true,"revision_fingerprint":"hmac:offline-rev-1","value":1}'


def test_accepts_keyvault_compatible_raw_p1363_signature_offline():
    private, public, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    signed = mock_keyvault_sign(private, intent)
    receipt = accept_digest_signature(plan, intent, signed)
    assert set(receipt) == {"issuer", "proof_id"}
    assert receipt["issuer"] == ISSUER
    assert receipt["proof_id"].startswith("es256:v1:" + public.kid + ":")
    verifier = IndependentReceiptVerifier(scope=SCOPE, keys=(public,))
    assert verifier(receipt, subject_kind=DOMAIN, subject=SUBJECT)
    assert not verifier(receipt, subject_kind=DOMAIN,
                        subject={**SUBJECT, "value": 9})


@pytest.mark.parametrize("bad_key", [
    "https://kv-example-sandbox.vault.azure.net/keys/receipt-signing-test",  # unpinned
    "http://kv-example-sandbox.vault.azure.net/keys/receipt-signing-test/0123456789abcdef0123456789abcdef",
    "https://kv-example-sandbox.vault.azure.net/keys/receipt-signing-test/latest",
    URI + "?api-version=7.4",
    URI + "#fragment",
    URI.replace("https://", "https://user@"),
    URI.replace(".net/keys/", ".net:8443/keys/"),
    URI.replace(".net/keys/", ".net:bad/keys/"),
    URI + "/",
    URI.replace("/keys/", "/secrets/"),
    URI.replace("https://", "HTTPS://"),
    URI.replace("0123456789abcdef0123456789abcdef", "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"),
])
def test_unpinned_or_ambiguous_key_id_rejected(bad_key):
    _, _, plan = fixture()
    with pytest.raises(DigestSigningContractError):
        replace(plan, key_id=bad_key)


def test_different_vault_host_rejected():
    _, _, plan = fixture()
    with pytest.raises(DigestSigningContractError):
        replace(plan, vault_host="another-vault.vault.azure.net")


def test_cannot_use_key_registered_to_another_issuer():
    _, _, plan = fixture()
    with pytest.raises(DigestSigningContractError):
        replace(plan, issuer="coverage_sensor")


def test_cannot_use_key_for_unapproved_domain():
    _, _, plan = fixture()
    with pytest.raises(DigestSigningContractError):
        replace(plan, domain="operation")


def test_intent_is_immutable_snapshot_from_mutable_subject():
    private, _, plan = fixture()
    original = {"source": {"items": [True, 1]}}
    intent = prepare_digest_signing_intent(plan, subject=original)
    original["source"]["items"].append(False)
    assert b"false" not in intent.subject_canonical_json
    assert accept_digest_signature(plan, intent, mock_keyvault_sign(private, intent))
    with pytest.raises(FrozenInstanceError):
        intent.issuer = "coverage_sensor"


@pytest.mark.parametrize("alteration", [
    {"source_receipt": {"issuer": ISSUER}},
    {"value": 1.5},
    {"text": "Espa\u00f1a"},
    {"bytes": b"not JSON"},
])
def test_invalid_or_recursive_subject_rejected(alteration):
    _, _, plan = fixture()
    with pytest.raises(DigestSigningContractError):
        prepare_digest_signing_intent(plan, subject=alteration)


def test_rejects_wrong_key_version_before_acceptance():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    signed = mock_keyvault_sign(private, intent)
    signed = replace(signed, key_id=URI.replace("0123456789abcdef", "1111111111111111"))
    with pytest.raises(DigestSigningContractError):
        accept_digest_signature(plan, intent, signed)


def test_rejects_bad_algorithm_and_signature_shape():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    signed = mock_keyvault_sign(private, intent)
    for value in [replace(signed, algorithm="RS256"),
                  replace(signed, signature=b"bad"),
                  replace(signed, signature=bytearray(signed.signature)),
                  replace(signed, signature=signed.signature + b"0")]:
        with pytest.raises(DigestSigningContractError):
            accept_digest_signature(plan, intent, value)


def test_wrong_signing_key_rejected_cryptographically():
    _, _, plan = fixture()
    other = ec.generate_private_key(ec.SECP256R1())
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    with pytest.raises(DigestSigningContractError, match="signature not valid"):
        accept_digest_signature(plan, intent, mock_keyvault_sign(other, intent))


def test_double_hashed_signature_rejected():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    der = private.sign(intent.digest_sha256, ec.ECDSA(hashes.SHA256()))  # WRONG: hashes digest again
    r, s = utils.decode_dss_signature(der)
    bad = DigestSigningResult(intent.key_id, "ES256", r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    with pytest.raises(DigestSigningContractError, match="signature not valid"):
        accept_digest_signature(plan, intent, bad)


def test_tampered_intent_digest_rejected():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    altered = replace(intent, digest_sha256=b"\0" * 32)
    with pytest.raises(DigestSigningContractError):
        accept_digest_signature(plan, altered, mock_keyvault_sign(private, altered))


def test_tampered_intent_subject_rejected():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    altered = replace(intent, subject_canonical_json=b'{"attested_release":false}')
    with pytest.raises(DigestSigningContractError):
        accept_digest_signature(plan, altered, mock_keyvault_sign(private, altered))


def test_mismatched_scope_rejected_even_with_same_key():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    different_plan = replace(plan, scope="tenant:different/project:other/f27")
    signed = mock_keyvault_sign(private, intent)
    with pytest.raises(DigestSigningContractError):
        accept_digest_signature(different_plan, intent, signed)


def test_distinct_signature_bytes_do_not_serve_as_replay_identity():
    private, _, plan = fixture()
    intent = prepare_digest_signing_intent(plan, subject=SUBJECT)
    # ECDSA may produce distinct valid signatures for the same logical subject.
    # This test asserts logical identity is stable, NOT signature byte distinctness.
    first = accept_digest_signature(plan, intent, mock_keyvault_sign(private, intent))
    second = accept_digest_signature(plan, intent, mock_keyvault_sign(private, intent))
    assert first["issuer"] == second["issuer"]
    assert intent.digest_sha256 == hashlib.sha256(
        __import__("src.workflows.incident_resolution.mcp_receipt_trust", fromlist=["signature_preimage_v1"]).signature_preimage_v1(
            scope=plan.scope, issuer=plan.issuer, domain=plan.domain,
            kid=plan.public_key.kid, subject=SUBJECT
        )).digest()
    # A verifier accepting both is NOT anti-replay; durable uniqueness is a separate gate.


def test_module_has_no_azure_credential_or_network_dependency():
    import inspect
    import src.workflows.incident_resolution.mcp_digest_signing_contract as mod
    text = inspect.getsource(mod)
    for forbidden in ("DefaultAzureCredential", "KeyClient(", "CryptographyClient(",
                      "create_key(", "az keyvault", "subprocess.run(", "requests.get(",
                      "shell=True", "ManagedIdentityCredential("):
        assert forbidden not in text
