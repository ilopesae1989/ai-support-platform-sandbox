from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from src.workflows.incident_resolution.procedure_capability_registry import (
    build_default_procedure_capability_registry,
)


TARGET = "src.workflows.incident_resolution.procedure_catalog"
MISSING = "F25_DEFAULT_PROCEDURE_CATALOG_NOT_IMPLEMENTED"
EXPECTED_SCHEMA_VERSION = "1.0"

EXPECTED = (
    (
        "NTTSY-SBX-AZ-VM-001",
        "1.0",
        "Arranque de máquina virtual Azure en estado Stopped (Allocated)",
        ("1",),
    ),
    (
        "NTTSY-SBX-AZ-VM-002",
        "1.0",
        "Arranque de máquina virtual Azure en estado Deallocated",
        ("1",),
    ),
    (
        "NTTSY-SBX-AZ-VM-DEMO-001",
        "1.0",
        "Arranque de máquina virtual Azure (escenario demo synthetic_demo)",
        ("1",),
    ),
)


def _api():
    module = __import__(TARGET, fromlist=["*"])
    required = (
        "PROCEDURE_CATALOG_SCHEMA_VERSION",
        "DEFAULT_PROCEDURE_CATALOG_PATH",
        "load_procedure_catalog",
        "build_default_procedure_catalog",
    )
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        pytest.fail(MISSING + ":" + ",".join(missing), pytrace=False)
    return module


def _valid_payload():
    return {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "procedures": [
            {
                "procedure_id": procedure_id,
                "procedure_version": version,
                "procedure_name": name,
                "lifecycle": "published",
                "step_ids": list(step_ids),
            }
            for procedure_id, version, name, step_ids in EXPECTED
        ],
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def test_f25_2_surface_is_explicit_and_stable():
    module = _api()

    assert module.PROCEDURE_CATALOG_SCHEMA_VERSION == "1.0"

    assert tuple(
        inspect.signature(
            module.load_procedure_catalog
        ).parameters
    ) == ("path",)

    assert tuple(
        inspect.signature(
            module.build_default_procedure_catalog
        ).parameters
    ) == ()


def test_default_manifest_is_source_packaged_json():
    module = _api()

    path = Path(
        module.DEFAULT_PROCEDURE_CATALOG_PATH
    )

    assert path.name == "procedure_catalog.v1.json"
    assert path.suffix == ".json"
    assert path.is_file()

    normalized = path.resolve().as_posix()

    assert (
        "/src/workflows/incident_resolution/"
        in normalized
    )


def test_default_manifest_contains_exact_three_published_records():
    module = _api()

    path = Path(
        module.DEFAULT_PROCEDURE_CATALOG_PATH
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert set(payload) == {
        "schema_version",
        "procedures",
    }

    assert (
        payload["schema_version"]
        == EXPECTED_SCHEMA_VERSION
    )

    assert type(payload["procedures"]) is list
    assert len(payload["procedures"]) == 3

    observed = tuple(
        (
            item["procedure_id"],
            item["procedure_version"],
            item["procedure_name"],
            tuple(item["step_ids"]),
            item["lifecycle"],
        )
        for item in payload["procedures"]
    )

    expected = tuple(
        (
            procedure_id,
            version,
            name,
            step_ids,
            "published",
        )
        for (
            procedure_id,
            version,
            name,
            step_ids,
        ) in EXPECTED
    )

    assert observed == expected


def test_default_builder_returns_exact_published_catalog():
    module = _api()

    catalog = (
        module
        .build_default_procedure_catalog()
    )

    assert catalog.count() == 3

    for (
        procedure_id,
        version,
        name,
        step_ids,
    ) in EXPECTED:
        definition = (
            catalog.resolve_published(
                procedure_id=procedure_id,
                procedure_version=version,
                procedure_name=name,
            )
        )

        assert definition.step_ids == step_ids
        assert definition.lifecycle == "published"


def test_default_catalog_and_existing_bindings_are_exactly_aligned():
    module = _api()

    catalog = (
        module
        .build_default_procedure_catalog()
    )

    registry = (
        build_default_procedure_capability_registry()
    )

    assert catalog.count() == 3
    assert registry.count() == 3

    for (
        procedure_id,
        version,
        name,
        step_ids,
    ) in EXPECTED:
        definition = (
            catalog.resolve_published(
                procedure_id=procedure_id,
                procedure_version=version,
                procedure_name=name,
            )
        )

        for step_id in definition.step_ids:
            assert registry.contains_binding(
                procedure_id=procedure_id,
                procedure_version=version,
                step_id=step_id,
            )

            capability = (
                registry.resolve_capability(
                    procedure_id=procedure_id,
                    procedure_version=version,
                    step_id=step_id,
                )
            )

            assert (
                capability.capability_id
                == "azure.vm.start"
            )


def test_loader_accepts_valid_exact_manifest(tmp_path):
    module = _api()

    path = tmp_path / "catalog.json"

    _write_json(
        path,
        _valid_payload(),
    )

    catalog = (
        module
        .load_procedure_catalog(
            path
        )
    )

    assert catalog.count() == 3


def test_loader_rejects_unknown_root_members(tmp_path):
    module = _api()

    payload = _valid_payload()
    payload["unexpected"] = True

    path = tmp_path / "catalog.json"
    _write_json(path, payload)

    with pytest.raises(
        module.ProcedureCatalogError
    ):
        module.load_procedure_catalog(
            path
        )


def test_loader_rejects_unknown_procedure_members(tmp_path):
    module = _api()

    payload = _valid_payload()

    payload["procedures"][0][
        "capability_id"
    ] = "azure.vm.start"

    path = tmp_path / "catalog.json"
    _write_json(path, payload)

    with pytest.raises(
        module.ProcedureCatalogError
    ):
        module.load_procedure_catalog(
            path
        )


def test_loader_rejects_duplicate_json_members(tmp_path):
    module = _api()

    path = tmp_path / "catalog.json"

    path.write_text(
        (
            '{"schema_version":"1.0",'
            '"schema_version":"1.0",'
            '"procedures":[]}'
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        module.ProcedureCatalogError
    ):
        module.load_procedure_catalog(
            path
        )


def test_loader_rejects_unsupported_schema_version(tmp_path):
    module = _api()

    payload = _valid_payload()
    payload["schema_version"] = "2.0"

    path = tmp_path / "catalog.json"
    _write_json(path, payload)

    with pytest.raises(
        module.ProcedureCatalogError
    ):
        module.load_procedure_catalog(
            path
        )


def test_loader_rejects_malformed_json(tmp_path):
    module = _api()

    path = tmp_path / "catalog.json"

    path.write_text(
        '{"schema_version":',
        encoding="utf-8",
    )

    with pytest.raises(
        module.ProcedureCatalogError
    ):
        module.load_procedure_catalog(
            path
        )


def test_loader_rejects_non_array_procedures(tmp_path):
    module = _api()

    payload = _valid_payload()
    payload["procedures"] = {}

    path = tmp_path / "catalog.json"
    _write_json(path, payload)

    with pytest.raises(
        module.ProcedureCatalogError
    ):
        module.load_procedure_catalog(
            path
        )
