"""F27-B05-T04, offline-only ES256 receipt verifier. Product wiring disabled.

No Azure access, signing, private keys, mutable global trust configuration,
network access, persistence, approval authority or replay database.
Not a deployment-ready attestation authority; no LIVE signing authority.

Canonicalization is an intentionally restrictive ASCII/I-JSON v1 profile
covering the existing opaque technical evidence fields. It is NOT a complete
implementation of RFC 8785; it rejects unsupported data rather than guessing.
"""
from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

_MAX_SAFE_INTEGER = (1 << 53) - 1
_MAX_PAYLOAD = 65536
_MAX_DEPTH = 12
_MAX_NODES = 2048
_PREAMBLE = b"AI-SUPPORT-F27-B05-RECEIPT-V1\x00"
_SCOPE_RE = re.compile(r"[A-Za-z0-9._:/-]{8,220}\Z", re.ASCII)
_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,120}\Z", re.ASCII)
_PROOF_RE = re.compile(r"es256:v1:([a-f0-9]{64}):([A-Za-z0-9_-]{86})\Z", re.ASCII)


class UnsupportedEvidence(ValueError):
    """Fail closed when v1 cannot express the evidence unambiguously."""


def _validate_text(value: str) -> str:
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise UnsupportedEvidence("v1 accepts printable ASCII only")
    return value


def _normalize(value: Any, *, depth: int, tally: list[int]) -> Any:
    tally[0] += 1
    if depth > _MAX_DEPTH or tally[0] > _MAX_NODES:
        raise UnsupportedEvidence("Evidence too deeply nested or large")
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        return _validate_text(value)
    if type(value) is int:
        if abs(value) > _MAX_SAFE_INTEGER:
            raise UnsupportedEvidence("Integer outside I-JSON safe range")
        return value
    if type(value) is float:
        if not math.isfinite(value) or not value.is_integer():
            raise UnsupportedEvidence("v1 rejects nonintegral/nonfinite floating point")
        if abs(value) > _MAX_SAFE_INTEGER:
            raise UnsupportedEvidence("Float outside I-JSON safe range")
        return int(value)
    if type(value) in (list, tuple):
        return [_normalize(v, depth=depth + 1, tally=tally) for v in value]
    if isinstance(value, Mapping):
        if len(value) > _MAX_NODES or any(type(k) is not str for k in value):
            raise UnsupportedEvidence("Map keys must be unique strings")
        return {
            _validate_text(key): _normalize(item, depth=depth + 1, tally=tally)
            for key, item in value.items()
        }
    raise UnsupportedEvidence("Unsupported type in receipt subject")


def canonical_subject_v1(subject: Mapping[str, object]) -> bytes:
    """Deterministic UTF-8 JSON in a narrow, reject-unsupported data profile.

    The ingestion JSON parser MUST reject duplicate keys before constructing
    this Mapping, since a dict cannot retain information about duplicates.
    """
    if not isinstance(subject, Mapping):
        raise UnsupportedEvidence("Subject must be a map")
    norm = _normalize(subject, depth=0, tally=[0])
    payload = json.dumps(norm, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(payload) > _MAX_PAYLOAD:
        raise UnsupportedEvidence("Subject exceeds size limit")
    return payload



def parse_subject_json_v1(data: bytes) -> Mapping[str, object]:
    """Reject duplicate JSON members before a subject reaches the verifier.

    Callers must also reject duplicate keys in the enclosing evidence bundle.
    This parser handles one receipt subject only. JSON numeric tokens are
    converted without binary-float rounding; integral decimals normalize to
    integers and genuinely fractional values fail closed. A Mapping provided
    directly to canonical_subject_v1 cannot recover lost wire precision.
    """
    if type(data) is not bytes or not data or len(data) > _MAX_PAYLOAD:
        raise UnsupportedEvidence("Invalid subject JSON byte length")

    def pairs_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise UnsupportedEvidence("Duplicate JSON property")
            result[key] = value
        return result

    def unsupported_constant(value: str) -> object:
        raise UnsupportedEvidence("JSON nonfinite constant is forbidden")

    def safe_integer(token: str) -> int:
        # Keep parsing bounded regardless of Python's configurable int limit.
        if len(token.lstrip("-")) > 16:
            raise UnsupportedEvidence("JSON integer outside I-JSON safe range")
        number = int(token)
        if abs(number) > _MAX_SAFE_INTEGER:
            raise UnsupportedEvidence("JSON integer outside I-JSON safe range")
        return number

    def exact_integral_decimal(token: str) -> int:
        # json.loads(..., parse_float=float) can round distinct wire values to
        # the same integer (e.g. 1.0000000000000001 or 1e-9999).
        # Parse the lexical JSON token exactly before any canonicalization.
        number = Decimal(token)
        if not number.is_finite():
            raise UnsupportedEvidence("Nonfinite JSON decimal is forbidden")
        if number.is_zero():
            return 0
        if number.adjusted() < 0 or number.adjusted() > 15:
            raise UnsupportedEvidence("JSON decimal outside integral safe range")
        if number != number.to_integral_value():
            raise UnsupportedEvidence("Nonintegral JSON decimal is forbidden")
        integer = int(number)
        if abs(integer) > _MAX_SAFE_INTEGER:
            raise UnsupportedEvidence("JSON decimal outside I-JSON safe range")
        return integer

    try:
        subject = json.loads(data.decode("utf-8", errors="strict"),
                             object_pairs_hook=pairs_unique,
                             parse_constant=unsupported_constant,
                             parse_int=safe_integer,
                             parse_float=exact_integral_decimal)
    except UnsupportedEvidence:
        raise
    except (UnicodeError, ValueError, RecursionError, OverflowError,
            InvalidOperation) as exc:
        raise UnsupportedEvidence("Invalid subject JSON") from exc
    canonical_subject_v1(subject)
    return subject


def signature_preimage_v1(*, scope: str, issuer: str, domain: str,
                          kid: str, subject: Mapping[str, object]) -> bytes:
    """Public v1 signing contract, NOT an authority to sign.

    Signer must sign exactly these bytes once with ES256 and use the P1363 64
    byte signature output. In Key Vault .NET SignDataAsync hashes internally;
    SignAsync hashes externally prepared 32-byte digest. Never use both hashes.
    """
    for value, pattern in ((scope, _SCOPE_RE), (issuer, _ID_RE),
                           (domain, _ID_RE)):
        if type(value) is not str or pattern.fullmatch(value) is None:
            raise UnsupportedEvidence("Invalid signing context")
    if type(kid) is not str or re.fullmatch(r"[a-f0-9]{64}", kid) is None:
        raise UnsupportedEvidence("Invalid public key fingerprint")
    return (_PREAMBLE + scope.encode("ascii") + b"\x00"
            + issuer.encode("ascii") + b"\x00"
            + domain.encode("ascii") + b"\x00"
            + kid.encode("ascii") + b"\x00"
            + canonical_subject_v1(subject))


@dataclass(frozen=True)
class TrustedPublicKey:
    """A trusted, out-of-band provisioned public key for exactly one issuer."""

    issuer: str
    spki_der: bytes
    domains: frozenset[str]

    def __post_init__(self) -> None:
        if type(self.issuer) is not str or not _ID_RE.fullmatch(self.issuer):
            raise ValueError("Invalid issuer")
        if not isinstance(self.spki_der, bytes) or not self.spki_der:
            raise ValueError("Public key must be DER SPKI bytes")
        if (not isinstance(self.domains, frozenset) or not self.domains or
                any(type(d) is not str or _ID_RE.fullmatch(d) is None
                    for d in self.domains)):
            raise ValueError("Explicit, valid allowed domains required")
        pub = serialization.load_der_public_key(self.spki_der)
        if not isinstance(pub, ec.EllipticCurvePublicKey) or not isinstance(pub.curve, ec.SECP256R1):
            raise ValueError("Trusted key must use P-256")
        if pub.public_bytes(serialization.Encoding.DER,
                            serialization.PublicFormat.SubjectPublicKeyInfo) != self.spki_der:
            raise ValueError("Public key DER must be canonical")

    @property
    def kid(self) -> str:
        return hashlib.sha256(self.spki_der).hexdigest()


class IndependentReceiptVerifier:
    """Callable for mcp_backend_evidence_contract.verify_receipt=...

    Keys must originate from independently approved trust material, never
    from the record being checked or from an authenticated-by-itself blob.
    """

    def __init__(self, *, scope: str, keys: tuple[TrustedPublicKey, ...]):
        if type(scope) is not str or _SCOPE_RE.fullmatch(scope) is None:
            raise ValueError("A fixed, trusted scope is required")
        if not isinstance(keys, tuple) or not keys:
            raise ValueError("At least one trusted public key required")
        registry: dict[tuple[str, str], tuple[ec.EllipticCurvePublicKey, frozenset[str]]] = {}
        owner_by_kid: dict[str, str] = {}
        for item in keys:
            if not isinstance(item, TrustedPublicKey):
                raise ValueError("All trusted keys must be explicitly registered")
            if item.kid in owner_by_kid and owner_by_kid[item.kid] != item.issuer:
                raise ValueError("Cannot trust the same signing key for multiple issuers")
            owner_by_kid[item.kid] = item.issuer
            index = (item.issuer, item.kid)
            if index in registry:
                raise ValueError("Duplicate trusted key entry")
            registry[index] = (
                serialization.load_der_public_key(item.spki_der), item.domains
            )
        self._scope = scope
        self._registry = MappingProxyType(registry)

    def __call__(self, receipt: object, *, subject_kind: object, subject: object) -> bool:
        try:
            if not isinstance(receipt, Mapping) or set(receipt) != {"issuer", "proof_id"}:
                return False
            issuer = receipt["issuer"]
            proof_id = receipt["proof_id"]
            if type(issuer) is not str or type(proof_id) is not str:
                return False
            match = _PROOF_RE.fullmatch(proof_id)
            if match is None or type(subject_kind) is not str or not isinstance(subject, Mapping):
                return False
            kid, sig64 = match.groups()
            registered = self._registry.get((issuer, kid))
            if registered is None:
                return False
            key, domains = registered
            if subject_kind not in domains:
                return False
            raw = base64.urlsafe_b64decode(sig64 + "==")
            if (len(raw) != 64 or
                    base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != sig64):
                return False
            preimage = signature_preimage_v1(scope=self._scope, issuer=issuer,
                                             domain=subject_kind, kid=kid,
                                             subject=subject)
            der = utils.encode_dss_signature(
                int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
            key.verify(der, preimage, ec.ECDSA(hashes.SHA256()))
            return True
        except (InvalidSignature, ValueError, TypeError, OverflowError, KeyError):
            return False
