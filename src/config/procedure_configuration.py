"""Load and retain the exact hash-pinned procedure configuration snapshot."""
from dataclasses import dataclass, field
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re

from src.runtime.execution_affinity import canonical_digest, require_digest
from src.workflows.incident_resolution.capability_registry import build_default_capability_registry
from src.workflows.incident_resolution.procedure_catalog import parse_procedure_catalog
from src.workflows.incident_resolution.procedure_governance import parse_procedure_governance, ProcedureGovernanceApprovalPolicy
from src.workflows.incident_resolution.procedure_admission import ProcedureAdmissionPolicy, parse_procedure_compatibility, DEFAULT_PROCEDURE_COMPATIBILITY_PATH
from src.workflows.incident_resolution.governed_procedure_admission import GovernedProcedureAdmissionPolicy
from src.workflows.incident_resolution.procedure_capability_registry import parse_procedure_capability_bindings

PATH_KEY = "PROCEDURE_CONFIGURATION_MANIFEST"
HASH_KEY = "PROCEDURE_CONFIGURATION_SHA256"
_KINDS = frozenset({"catalog", "governance", "bindings", "compatibility"})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate procedure configuration JSON member.")
        result[key] = value
    return result


def _decode(raw: bytes):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Invalid procedure configuration JSON.") from exc


def _read_snapshot(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Procedure configuration requires regular files without symlinks.")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Procedure configuration exceeds its size limit.")
    return raw


def _compose_snapshot(documents):
    payloads = {kind: _decode(raw) for kind, raw in documents}
    catalog = parse_procedure_catalog(payloads["catalog"])
    governance = parse_procedure_governance(payloads["governance"], catalog=catalog)
    capabilities = parse_procedure_capability_bindings(
        payloads["bindings"], catalog=catalog, capability_registry=build_default_capability_registry(),
    )
    admission = ProcedureAdmissionPolicy(
        catalog=catalog, legacy_compatibility=parse_procedure_compatibility(payloads["compatibility"]),
    )
    return (GovernedProcedureAdmissionPolicy(admission_policy=admission,
                governance_policy=ProcedureGovernanceApprovalPolicy(registry=governance)), capabilities)


@dataclass(frozen=True)
class ProcedureConfiguration:
    admission: GovernedProcedureAdmissionPolicy
    capabilities: object
    manifest_sha256: str | None = field(default=None, kw_only=True)
    _documents: tuple[tuple[str, bytes], ...] | None = field(default=None, repr=False, kw_only=True)

    def __post_init__(self):
        if (self.manifest_sha256 is None) != (self._documents is None):
            raise ValueError("Procedure digest and snapshot must be supplied together.")
        if self._documents is not None:
            require_digest(self.manifest_sha256, "procedure manifest")
            if (type(self._documents) is not tuple or len(self._documents) != 4
                    or any(type(item) is not tuple or len(item) != 2 or type(item[0]) is not str
                           or type(item[1]) is not bytes or not item[1] or len(item[1]) > 1048576
                           for item in self._documents)
                    or {item[0] for item in self._documents} != _KINDS):
                raise ValueError("An immutable complete procedure snapshot is required.")

    @property
    def fingerprint(self) -> str | None:
        if self._documents is None:
            return None
        return canonical_digest({"schema_version": "procedure-snapshot-v1", "documents": {
            kind: hashlib.sha256(raw).hexdigest() for kind, raw in self._documents
        }})

    def workflow_options(self):
        """Historical composition retains the injected instances and call shape."""
        return {"governed_procedure_admission_policy": self.admission,
                "procedure_capability_registry": self.capabilities}

    def verified_workflow_options(self):
        """Affinity composition rebuilds from verified bytes, never mutated registries."""
        if self._documents is None:
            raise ValueError("A verified procedure snapshot is required for affinity.")
        admission, capabilities = _compose_snapshot(self._documents)
        return {"governed_procedure_admission_policy": admission,
                "procedure_capability_registry": capabilities}


def build_procedure_configuration(environment):
    if not isinstance(environment, Mapping):
        raise TypeError("environment must implement Mapping.")
    if PATH_KEY not in environment and HASH_KEY not in environment:
        return None
    path, digest = environment.get(PATH_KEY), environment.get(HASH_KEY)
    if type(path) is not str or not path or path != path.strip():
        raise ValueError("Procedure configuration requires an explicit path and SHA256.")
    require_digest(digest, "procedure manifest")
    manifest = Path(path)
    raw = _read_snapshot(manifest, 65536)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Procedure manifest digest mismatch.")
    payload = _decode(raw)
    if (type(payload) is not dict or set(payload) != {"schema_version", "files"}
            or payload["schema_version"] != "1.0" or type(payload["files"]) is not dict
            or set(payload["files"]) != {"catalog", "governance", "bindings"}):
        raise ValueError("Procedure manifest schema mismatch.")
    documents = {}
    for kind, item in payload["files"].items():
        if (type(item) is not dict or set(item) != {"name", "sha256"}
                or type(item["name"]) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+\.json", item["name"])):
            raise ValueError("Invalid procedure configuration file reference.")
        require_digest(item["sha256"], "procedure file")
        data = _read_snapshot(manifest.parent / item["name"], 1048576)
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Procedure configuration file digest mismatch.")
        documents[kind] = data
    documents["compatibility"] = _read_snapshot(DEFAULT_PROCEDURE_COMPATIBILITY_PATH, 1048576)
    snapshot = tuple(sorted(documents.items()))
    admission, capabilities = _compose_snapshot(snapshot)
    return ProcedureConfiguration(admission, capabilities, manifest_sha256=digest, _documents=snapshot)
