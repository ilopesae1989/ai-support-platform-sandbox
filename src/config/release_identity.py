"""Verify release inputs locally before constructing a candidate affinity.

This does not deploy or activate version-aware queue selection. The production
host rejects these keys until the complete admission/queue contract is wired.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re

from src.config.foundry_deployment import FoundryDeploymentConfiguration
from src.config.procedure_configuration import ProcedureConfiguration
from src.runtime.execution_affinity import (
    ExecutionAffinity, ProductReleaseIdentity, canonical_digest, require_digest, require_identifier,
)

MANIFEST_KEY = "RUNTIME_RELEASE_MANIFEST"
HASH_KEY = "RUNTIME_RELEASE_SHA256"
INSTALLATION_KEY = "RUNTIME_INSTALLATION_ID"
RELEASE_KEYS = frozenset({MANIFEST_KEY, HASH_KEY, INSTALLATION_KEY})
RELEASE_SCHEMA_VERSION = "product-release-v1"
MAX_SOURCE_BYTES = 32 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member.")
        result[key] = value
    return result


def _read_bounded(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Release inputs must be regular files without symlinks.")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Release input exceeds its size limit.")
    return data


def observe_source_digest(package_root: Path) -> str:
    """Hash exact shipped src bytes and runtime requirements in stable path order.

    Cache directories are excluded. Other file types and symlinks fail closed.
    The immutable artifact/CI contract must prevent writes after this observation.
    """
    root = Path(package_root)
    source = root / "src"
    if root.is_symlink() or source.is_symlink() or not source.is_dir():
        raise ValueError("An explicit package root with src is required.")
    files = [root / "requirements-runtime.txt"]
    directories = [source]
    visited = 0
    while directories:
        directory = directories.pop()
        for item in sorted(directory.iterdir()):
            visited += 1
            if visited > 10_000:
                raise ValueError("Runtime source inventory exceeds its limit.")
            if item.is_symlink():
                raise ValueError("Runtime source symlinks are excluded.")
            if item.is_dir():
                if item.name != "__pycache__":
                    directories.append(item)
            elif item.is_file() and (item.suffix in {".py", ".json"}
                                    or item.name == ".gitkeep" and item.stat().st_size == 0):
                files.append(item)
            else:
                raise ValueError("Unsupported runtime source entry.")
    if len(files) == 1:
        raise ValueError("Runtime source inventory must not be empty.")
    observed = {}
    remaining = MAX_SOURCE_BYTES
    for path in sorted(files):
        data = _read_bounded(path, min(4 * 1024 * 1024, remaining))
        remaining -= len(data)
        observed[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    return canonical_digest({"schema_version": "runtime-source-v1", "files": observed})


def observe_environment_digest() -> str:
    """Bind interpreter, OS/architecture and all installed distribution versions.

    Includes development packages if present; production manifests must be built
    in the final runtime environment. This is not a wheel/native-library hash.
    """
    distributions = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if not name or not version:
            raise ValueError("Installed distribution has incomplete identity.")
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in distributions:
            raise ValueError("Installed distribution identity is ambiguous.")
        distributions[name] = version
    if not distributions:
        raise ValueError("Installed distribution inventory must not be empty.")
    return canonical_digest({"schema_version": "runtime-environment-v1",
                             "python": platform.python_version(),
                             "implementation": platform.python_implementation(),
                             "system": platform.system(), "machine": platform.machine(),
                             "distributions": distributions})


def build_execution_affinity(environment: Mapping, *, deployment: FoundryDeploymentConfiguration | None,
                             procedures: ProcedureConfiguration | None,
                             package_root: Path | None = None) -> ExecutionAffinity | None:
    if not isinstance(environment, Mapping):
        raise TypeError("environment must implement Mapping.")
    present = RELEASE_KEYS.intersection(environment)
    if not present:
        return None
    if present != RELEASE_KEYS:
        raise ValueError("Release configuration requires all three explicit keys.")
    installation = require_identifier(environment[INSTALLATION_KEY], "installation_id")
    expected = require_digest(environment[HASH_KEY], "release manifest hash")
    path = environment[MANIFEST_KEY]
    if type(path) is not str or not path or path != path.strip():
        raise ValueError("An exact release manifest path is required.")
    if type(deployment) is not FoundryDeploymentConfiguration:
        raise ValueError("Affinity requires the complete F46 Foundry configuration.")
    if type(procedures) is not ProcedureConfiguration or procedures.fingerprint is None:
        raise ValueError("Affinity requires a verified procedure snapshot.")
    raw = _read_bounded(Path(path), 65536)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Release manifest digest mismatch.")
    try:
        document = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Invalid release manifest JSON.") from exc
    if (type(document) is not dict
            or set(document) != {"schema_version", "release_id", "source_sha256", "environment_sha256"}
            or document["schema_version"] != RELEASE_SCHEMA_VERSION):
        raise ValueError("Unsupported release manifest schema.")
    release = ProductReleaseIdentity(**{k: v for k, v in document.items() if k != "schema_version"})
    root = Path(__file__).resolve().parents[2] if package_root is None else Path(package_root)
    if observe_source_digest(root) != release.source_sha256:
        raise ValueError("Runtime source digest differs from the release manifest.")
    if observe_environment_digest() != release.environment_sha256:
        raise ValueError("Installed runtime differs from the release manifest.")
    return ExecutionAffinity(installation_id=installation, release=release,
                             foundry_sha256=deployment.fingerprint, procedures_sha256=procedures.fingerprint)


def reject_incomplete_affinity_activation(environment: Mapping) -> None:
    if RELEASE_KEYS.intersection(environment):
        raise ValueError("Release affinity host activation requires the pending durable admission and queue contract.")
