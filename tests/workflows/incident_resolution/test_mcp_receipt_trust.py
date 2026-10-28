"""OFFLINE ONLY. Test signing keys here are ephemeral and never deployed."""
import base64
import copy
from pathlib import Path
import runpy
import sys

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.workflows.incident_resolution.mcp_receipt_trust import (
    IndependentReceiptVerifier,
    TrustedPublicKey,
    UnsupportedEvidence,
    canonical_subject_v1,
    signature_preimage_v1,
    parse_subject_json_v1,
)

SCOPE = "tenant:0cb40b2b-6cfc-4c63-bf7b-da710ea390cb/project:icenter-sbx/f27"
SCOPE_OTHER = "tenant:11111111-1111-1111-1111-111111111111/project:other/f27"
DOM = "backend_provenance"
SUBJECT = {
    "attested_release": True,
    "image_fingerprint": "hmac:synthetic-image-1",
    "revision_fingerprint": "hmac:synthetic-revision-1",
    "sample_ratio": 1.0,
    "nested": {"a": [False, None, 1]},
}


def new_fixture():
    private = ec.generate_private_key(ec.SECP256R1())
    spki = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    root = TrustedPublicKey(issuer="mcp_backend", spki_der=spki,
                            domains=frozenset({DOM, "correlation"}))
    verifier = IndependentReceiptVerifier(scope=SCOPE, keys=(root,))
    return private, root, verifier


def seal(private, root, data=SUBJECT, domain=DOM, scope=SCOPE):
    message = signature_preimage_v1(scope=scope, issuer=root.issuer,
                                    domain=domain, kid=root.kid, subject=data)
    der = private.sign(message, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return {"issuer": root.issuer,
            "proof_id": "es256:v1:" + root.kid + ":" +
                         base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")}


def test_accept_and_reject_mutations():
    private, root, verifier = new_fixture()
    receipt = seal(private, root)
    assert verifier(receipt, subject_kind=DOM, subject=SUBJECT) is True
    bad = copy.deepcopy(SUBJECT)
    bad["attested_release"] = False
    assert verifier(receipt, subject_kind=DOM, subject=bad) is False
    bad = copy.deepcopy(SUBJECT)
    bad["nested"]["a"][2] = 9
    assert verifier(receipt, subject_kind=DOM, subject=bad) is False
    assert verifier(receipt, subject_kind="correlation", subject=SUBJECT) is False
    assert verifier(receipt, subject_kind="operation", subject=SUBJECT) is False
    assert verifier(receipt, subject_kind=DOM, subject={**SUBJECT, "extra": True}) is False


def test_signer_separation_and_rotation_allowlist():
    private, root, verifier = new_fixture()
    receipt = seal(private, root)
    altered = {**receipt, "issuer": "coverage_sensor"}
    assert not verifier(altered, subject_kind=DOM, subject=SUBJECT)
    alternate = ec.generate_private_key(ec.SECP256R1())
    alt_spki = alternate.public_key().public_bytes(serialization.Encoding.DER,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo)
    alt_root = TrustedPublicKey("mcp_backend", alt_spki, frozenset({DOM}))
    assert not verifier(seal(alternate, alt_root), subject_kind=DOM, subject=SUBJECT)
    # A multi-key trust list is explicit, not inferred from untrusted receipts.
    rotated = IndependentReceiptVerifier(scope=SCOPE, keys=(root, alt_root))
    assert rotated(seal(alternate, alt_root), subject_kind=DOM, subject=SUBJECT)
    assert rotated(receipt, subject_kind=DOM, subject=SUBJECT)
    # A key must never be shared by two logical issuers.
    with pytest.raises(ValueError, match="multiple issuers"):
        IndependentReceiptVerifier(scope=SCOPE, keys=(
            root, TrustedPublicKey("coverage_sensor", root.spki_der, frozenset({"coverage"}))))


def test_wrong_scope_fails():
    private, root, _ = new_fixture()
    wrong = IndependentReceiptVerifier(scope=SCOPE_OTHER, keys=(root,))
    assert not wrong(seal(private, root), subject_kind=DOM, subject=SUBJECT)


def test_bad_receipts_fail_closed():
    private, root, verifier = new_fixture()
    receipt = seal(private, root)
    proof = receipt["proof_id"]
    cases = [
        {}, None, "trusted", {"issuer": "mcp_backend"},
        {"issuer": "mcp_backend", "proof_id": proof, "extra": True},
        {"issuer": "mcp_backend", "proof_id": "synthetic:test-proof"},
        {"issuer": "mcp_backend", "proof_id": proof.replace(":v1:", ":v2:")},
        {"issuer": "mcp_backend", "proof_id": proof[:-1] + "!"},
        {"issuer": "mcp_backend", "proof_id": proof + "="},
        {"issuer": "mcp_backend", "proof_id": proof[:9] + "0" * 64 + proof[73:]},
        {"issuer": "coverage_sensor", "proof_id": proof},
    ]
    for item in cases:
        assert verifier(item, subject_kind=DOM, subject=SUBJECT) is False
    # Signature bit flip in the 64-byte raw signature.
    prefix, kid, encoded = proof.rsplit(":", 2)
    raw = bytearray(base64.urlsafe_b64decode(encoded + "=="))
    raw[0] ^= 1
    forged = {"issuer": "mcp_backend", "proof_id":
              prefix + ":" + kid + ":" +
              base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")}
    assert not verifier(forged, subject_kind=DOM, subject=SUBJECT)


def test_canonical_ascii_profile():
    assert canonical_subject_v1({"z": 1.0, "a": [True, 1]}) == b'{"a":[true,1],"z":1}'
    assert canonical_subject_v1({"a": 1}) == canonical_subject_v1({"a": 1.0})
    assert canonical_subject_v1({"a": -0.0}) == b'{"a":0}'
    assert canonical_subject_v1({"key": "plain ascii\\and quote\""}) == (
        b'{"key":"plain ascii\\\\and quote\\\""}'
    )


@pytest.mark.parametrize("subject", [
    {"a": "Espa\u00f1a"},
    {"a": 1.25},
    {"a": float("nan")},
    {"a": float("inf")},
    {"a": 2 ** 53},
    {"a": object()},
    {"a": b"unsupported"},
    {"a": "control\nchar"},
    {"a": {1: "bad-key"}},
    {"a": [1] * 2049},
])
def test_reject_outside_canonical_subset(subject):
    with pytest.raises(UnsupportedEvidence):
        canonical_subject_v1(subject)



def test_parser_rejects_duplicate_members_and_invalid_json():
    assert parse_subject_json_v1(b'{"b":true,"a":1}') == {"b": True, "a": 1}
    for value in (b'{"a":1,"a":2}', b'{"outer":{"x":1,"x":2}}',
                  b'{"a":NaN}', b'{"a":1.25}', b'{"a":"\\ud800"}',
                  b'[]', b'null', b'{}x',
                  b'{"a":' + b'9' * 4500 + b'}',
                  b'{"a":' + b'[' * 12000 + b'0' + b']' * 12000 + b'}'):
        with pytest.raises(UnsupportedEvidence):
            parse_subject_json_v1(value)


@pytest.mark.parametrize("raw", [
    b'{"a":1.0000000000000001}',
    b'{"a":0.99999999999999999}',
    b'{"a":1e-9999}',
    b'{"a":1e1000000}',
    b'{"a":9007199254740992.0}',
    b'{"a":9007199254740992}',
    b'{"a":1e99999999999999999999999}',
    b'{"a":-1.00000000000000001}',
])
def test_parser_rejects_decimal_rounding_and_unsafe_magnitudes(raw):
    with pytest.raises(UnsupportedEvidence):
        parse_subject_json_v1(raw)


def test_exact_integral_decimal_json_compatibility():
    raw = b'{"z":1.0,"a":[1e2,-0.0],"zero":0.000,"v":1.0000000000000}'
    parsed = parse_subject_json_v1(raw)
    assert parsed == {"z": 1, "a": [100, 0], "zero": 0, "v": 1}
    assert type(parsed["z"]) is int
    assert type(parsed["a"][0]) is int
    assert canonical_subject_v1(parsed) == (
        b'{"a":[100,0],"v":1,"z":1,"zero":0}'
    )
    assert parse_subject_json_v1(b'{"a":9007199254740991.0}') == {
        "a": 9007199254740991
    }


def test_public_key_validation():
    private = ec.generate_private_key(ec.SECP384R1())
    spki = private.public_key().public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(ValueError, match="P-256"):
        TrustedPublicKey("mcp_backend", spki, frozenset({DOM}))


def test_no_private_keys_or_azure_configuration_in_verifier():
    import inspect
    import src.workflows.incident_resolution.mcp_receipt_trust as mod
    source = inspect.getsource(mod)
    forbidden = ("DefaultAzureCredential", "az keyvault", "create_key(", "sign_data(",
                 "generate_private_key", "requests.get", "urllib.request", "sys.exit(")
    for x in forbidden:
        assert x not in source


def test_full_original_contract_integration_offline():
    """Real contract integration (still OFFLINE and synthetic signing keys)."""
    repo = Path(__file__).resolve().parents[3]
    contract_file = repo / "src/workflows/incident_resolution/mcp_backend_evidence_contract.py"
    fixture_file = repo / "tests/workflows/incident_resolution/test_mcp_backend_evidence_attestation.py"
    assert contract_file.is_file() and fixture_file.is_file()
    sys.path.insert(0, str(repo))
    import importlib
    contract = importlib.import_module("src.workflows.incident_resolution.mcp_backend_evidence_contract")
    historical = runpy.run_path(str(fixture_file))
    bundle = historical["_ready"]()
    grants = {
        "python_governor": {
            "operation", "event:OPERATION_AUTHORITY_VALIDATED",
            "event:MCP_APPROVAL_PENDING", "event:MCP_APPROVAL_DECIDED",
            "event:OPERATION_EVIDENCE_COMMITTED",
        },
        "foundry_adapter": {"event:MCP_APPROVAL_PENDING", "event:MCP_APPROVAL_DECIDED"},
        "mcp_backend": {"correlation", "backend_provenance",
                        "event:MCP_HTTP_AUTH_EVALUATED",
                        "event:MCP_TOOL_DISPATCH_STARTED",
                        "event:MCP_TOOL_DISPATCH_FINISHED"},
        "coverage_sensor": {"coverage"},
        "evidence_store": {"event:OPERATION_EVIDENCE_COMMITTED"},
    }
    signing = {}
    roots = []
    for name, allowed in grants.items():
        private = ec.generate_private_key(ec.SECP256R1())
        spki = private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        root = TrustedPublicKey(name, spki, frozenset(allowed))
        signing[name] = (private, root)
        roots.append(root)

    def reseal(record, domain):
        issuer = record["source_receipt"]["issuer"]
        subject = {key: value for key, value in record.items() if key != "source_receipt"}
        record["source_receipt"] = seal(*signing[issuer], data=subject, domain=domain)

    reseal(bundle["operation"], "operation")
    for section in ("consumer_events", "backend_events"):
        for ev in bundle[section]:
            reseal(ev, "event:" + ev["event_type"])
    for section in ("correlation", "coverage", "backend_provenance"):
        reseal(bundle[section], section)
    verifier = IndependentReceiptVerifier(scope=SCOPE, keys=tuple(roots))
    result = contract.verify_backend_evidence(bundle, verify_receipt=verifier)
    assert result == "VERIFIED_NO_GROUP_LIST_DISPATCH_DURING_PENDING", result
    altered = copy.deepcopy(bundle)
    altered["backend_provenance"]["attested_release"] = False
    assert contract.verify_backend_evidence(altered, verify_receipt=verifier) == "NOT_CERTIFIED"
