from __future__ import annotations

import inspect
import json

import pytest

import src.workflows.incident_resolution.procedure_capability_registry as registry_module

from src.workflows.incident_resolution.capability_registry import (
    CapabilityNotFoundError,
    build_default_capability_registry,
)

from src.workflows.incident_resolution.procedure_capability_binding import (
    ProcedureCapabilityBindingError,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    DuplicateProcedureCapabilityBindingError,
    ProcedureCapabilityRegistry,
    ProcedureCapabilityRegistryError,
)

from src.workflows.incident_resolution.procedure_catalog import (
    ProcedureCatalog,
    ProcedureDefinition,
)


MISSING = (
    "F25_PROCEDURE_CAPABILITY_BINDING_MANIFEST_LOADER_NOT_IMPLEMENTED"
)


def _api():
    required = (
        "PROCEDURE_CAPABILITY_BINDINGS_SCHEMA_VERSION",
        "load_procedure_capability_bindings",
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
        .PROCEDURE_CAPABILITY_BINDINGS_SCHEMA_VERSION,
        registry_module
        .load_procedure_capability_bindings,
    )


def _catalog(
    *,
    lifecycle="published",
):
    return ProcedureCatalog(
        definitions=(
            ProcedureDefinition(
                procedure_id="PROC-A",
                procedure_version="1.0",
                procedure_name="Procedure A",
                lifecycle=lifecycle,
                step_ids=(
                    "1",
                    "2",
                ),
            ),
            ProcedureDefinition(
                procedure_id="PROC-B",
                procedure_version="1.0",
                procedure_name="Procedure B",
                lifecycle="published",
                step_ids=(
                    "1",
                ),
            ),
        )
    )


def _valid_payload():
    return {
        "schema_version": "1.0",
        "bindings": [
            {
                "procedure_id": "PROC-A",
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
                "procedure_id": "PROC-B",
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
        ],
    }


def _write_json(
    tmp_path,
    payload,
):
    path = (
        tmp_path
        / "procedure-capability-bindings.json"
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def _load(
    tmp_path,
    payload,
    *,
    catalog=None,
):
    _, loader = _api()

    return loader(
        _write_json(
            tmp_path,
            payload,
        ),
        catalog=(
            catalog
            if catalog is not None
            else _catalog()
        ),
        capability_registry=(
            build_default_capability_registry()
        ),
    )


def test_binding_manifest_loader_surface_is_missing_red():
    schema_version, loader = _api()

    assert schema_version == "1.0"
    assert callable(loader)


def test_loader_contract_requires_explicit_authorities():
    _, loader = _api()

    signature = inspect.signature(
        loader
    )

    assert tuple(
        signature.parameters
    ) == (
        "path",
        "catalog",
        "capability_registry",
    )

    assert (
        signature.parameters[
            "path"
        ].default
        is inspect.Parameter.empty
    )

    for name in (
        "catalog",
        "capability_registry",
    ):
        parameter = signature.parameters[
            name
        ]

        assert (
            parameter.kind
            is inspect.Parameter.KEYWORD_ONLY
        )

        assert (
            parameter.default
            is inspect.Parameter.empty
        )


def test_loader_builds_exact_registry_from_configuration(
    tmp_path,
):
    registry = _load(
        tmp_path,
        _valid_payload(),
    )

    assert isinstance(
        registry,
        ProcedureCapabilityRegistry,
    )

    assert registry.count() == 2

    first = registry.get_binding(
        procedure_id="PROC-A",
        procedure_version="1.0",
        step_id="1",
    )

    second = registry.get_binding(
        procedure_id="PROC-B",
        procedure_version="1.0",
        step_id="1",
    )

    assert (
        first.capability_id
        == "azure.vm.start"
    )

    assert (
        first.applicability
        .allowed_environments
        == (
            "sandbox",
        )
    )

    assert (
        first.applicability
        .allowed_incident_origins
        == (
            "observed",
        )
    )

    assert (
        second.applicability
        .allowed_incident_origins
        == (
            "synthetic_demo",
        )
    )

    first_capability = (
        registry.resolve_capability(
            procedure_id="PROC-A",
            procedure_version="1.0",
            step_id="1",
        )
    )

    second_capability = (
        registry.resolve_capability(
            procedure_id="PROC-B",
            procedure_version="1.0",
            step_id="1",
        )
    )

    assert first_capability is second_capability


@pytest.mark.parametrize(
    "payload",
    (
        {
            "bindings": [],
        },
        {
            "schema_version": "1.0",
        },
        {
            "schema_version": "1.0",
            "bindings": [],
            "extra": True,
        },
    ),
)
def test_loader_requires_exact_root_members(
    tmp_path,
    payload,
):
    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_rejects_unsupported_schema_version(
    tmp_path,
):
    payload = _valid_payload()
    payload[
        "schema_version"
    ] = "2.0"

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_requires_bindings_json_array(
    tmp_path,
):
    payload = _valid_payload()
    payload["bindings"] = {}

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "extra",
    ),
)
def test_loader_requires_exact_binding_members(
    tmp_path,
    mutation,
):
    payload = _valid_payload()

    item = payload[
        "bindings"
    ][0]

    if mutation == "missing":
        item.pop(
            "capability_id"
        )
    else:
        item["extra"] = True

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "extra",
    ),
)
def test_loader_requires_exact_applicability_members(
    tmp_path,
    mutation,
):
    payload = _valid_payload()

    applicability = payload[
        "bindings"
    ][0][
        "applicability"
    ]

    if mutation == "missing":
        applicability.pop(
            "allowed_environments"
        )
    else:
        applicability["extra"] = True

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


@pytest.mark.parametrize(
    "field",
    (
        "allowed_environments",
        "allowed_incident_origins",
    ),
)
def test_loader_requires_applicability_arrays(
    tmp_path,
    field,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ][0][
        "applicability"
    ][field] = "sandbox"

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_delegates_exact_binding_validation(
    tmp_path,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ][0][
        "procedure_id"
    ] = " PROC-A"

    with pytest.raises(
        ProcedureCapabilityBindingError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_rejects_unknown_capability(
    tmp_path,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ][0][
        "capability_id"
    ] = "azure.vm.restart"

    with pytest.raises(
        CapabilityNotFoundError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_rejects_unknown_catalog_identity(
    tmp_path,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ][0][
        "procedure_id"
    ] = "PROC-UNKNOWN"

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_rejects_unknown_catalog_step(
    tmp_path,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ][0][
        "step_id"
    ] = "99"

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_binding_configuration_does_not_require_published_lifecycle(
    tmp_path,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ] = [
        payload[
            "bindings"
        ][0]
    ]

    registry = _load(
        tmp_path,
        payload,
        catalog=(
            _catalog(
                lifecycle="draft",
            )
        ),
    )

    assert registry.contains_binding(
        procedure_id="PROC-A",
        procedure_version="1.0",
        step_id="1",
    )


def test_loader_rejects_duplicate_exact_binding(
    tmp_path,
):
    payload = _valid_payload()

    payload[
        "bindings"
    ].append(
        dict(
            payload[
                "bindings"
            ][0]
        )
    )

    with pytest.raises(
        DuplicateProcedureCapabilityBindingError
    ):
        _load(
            tmp_path,
            payload,
        )


def test_loader_rejects_duplicate_json_members(
    tmp_path,
):
    _, loader = _api()

    path = (
        tmp_path
        / "duplicate.json"
    )

    path.write_text(
        (
            "{"
            '"schema_version":"1.0",'
            '"schema_version":"1.0",'
            '"bindings":[]'
            "}"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        loader(
            path,
            catalog=_catalog(),
            capability_registry=(
                build_default_capability_registry()
            ),
        )


def test_loader_fails_closed_for_malformed_unicode_and_io(
    tmp_path,
):
    _, loader = _api()

    malformed = (
        tmp_path
        / "malformed.json"
    )

    malformed.write_text(
        "{",
        encoding="utf-8",
    )

    invalid_unicode = (
        tmp_path
        / "invalid-utf8.json"
    )

    invalid_unicode.write_bytes(
        b"\xff\xfe\x00"
    )

    missing = (
        tmp_path
        / "missing.json"
    )

    for path in (
        malformed,
        invalid_unicode,
        missing,
    ):
        with pytest.raises(
            ProcedureCapabilityRegistryError
        ):
            loader(
                path,
                catalog=_catalog(),
                capability_registry=(
                    build_default_capability_registry()
                ),
            )


def test_loader_rejects_invalid_dependencies(
    tmp_path,
):
    _, loader = _api()

    path = _write_json(
        tmp_path,
        _valid_payload(),
    )

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        loader(
            path,
            catalog=None,
            capability_registry=(
                build_default_capability_registry()
            ),
        )

    with pytest.raises(
        ProcedureCapabilityRegistryError
    ):
        loader(
            path,
            catalog=_catalog(),
            capability_registry=None,
        )


def test_loader_preserves_capability_authority_separation():
    source = inspect.getsource(
        registry_module
    )

    assert (
        "procedure_governance"
        not in source
    )

    assert (
        "governed_procedure_admission"
        not in source
    )

    assert (
        "agent_framework"
        not in source
    )