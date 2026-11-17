import hashlib
import json
import shutil

import pytest

from src.config import procedure_configuration as module
from tests.config.test_f27_integrated_publication import bundle


def test_verified_snapshot_survives_source_changes_and_registry_mutation(tmp_path):
    env = bundle(tmp_path, approved=True)
    cfg = module.build_procedure_configuration(env)
    fingerprint = cfg.fingerprint
    cfg.capabilities._bindings.clear()
    (tmp_path / "catalog.json").write_text("{}")
    rebuilt = cfg.verified_workflow_options()
    assert rebuilt["procedure_capability_registry"].get_binding(
        procedure_id="AI-SUPPORT-SBX-AZ-RG-LIST-001", procedure_version="1.0", step_id="1",
    ).capability_id == "azure.resource_group.list"
    assert cfg.fingerprint == fingerprint
    with pytest.raises(ValueError, match="digest"):
        module.build_procedure_configuration(env)


def test_snapshot_fingerprint_is_independent_of_absolute_paths(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    env_a = bundle(a)
    shutil.copytree(a, b)
    env_b = {**env_a, module.PATH_KEY: str(b / "manifest.json")}
    assert module.build_procedure_configuration(env_a).fingerprint == module.build_procedure_configuration(env_b).fingerprint


def test_compatibility_bytes_are_part_of_snapshot_even_when_manifest_unchanged(tmp_path, monkeypatch):
    env = bundle(tmp_path)
    original = module.build_procedure_configuration(env)
    changed = tmp_path / "compatibility.json"
    changed.write_text('{"schema_version":"1.0","procedures":[]}')
    monkeypatch.setattr(module, "DEFAULT_PROCEDURE_COMPATIBILITY_PATH", changed)
    updated = module.build_procedure_configuration(env)
    assert updated.manifest_sha256 == original.manifest_sha256
    assert updated.fingerprint != original.fingerprint


def test_loader_parses_verified_bytes_instead_of_reopening_changed_file(tmp_path, monkeypatch):
    env = bundle(tmp_path)
    parse = module.parse_procedure_catalog
    def change_file_then_parse(payload):
        (tmp_path / "catalog.json").write_text("{}")
        return parse(payload)
    monkeypatch.setattr(module, "parse_procedure_catalog", change_file_then_parse)
    cfg = module.build_procedure_configuration(env)
    assert cfg.capabilities.get_binding(procedure_id="NTTSY-SBX-AZ-VM-001", procedure_version="1.0",
                                       step_id="1").capability_id == "azure.vm.start"
    assert cfg.fingerprint is not None


@pytest.mark.parametrize("kind", ["manifest", "catalog", "governance", "bindings"])
def test_duplicate_members_are_rejected_even_with_matching_hashes(tmp_path, kind):
    env = bundle(tmp_path)
    target = tmp_path / f"{kind}.json"
    raw = target.read_text()
    raw = raw.replace('"schema_version": "1.0"', '"schema_version":"1.0","schema_version":"1.0"', 1)
    target.write_text(raw)
    manifest_path = tmp_path / "manifest.json"
    if kind != "manifest":
        document = json.loads(manifest_path.read_text())
        document["files"][kind]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(document))
    env[module.HASH_KEY] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="JSON"):
        module.build_procedure_configuration(env)


def test_unverified_injected_configuration_cannot_be_used_as_verified_snapshot(tmp_path):
    original = module.build_procedure_configuration(bundle(tmp_path))
    manual = module.ProcedureConfiguration(original.admission, original.capabilities)
    assert manual.fingerprint is None
    with pytest.raises(ValueError, match="verified"):
        manual.verified_workflow_options()
