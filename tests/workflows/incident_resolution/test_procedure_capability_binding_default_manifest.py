from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import src.workflows.incident_resolution.procedure_capability_registry as registry_module

from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)

from src.workflows.incident_resolution.procedure_catalog import (
    build_default_procedure_catalog,
)


MISSING = (
    "F25_DEFAULT_PROCEDURE_CAPABILITY_BINDING_MANIFEST_NOT_IMPLEMENTED"
)


EXPECTED_BINDINGS = (
    {
        "procedure_id": "NTTSY-SBX-AZ-VM-001",
        "procedure_version": "1.0",
        "step_id": "1",
        "capability_id": "azure.vm.start",
        "applicability": {
            "allowed_environments": [
                "sandbox",
            ],
            "allowed_incident_origins": [
                "observed",
            ],
        },
    },
    {
        "procedure_id": "NTTSY-SBX-AZ-VM-002",
        "procedure_version": "1.0",
        "step_id": "1",
        "capability_id": "azure.vm.start",
        "applicability": {
            "allowed_environments": [
                "sandbox",
            ],
            "allowed_incident_origins": [
                "observed",
            ],
        },
    },
    {
        "procedure_id": "NTTSY-SBX-AZ-VM-DEMO-001",
        "procedure_version": "1.0",
        "step_id": "1",
        "capability_id": "azure.vm.start",
        "applicability": {
            "allowed_environments": [
                "sandbox",
            ],
            "allowed_incident_origins": [
                "synthetic_demo",
            ],
        },
    },
)


def _api():
    required = (
        "DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH",
        "load_procedure_capability_bindings",
        "build_default_procedure_capability_registry",
    )

    missing = tuple(
        name
        for name in required
        if not hasattr(
            registry_module,
            name,
        )
    )

    if missing:
        pytest.fail(
            MISSING,
            pytrace=False,
        )

    return (
        registry_module
        .DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH,
        registry_module
        .load_procedure_capability_bindings,
        registry_module
        .build_default_procedure_capability_registry,
    )


def _payload():
    path, _, _ = _api()

    return json.loads(
        Path(
            path
        ).read_text(
            encoding="utf-8"
        )
    )


def test_default_binding_manifest_surface_is_missing_red():
    path, loader, builder = _api()

    assert callable(loader)
    assert callable(builder)

    assert (
        Path(path).name
        == "procedure_capability_bindings.v1.json"
    )


def test_default_binding_manifest_is_source_packaged_json():
    path, _, _ = _api()

    path = Path(
        path
    )

    assert path.is_file()
    assert path.suffix == ".json"

    assert (
        path.parent
        == Path(
            registry_module.__file__
        ).resolve().parent
    )


def test_default_binding_manifest_contains_exact_three_bindings():
    payload = _payload()

    assert set(
        payload
    ) == {
        "schema_version",
        "bindings",
    }

    assert (
        payload[
            "schema_version"
        ]
        == "1.0"
    )

    assert (
        payload[
            "bindings"
        ]
        == list(
            EXPECTED_BINDINGS
        )
    )


def test_default_builder_uses_manifest_loader_not_python_binding_constructors():
    _, _, builder = _api()

    source = inspect.getsource(
        builder
    )

    assert (
        "load_procedure_capability_bindings"
        in source
    )

    assert (
        "DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH"
        in source
    )

    assert (
        "build_default_procedure_catalog"
        in source
    )

    assert (
        "build_default_capability_registry"
        in source
    )

    assert (
        "ProcedureCapabilityBinding("
        not in source
    )

    assert (
        "ProcedureApplicability("
        not in source
    )


def test_default_builder_returns_exact_manifest_bindings():
    _, _, builder = _api()

    registry = builder()

    assert registry.count() == 3

    for expected in EXPECTED_BINDINGS:
        binding = registry.get_binding(
            procedure_id=expected[
                "procedure_id"
            ],
            procedure_version=expected[
                "procedure_version"
            ],
            step_id=expected[
                "step_id"
            ],
        )

        assert (
            binding.capability_id
            == expected[
                "capability_id"
            ]
        )

        assert (
            binding.applicability
            .allowed_environments
            == tuple(
                expected[
                    "applicability"
                ][
                    "allowed_environments"
                ]
            )
        )

        assert (
            binding.applicability
            .allowed_incident_origins
            == tuple(
                expected[
                    "applicability"
                ][
                    "allowed_incident_origins"
                ]
            )
        )


def test_default_manifest_is_exactly_aligned_with_default_catalog_steps():
    _, _, builder = _api()

    catalog = (
        build_default_procedure_catalog()
    )

    registry = builder()

    payload = _payload()

    expected_keys = {
        (
            item[
                "procedure_id"
            ],
            item[
                "procedure_version"
            ],
            item[
                "step_id"
            ],
        )
        for item in payload[
            "bindings"
        ]
    }

    catalog_keys = set()

    for item in json.loads(
        Path(
            registry_module
            .DEFAULT_PROCEDURE_CAPABILITY_BINDINGS_PATH
        ).with_name(
            "procedure_catalog.v1.json"
        ).read_text(
            encoding="utf-8"
        )
    )[
        "procedures"
    ]:
        for step_id in item[
            "step_ids"
        ]:
            key = (
                item[
                    "procedure_id"
                ],
                item[
                    "procedure_version"
                ],
                step_id,
            )

            catalog_keys.add(
                key
            )

            assert registry.contains_binding(
                procedure_id=key[0],
                procedure_version=key[1],
                step_id=key[2],
            )

            assert catalog.contains_step(
                key[0],
                key[1],
                key[2],
            )

    assert expected_keys == catalog_keys


def test_default_manifest_preserves_capability_reuse():
    _, _, builder = _api()

    registry = builder()

    resolved = [
        registry.resolve_capability(
            procedure_id=item[
                "procedure_id"
            ],
            procedure_version=item[
                "procedure_version"
            ],
            step_id=item[
                "step_id"
            ],
        )
        for item in EXPECTED_BINDINGS
    ]

    assert {
        item.capability_id
        for item in resolved
    } == {
        "azure.vm.start"
    }

    assert (
        resolved[0]
        is resolved[1]
        is resolved[2]
    )


def test_default_manifest_can_be_loaded_with_explicit_authorities():
    path, loader, _ = _api()

    registry = loader(
        path,
        catalog=(
            build_default_procedure_catalog()
        ),
        capability_registry=(
            build_default_capability_registry()
        ),
    )

    assert registry.count() == 3


def test_default_binding_configuration_removes_default_python_binding_authority():
    _, _, builder = _api()

    source = inspect.getsource(
        builder
    )

    assert (
        "ProcedureCapabilityBinding("
        not in source
    )

    assert (
        "ProcedureApplicability("
        not in source
    )