import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import release_identity as module
from src.config.procedure_configuration import build_procedure_configuration
from src.config.foundry_deployment import build_foundry_deployment_configuration
from tests.config.test_f27_integrated_publication import bundle
from tests.config.test_foundry_deployment import deployment_document, environment
from tests.test_production_capability_foundry_agent_wiring import rig


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    root = tmp_path / "package"
    (root / "src").mkdir(parents=True)
    (root / "src/app.py").write_bytes(b"VALUE = 1\n")
    (root / "src/settings.json").write_bytes(b'{"schema_version":"1.0"}')
    (root / "requirements-runtime.txt").write_bytes(b"synthetic-runtime==1.0\n")
    dist = SimpleNamespace(metadata={"Name": "synthetic-runtime"}, version="1.0")
    monkeypatch.setattr(module.metadata, "distributions", lambda: [dist])
    procedure_dir = tmp_path / "procedures"
    procedure_dir.mkdir()
    procedures = build_procedure_configuration(bundle(procedure_dir))
    deployment = build_foundry_deployment_configuration(environment(deployment_document()))
    manifest = tmp_path / "release.json"
    document = {"schema_version": module.RELEASE_SCHEMA_VERSION, "release_id": "release-17",
                "source_sha256": module.observe_source_digest(root),
                "environment_sha256": module.observe_environment_digest()}
    def write(document):
        manifest.write_text(json.dumps(document), encoding="utf-8")
        return {module.MANIFEST_KEY: str(manifest), module.HASH_KEY: hashlib.sha256(manifest.read_bytes()).hexdigest(),
                module.INSTALLATION_KEY: "installation-a"}
    values = write(document)
    def build(values=values, **kwargs):
        return module.build_execution_affinity(values, deployment=deployment, procedures=procedures,
                                               package_root=root, **kwargs)
    return SimpleNamespace(root=root, deployment=deployment, procedures=procedures, document=document,
                           manifest=manifest, values=values, dist=dist, build=build, write=write)


def test_same_release_is_reusable_but_installations_have_distinct_affinity(candidate, monkeypatch):
    monkeypatch.setenv(module.INSTALLATION_KEY, "ignored-process-value")
    a = candidate.build()
    b = candidate.build({**candidate.values, module.INSTALLATION_KEY: "installation-b"})
    assert a.release == b.release and a.fingerprint != b.fingerprint
    assert a.procedures_sha256 == candidate.procedures.fingerprint
    assert a.foundry_sha256 == candidate.deployment.fingerprint


@pytest.mark.parametrize("change", ["code", "json", "requirements", "dependency", "new-file", "removed-file"])
def test_changed_runtime_is_rejected_against_pinned_manifest(candidate, change):
    if change == "code": (candidate.root / "src/app.py").write_bytes(b"VALUE = 2\n")
    elif change == "json": (candidate.root / "src/settings.json").write_bytes(b"{}")
    elif change == "requirements": (candidate.root / "requirements-runtime.txt").write_bytes(b"different==1.0\n")
    elif change == "dependency": candidate.dist.version = "2.0"
    elif change == "new-file": (candidate.root / "src/new.py").write_bytes(b"VALUE = 3\n")
    else: (candidate.root / "src/app.py").unlink()
    with pytest.raises(ValueError, match="differs"):
        candidate.build()


@pytest.mark.parametrize("key", sorted(module.RELEASE_KEYS))
def test_partial_release_configuration_is_not_ignored(candidate, key):
    values = dict(candidate.values)
    del values[key]
    with pytest.raises(ValueError, match="all three"):
        candidate.build(values)


@pytest.mark.parametrize("change", ["schema", "extra", "missing", "latest", "uppercase", "bad-root"])
def test_manifest_rejects_unsupported_identity(candidate, change):
    doc = dict(candidate.document)
    if change == "schema": doc["schema_version"] = "product-release-v2"
    elif change == "extra": doc["allow_migration"] = True
    elif change == "missing": del doc["source_sha256"]
    elif change == "latest": doc["release_id"] = "latest"
    elif change == "uppercase": doc["source_sha256"] = "A" * 64
    else: doc = []
    with pytest.raises(ValueError):
        candidate.build(candidate.write(doc))


def test_changed_manifest_is_rejected_before_observing_runtime(candidate, monkeypatch):
    candidate.manifest.write_bytes(b"{}")
    def forbidden(*args): raise AssertionError("Must check manifest digest before source inventory")
    monkeypatch.setattr(module, "observe_source_digest", forbidden)
    with pytest.raises(ValueError, match="digest mismatch"):
        candidate.build()


def test_duplicate_manifest_members_rejected_with_matching_hash(candidate):
    candidate.manifest.write_text('{"schema_version":"product-release-v1","schema_version":"product-release-v1"}')
    values = {**candidate.values, module.HASH_KEY: hashlib.sha256(candidate.manifest.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match="JSON"):
        candidate.build(values)


def test_ambiguous_distribution_inventory_is_rejected(candidate, monkeypatch):
    monkeypatch.setattr(module.metadata, "distributions", lambda: [candidate.dist, candidate.dist])
    with pytest.raises(ValueError, match="ambiguous"):
        candidate.build()


@pytest.mark.parametrize("change", ["unsupported-file", "symlink", "source-over-limit"])
def test_source_inventory_fails_closed(candidate, monkeypatch, change):
    if change == "unsupported-file": (candidate.root / "src/extension.so").write_bytes(b"unknown")
    elif change == "source-over-limit": monkeypatch.setattr(module, "MAX_SOURCE_BYTES", 1)
    else:
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == "app.py" or original(p))
    with pytest.raises(ValueError):
        candidate.build()


def test_cache_and_file_creation_order_do_not_change_source_identity(candidate):
    old = module.observe_source_digest(candidate.root)
    cache = candidate.root / "src/__pycache__"
    cache.mkdir()
    (cache / "app.cpython-314.pyc").write_bytes(b"synthetic-cache")
    path = candidate.root / "src/app.py"
    raw = path.read_bytes()
    path.unlink()
    path.write_bytes(raw)
    assert module.observe_source_digest(candidate.root) == old


@pytest.mark.parametrize("dependency", ["deployment", "procedures"])
def test_unverified_or_missing_configuration_cannot_claim_affinity(candidate, dependency):
    args = {"deployment": candidate.deployment, "procedures": candidate.procedures}
    args[dependency] = None
    with pytest.raises(ValueError):
        module.build_execution_affinity(candidate.values, package_root=candidate.root, **args)


def test_absence_preserves_legacy_without_touching_files_or_inventory(monkeypatch):
    def forbidden(*args): raise AssertionError("Legacy composition must not inspect a release")
    monkeypatch.setattr(module, "observe_source_digest", forbidden)
    assert module.build_execution_affinity({}, deployment=None, procedures=None) is None


@pytest.mark.parametrize("key", sorted(module.RELEASE_KEYS))
def test_production_refuses_partial_feature_activation_before_creating_providers(rig, key):
    rig.environment[key] = "synthetic-request"
    with pytest.raises(ValueError, match="pending durable admission and queue"):
        rig.invoke("application")
    assert rig.effects == []
