"""Immutable execution identity, not an authorization or a migration policy."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

AFFINITY_STATE_KEY = "incident_execution_affinity"
AFFINITY_SCHEMA_VERSION = "execution-affinity-v1"
STATE_CONTRACT_VERSION = "incident-state-v1"
CHECKPOINT_FORMAT_VERSION = "1.0"


def require_digest(value: object, name: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} requires an exact lowercase SHA256.")
    return value


def require_identifier(value: object, name: str) -> str:
    if (type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)
            or value.casefold() in {"latest", "default"}):
        raise ValueError(f"{name} requires an explicit bounded identifier.")
    return value


def canonical_digest(document: object) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True, kw_only=True)
class ProductReleaseIdentity:
    """Content observed by the release verifier; not an OCI digest or attestation."""

    release_id: str
    source_sha256: str
    environment_sha256: str

    def __post_init__(self) -> None:
        require_identifier(self.release_id, "release_id")
        require_digest(self.source_sha256, "source_sha256")
        require_digest(self.environment_sha256, "environment_sha256")

    def to_document(self) -> dict[str, str]:
        return {"release_id": self.release_id, "source_sha256": self.source_sha256,
                "environment_sha256": self.environment_sha256}


@dataclass(frozen=True, kw_only=True)
class ExecutionAffinity:
    installation_id: str
    release: ProductReleaseIdentity
    foundry_sha256: str
    procedures_sha256: str
    schema_version: str = AFFINITY_SCHEMA_VERSION
    state_contract_version: str = STATE_CONTRACT_VERSION
    checkpoint_format_version: str = CHECKPOINT_FORMAT_VERSION

    def __post_init__(self) -> None:
        require_identifier(self.installation_id, "installation_id")
        if type(self.release) is not ProductReleaseIdentity:
            raise TypeError("An explicit ProductReleaseIdentity is required.")
        require_digest(self.foundry_sha256, "foundry_sha256")
        require_digest(self.procedures_sha256, "procedures_sha256")
        if (self.schema_version != AFFINITY_SCHEMA_VERSION
                or self.state_contract_version != STATE_CONTRACT_VERSION
                or self.checkpoint_format_version != CHECKPOINT_FORMAT_VERSION):
            raise ValueError("Unsupported execution affinity contract.")

    def to_document(self) -> dict:
        return {"schema_version": self.schema_version, "installation_id": self.installation_id,
                "release": self.release.to_document(), "foundry_sha256": self.foundry_sha256,
                "procedures_sha256": self.procedures_sha256,
                "state_contract_version": self.state_contract_version,
                "checkpoint_format_version": self.checkpoint_format_version}

    @property
    def fingerprint(self) -> str:
        return canonical_digest(self.to_document())

    @classmethod
    def from_document(cls, document: object) -> ExecutionAffinity:
        fields = {"schema_version", "installation_id", "release", "foundry_sha256", "procedures_sha256",
                  "state_contract_version", "checkpoint_format_version"}
        if type(document) is not dict or set(document) != fields:
            raise ValueError("Invalid execution affinity document.")
        release = document["release"]
        if type(release) is not dict or set(release) != {"release_id", "source_sha256", "environment_sha256"}:
            raise ValueError("Invalid product release document.")
        return cls(**{**document, "release": ProductReleaseIdentity(**release)})
