"""F27-B05-T03/T04: OFFLINE digest-signing contract; NOT product wiring.

This module NEVER connects to Azure, obtains credentials, creates keys, signs,
changes RBAC, calls MCP, approves requests or grants operational authority.
It prepares a digest to be signed by a separate, approved signer and validates
its returned public signature against an out-of-band pinned public key.

Production integration, trust anchor enrollment, signature authority, signer
separation, key lifecycle and replay resistance remain separate gates.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import re
from typing import Mapping
from urllib.parse import urlsplit

from .mcp_receipt_trust import (
    IndependentReceiptVerifier,
    TrustedPublicKey,
    UnsupportedEvidence,
    canonical_subject_v1,
    parse_subject_json_v1,
    signature_preimage_v1,
)

_KEY_NAME = re.compile(r"[A-Za-z0-9-]{1,127}\Z", re.ASCII)
_KEY_VERSION = re.compile(r"[0-9a-fA-F]{32}\Z", re.ASCII)


class DigestSigningContractError(ValueError):
    """A proposed signature violates the OFFLINE pinned signing contract."""


def _validate_pinned_key_id(value: str) -> tuple[str, str, str]:
    """Require a versioned HTTPS Key Vault key URI; no latest or unpinned ID."""
    if type(value) is not str or not value.startswith("https://"):
        raise DigestSigningContractError("key ID must have canonical HTTPS prefix")
    try:
        uri = urlsplit(value)
    except ValueError as exc:
        raise DigestSigningContractError("invalid key URI") from exc
    try:
        noncanonical_authority = (uri.username is not None or uri.password is not None
                                  or uri.port is not None)
    except ValueError as exc:
        raise DigestSigningContractError("invalid key URI port") from exc
    if (uri.scheme != "https" or not uri.hostname or noncanonical_authority
            or uri.query or uri.fragment or uri.netloc != uri.hostname
            or re.fullmatch(r"[a-z0-9][a-z0-9.-]*", uri.hostname) is None):
        raise DigestSigningContractError("key ID must be a pinned HTTPS key URI")
    components = uri.path.split("/")
    if (len(components) != 4 or components[0] != ""
            or components[1] != "keys"
            or not _KEY_NAME.fullmatch(components[2])
            or not _KEY_VERSION.fullmatch(components[3])):
        raise DigestSigningContractError("key ID must contain /keys/<name>/<version>")
    if "%" in value or "@" in value or "\\" in value:
        raise DigestSigningContractError("encoded/ambiguous key URIs are forbidden")
    return uri.hostname, components[2], components[3]


@dataclass(frozen=True)
class PinnedDigestSigningPlan:
    """Provisioned from approved config, never constructed from a receipt.

    `key_id` is the actual *versioned* Key Vault signing URI. `public_key`
    must be independently approved DER/SPKI; its SHA256 is the receipt `kid`,
    distinct from the version component of `key_id`.
    """
    scope: str
    issuer: str
    domain: str
    key_id: str
    vault_host: str
    public_key: TrustedPublicKey

    def __post_init__(self) -> None:
        host, _, _ = _validate_pinned_key_id(self.key_id)
        if (type(self.vault_host) is not str or host != self.vault_host
                or self.public_key.issuer != self.issuer
                or self.domain not in self.public_key.domains):
            raise DigestSigningContractError("untrusted or mismatched signing plan")
        # Validate scope, issuer, domain, public kid using the existing contract.
        try:
            signature_preimage_v1(scope=self.scope, issuer=self.issuer,
                                  domain=self.domain, kid=self.public_key.kid,
                                  subject={"offline_contract_check": True})
        except (UnsupportedEvidence, ValueError, TypeError) as exc:
            raise DigestSigningContractError("invalid signing scope or domain") from exc


@dataclass(frozen=True)
class DigestSigningIntent:
    """Immutable digest/signing inputs; a proposal, never an authorization."""
    key_id: str
    issuer: str
    domain: str
    kid: str
    scope: str
    subject_canonical_json: bytes
    digest_sha256: bytes


@dataclass(frozen=True)
class DigestSigningResult:
    """Public projection of a provider result (no credential/private material)."""
    key_id: str
    algorithm: str
    signature: bytes


def prepare_digest_signing_intent(
    plan: PinnedDigestSigningPlan, *, subject: Mapping[str, object],
) -> DigestSigningIntent:
    """Prepare SHA256(signature_preimage_v1) exactly once; NO SIGN is done."""
    if type(plan) is not PinnedDigestSigningPlan or not isinstance(subject, Mapping):
        raise DigestSigningContractError("explicit signing plan and subject required")
    if "source_receipt" in subject:
        raise DigestSigningContractError("source_receipt must not sign itself")
    try:
        canonical = canonical_subject_v1(subject)
        preimage = signature_preimage_v1(
            scope=plan.scope, issuer=plan.issuer, domain=plan.domain,
            kid=plan.public_key.kid, subject=subject,
        )
    except (UnsupportedEvidence, ValueError, TypeError) as exc:
        raise DigestSigningContractError("unsupported evidence") from exc
    return DigestSigningIntent(
        key_id=plan.key_id, issuer=plan.issuer, domain=plan.domain,
        kid=plan.public_key.kid, scope=plan.scope,
        subject_canonical_json=canonical,
        digest_sha256=hashlib.sha256(preimage).digest(),
    )


def accept_digest_signature(
    plan: PinnedDigestSigningPlan,
    intent: DigestSigningIntent,
    signed: DigestSigningResult,
) -> dict[str, str]:
    """Accept a provider result ONLY after verifying the exact pinned subject.

    Signers perform their own access controls. This function neither calls nor
    authorizes them. Caller must persist/replay-protect the operation elsewhere.
    """
    if (type(plan) is not PinnedDigestSigningPlan
            or type(intent) is not DigestSigningIntent
            or type(signed) is not DigestSigningResult):
        raise DigestSigningContractError("invalid signing result contract")
    if (signed.key_id != plan.key_id or signed.key_id != intent.key_id
            or signed.algorithm != "ES256"
            or type(signed.signature) is not bytes
            or len(signed.signature) != 64):
        raise DigestSigningContractError("algorithm, key version or signature mismatch")
    if (intent.issuer != plan.issuer or intent.domain != plan.domain
            or intent.scope != plan.scope or intent.kid != plan.public_key.kid
            or type(intent.subject_canonical_json) is not bytes
            or type(intent.digest_sha256) is not bytes
            or len(intent.digest_sha256) != 32):
        raise DigestSigningContractError("signing intent differs from trust policy")
    try:
        subject = parse_subject_json_v1(intent.subject_canonical_json)
        check = prepare_digest_signing_intent(plan, subject=subject)
    except (ValueError, TypeError, UnsupportedEvidence) as exc:
        raise DigestSigningContractError("invalid canonical subject") from exc
    if check != intent:
        raise DigestSigningContractError("digest or canonical subject mismatch")
    proof = ("es256:v1:" + intent.kid + ":"
             + base64.urlsafe_b64encode(signed.signature).rstrip(b"=").decode("ascii"))
    receipt = {"issuer": plan.issuer, "proof_id": proof}
    verifier = IndependentReceiptVerifier(scope=plan.scope, keys=(plan.public_key,))
    if verifier(receipt, subject_kind=plan.domain, subject=subject) is not True:
        raise DigestSigningContractError("signature not valid for the pinned subject")
    return receipt
