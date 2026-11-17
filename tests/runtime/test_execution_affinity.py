from dataclasses import FrozenInstanceError, replace
import json

import pytest

from src.runtime.execution_affinity import ExecutionAffinity, ProductReleaseIdentity


def affinity():
    return ExecutionAffinity(installation_id="customer-a", release=ProductReleaseIdentity(
        release_id="release-17", source_sha256="a" * 64, environment_sha256="b" * 64),
        foundry_sha256="c" * 64, procedures_sha256="d" * 64)


def test_affinity_roundtrip_and_returned_document_cannot_mutate_identity():
    original = affinity()
    document = original.to_document()
    assert ExecutionAffinity.from_document(json.loads(json.dumps(document))) == original
    document["release"]["source_sha256"] = "e" * 64
    assert original.release.source_sha256 == "a" * 64
    assert ExecutionAffinity.from_document(document).fingerprint != original.fingerprint
    with pytest.raises(FrozenInstanceError):
        original.installation_id = "other"


@pytest.mark.parametrize("field,value", [
    ("installation_id", "customer-b"), ("foundry_sha256", "e" * 64), ("procedures_sha256", "e" * 64),
])
def test_affinity_isolated_by_installation_and_configuration(field, value):
    original = affinity()
    changed = replace(original, **{field: value})
    assert changed.release == original.release and changed.fingerprint != original.fingerprint


@pytest.mark.parametrize("field,value", [
    ("release_id", "release-18"), ("source_sha256", "e" * 64), ("environment_sha256", "e" * 64),
])
def test_affinity_changes_with_release_content(field, value):
    original = affinity()
    assert replace(original, release=replace(original.release, **{field: value})).fingerprint != original.fingerprint


@pytest.mark.parametrize("change", ["extra", "missing", "schema", "checkpoint", "state", "release-extra",
                                     "uppercase-hash", "short-hash", "blank-installation", "latest", "bad-release"])
def test_unknown_or_ambiguous_persisted_identity_is_not_adopted(change):
    doc = affinity().to_document()
    if change == "extra": doc["authority"] = "approve"
    elif change == "missing": del doc["release"]
    elif change == "schema": doc["schema_version"] = "execution-affinity-v2"
    elif change == "checkpoint": doc["checkpoint_format_version"] = "2.0"
    elif change == "state": doc["state_contract_version"] = "unknown"
    elif change == "release-extra": doc["release"]["latest"] = True
    elif change == "uppercase-hash": doc["foundry_sha256"] = "A" * 64
    elif change == "short-hash": doc["procedures_sha256"] = "d" * 63
    elif change == "blank-installation": doc["installation_id"] = " customer-a"
    elif change == "latest": doc["release"]["release_id"] = "latest"
    else: doc["release"] = "release-17"
    with pytest.raises((TypeError, ValueError)):
        ExecutionAffinity.from_document(doc)
