"""Version-pinned Key Vault ES256 signing adapter for the existing F27 format.

Cryptographic transport only: signing does not authenticate an observation,
prove a provider link, confer approval, or provide durable replay protection.
The backend producer and independent attestor must supply their own validated
subjects. This module is not wired into the served application.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re
from threading import Lock
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from azure.identity import ManagedIdentityCredential
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.workflows.incident_resolution.mcp_receipt_trust import (
    TrustedPublicKey, canonical_subject_v1, parse_subject_json_v1,
    signature_preimage_v1,
)

_API_VERSION = "2025-07-01"
_TOKEN_SCOPE = "https://vault.azure.net/.default"
_MAX_REPLY = 16384


class ReceiptSigningUnavailable(RuntimeError):
    """No usable receipt. The caller must not retry this attempt automatically."""


@dataclass(frozen=True)
class ReceiptManagedIdentity:
    """Explicit selector plus expected principal, not proof of runtime identity.

    A system-assigned identity is selected by omitting SDK client_id only after
    the caller explicitly selects that kind. Principal IDs come from separate
    deployment evidence; effective identity and RBAC require runtime checks.
    """
    kind: str
    principal_id: str
    client_id: str | None = None

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in ("system_assigned", "user_assigned"):
            raise ValueError("Explicit managed identity kind required")
        for value in (self.principal_id,):
            if type(value) is not str or str(UUID(value)) != value or UUID(value).int == 0:
                raise ValueError("Canonical managed identity principal ID required")
        if self.kind == "system_assigned":
            if self.client_id is not None:
                raise ValueError("System-assigned identity cannot select a client ID")
        elif (type(self.client_id) is not str or str(UUID(self.client_id)) != self.client_id
              or UUID(self.client_id).int == 0):
            raise ValueError("User-assigned identity requires a canonical client ID")


@dataclass(frozen=True)
class KeyVaultReceiptPin:
    key_id: str
    managed_identity: ReceiptManagedIdentity
    scope: str
    public_key: TrustedPublicKey

    def __post_init__(self):
        if type(self.key_id) is not str:
            raise ValueError("Versioned Key Vault key ID required")
        p = urlsplit(self.key_id)
        if (p.scheme != "https" or p.query or p.fragment or
                re.fullmatch(r"[a-z][a-z0-9-]{1,22}[a-z0-9]\.vault\.azure\.net", p.netloc) is None or
                re.fullmatch(r"/keys/[A-Za-z0-9-]{1,127}/[a-f0-9]{32}", p.path) is None):
            raise ValueError("Exact public Azure vault and key version required")
        if type(self.managed_identity) is not ReceiptManagedIdentity:
            raise ValueError("Explicit managed identity selector and principal required")
        if type(self.public_key) is not TrustedPublicKey:
            raise ValueError("Independently provisioned public key required")
        for domain in self.public_key.domains:
            signature_preimage_v1(scope=self.scope, issuer=self.public_key.issuer,
                domain=domain, kid=self.public_key.kid, subject={})


def validate_independent_receipt_pins(backend: KeyVaultReceiptPin,
                                      attestor: KeyVaultReceiptPin) -> None:
    """Static separation only; Azure role assignments still require proof."""
    if type(backend) is not KeyVaultReceiptPin or type(attestor) is not KeyVaultReceiptPin:
        raise ValueError("Two explicit receipt pins required")
    if (backend.public_key.issuer != "mcp_backend" or
            attestor.public_key.issuer != "correlation_attestor" or
            backend.scope != attestor.scope or
            backend.public_key.kid == attestor.public_key.kid or
            backend.key_id == attestor.key_id or
            backend.managed_identity.principal_id == attestor.managed_identity.principal_id or
            (backend.managed_identity.client_id is not None and
             backend.managed_identity.client_id == attestor.managed_identity.client_id)):
        raise ValueError("Separate backend and attestor keys and identities required")


@dataclass(frozen=True)
class SignedReceiptSubject:
    canonical_subject: bytes
    issuer: str
    proof_id: str
    key_version_id: str

    @property
    def receipt(self):
        return {"issuer": self.issuer, "proof_id": self.proof_id}


def _reply(raw: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate response member")
            result[key] = value
        return result
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if type(obj) is not dict or set(obj) != {"kid", "value"}:
        raise ValueError("Unexpected signing response")
    return obj


class KeyVaultReceiptSignAttempt:
    """At most one sign POST per object, including failed/uncertain attempts.

    The instance guard is not a durable operation/replay ledger. Do not create
    another instance to retry an uncertain result. Injected clients are for
    tests; use build_managed_identity_sign_attempt for deployed transport.
    """

    def __init__(self, *, pin: KeyVaultReceiptPin, credential, client):
        if type(pin) is not KeyVaultReceiptPin:
            raise ValueError("Explicit receipt signing pin required")
        self.pin, self._credential, self._client = pin, credential, client
        self._lock, self._consumed = Lock(), False

    def sign(self, *, subject_json: bytes, domain: str) -> SignedReceiptSubject:
        # Snapshot and reject unsupported wire data before consuming a request.
        subject = parse_subject_json_v1(subject_json)
        if domain not in self.pin.public_key.domains:
            raise ValueError("Unregistered receipt domain")
        canonical = canonical_subject_v1(subject)
        preimage = signature_preimage_v1(scope=self.pin.scope,
            issuer=self.pin.public_key.issuer, domain=domain,
            kid=self.pin.public_key.kid, subject=subject)
        digest = hashlib.sha256(preimage).digest()
        body = json.dumps({"alg": "ES256", "value": base64.urlsafe_b64encode(digest)
                           .rstrip(b"=").decode("ascii")}, separators=(",", ":")).encode("ascii")
        with self._lock:
            if self._consumed:
                raise ReceiptSigningUnavailable("SIGN_ATTEMPT_ALREADY_CONSUMED")
            self._consumed = True
        try:
            token = self._credential.get_token(_TOKEN_SCOPE).token
            if type(token) is not str or not token or "\r" in token or "\n" in token:
                raise ValueError("Invalid credential result")
            with self._client.stream("POST", self.pin.key_id + "/sign?api-version=" + _API_VERSION,
                    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                             "Accept": "application/json"}, content=body) as response:
                if response.status_code != 200:
                    raise ValueError("Non-success response")
                parts, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_REPLY:
                        raise ValueError("Oversized signing response")
                    parts.append(chunk)
                obj = _reply(b"".join(parts))
            if obj["kid"] != self.pin.key_id:
                raise ValueError("Signing version mismatch")
            encoded = obj["value"]
            if type(encoded) is not str or re.fullmatch(r"[A-Za-z0-9_-]{86}", encoded) is None:
                raise ValueError("Expected P1363 ES256 signature")
            raw = base64.urlsafe_b64decode(encoded + "==")
            if len(raw) != 64 or base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != encoded:
                raise ValueError("Noncanonical ES256 signature")
            der = utils.encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
            public = serialization.load_der_public_key(self.pin.public_key.spki_der)
            public.verify(der, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
            return SignedReceiptSubject(canonical, self.pin.public_key.issuer,
                "es256:v1:" + self.pin.public_key.kid + ":" + encoded, self.pin.key_id)
        except Exception:
            # No response bodies, URLs, tokens or exception details in public errors.
            raise ReceiptSigningUnavailable("SIGN_RESULT_UNUSABLE_NO_RETRY") from None

    def close(self):
        try:
            self._client.close()
        finally:
            self._credential.close()


def build_managed_identity_sign_attempt(pin: KeyVaultReceiptPin) -> KeyVaultReceiptSignAttempt:
    """No CLI/default credential fallback; no automatic sign retry or redirect."""
    if type(pin) is not KeyVaultReceiptPin:
        raise ValueError("Explicit receipt signing pin required")
    identity = pin.managed_identity
    if identity.kind == "system_assigned":
        credential = ManagedIdentityCredential(retry_total=0)
    else:
        credential = ManagedIdentityCredential(client_id=identity.client_id, retry_total=0)
    client = httpx.Client(transport=httpx.HTTPTransport(retries=0),
                         trust_env=False, follow_redirects=False, timeout=20.0)
    return KeyVaultReceiptSignAttempt(pin=pin, credential=credential, client=client)
