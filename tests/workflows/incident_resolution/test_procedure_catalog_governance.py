from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
import importlib
import inspect
import textwrap

import pytest


TARGET = "src.workflows.incident_resolution.procedure_catalog"
MISSING = "F25_PROCEDURE_CATALOG_NOT_IMPLEMENTED"


def _api():
    try:
        return importlib.import_module(TARGET)
    except ModuleNotFoundError as exc:
        if exc.name != TARGET:
            raise
        pytest.fail(MISSING, pytrace=False)


def _definition(
    module,
    *,
    procedure_id="PROC-A",
    procedure_version="1.0",
    procedure_name="Procedure A",
    lifecycle="published",
    step_ids=("1", "2"),
):
    return module.ProcedureDefinition(
        procedure_id=procedure_id,
        procedure_version=procedure_version,
        procedure_name=procedure_name,
        lifecycle=lifecycle,
        step_ids=step_ids,
    )


def test_contract_surface_is_explicit():
    module = _api()

    for name in (
        "ProcedureCatalogError",
        "ProcedureNotFoundError",
        "DuplicateProcedureDefinitionError",
        "ProcedureNotPublishedError",
        "ProcedureIdentityMismatchError",
        "ProcedureDefinition",
        "ProcedureCatalog",
    ):
        assert hasattr(module, name)


def test_definition_has_only_governed_procedure_fields():
    module = _api()
    definition = _definition(module)

    assert tuple(field.name for field in fields(definition)) == (
        "procedure_id",
        "procedure_version",
        "procedure_name",
        "lifecycle",
        "step_ids",
    )

    assert not hasattr(definition, "capability_id")
    assert not hasattr(definition, "operation_action")


def test_definition_is_immutable():
    module = _api()
    definition = _definition(module)

    with pytest.raises(FrozenInstanceError):
        definition.procedure_name = "Changed"


def test_definition_requires_exact_nonblank_identity():
    module = _api()

    invalid = (
        {"procedure_id": ""},
        {"procedure_id": " PROC-A"},
        {"procedure_id": "PROC-A "},
        {"procedure_version": ""},
        {"procedure_version": " 1.0"},
        {"procedure_version": "1.0 "},
        {"procedure_name": ""},
        {"procedure_name": " Procedure A"},
        {"procedure_name": "Procedure A "},
    )

    for change in invalid:
        with pytest.raises(module.ProcedureCatalogError):
            _definition(module, **change)


def test_definition_requires_exact_supported_lifecycle():
    module = _api()

    for lifecycle in (
        "",
        " published",
        "published ",
        "active",
        "disabled",
        "PUBLISHED",
    ):
        with pytest.raises(module.ProcedureCatalogError):
            _definition(module, lifecycle=lifecycle)

    for lifecycle in (
        "draft",
        "published",
        "retired",
    ):
        assert _definition(module, lifecycle=lifecycle).lifecycle == lifecycle


def test_definition_requires_nonempty_unique_exact_step_tuple():
    module = _api()

    invalid = (
        [],
        (),
        ("",),
        (" 1",),
        ("1 ",),
        ("1", "1"),
    )

    for step_ids in invalid:
        with pytest.raises(module.ProcedureCatalogError):
            _definition(module, step_ids=step_ids)


def test_catalog_rejects_duplicate_exact_version():
    module = _api()

    first = _definition(module)
    second = _definition(
        module,
        procedure_name="Same identity, different supplied object",
    )

    with pytest.raises(module.DuplicateProcedureDefinitionError):
        module.ProcedureCatalog(
            definitions=(first, second),
        )


def test_catalog_allows_same_id_with_different_versions():
    module = _api()

    first = _definition(module)
    second = _definition(
        module,
        procedure_version="2.0",
        procedure_name="Procedure A v2",
    )

    catalog = module.ProcedureCatalog(
        definitions=(first, second),
    )

    assert catalog.count() == 2
    assert catalog.get("PROC-A", "1.0") is first
    assert catalog.get("PROC-A", "2.0") is second


def test_lookup_is_exact_without_case_trim_or_version_fallback():
    module = _api()
    definition = _definition(module)

    catalog = module.ProcedureCatalog(
        definitions=(definition,),
    )

    assert catalog.get("PROC-A", "1.0") is definition
    assert catalog.contains("PROC-A", "1.0") is True

    for procedure_id, version in (
        ("proc-a", "1.0"),
        (" PROC-A", "1.0"),
        ("PROC-A ", "1.0"),
        ("PROC-A", "1"),
        ("PROC-A", "1.0 "),
        ("PROC-A", "2.0"),
    ):
        assert catalog.contains(procedure_id, version) is False

        with pytest.raises(module.ProcedureNotFoundError):
            catalog.get(procedure_id, version)


def test_resolve_published_requires_exact_canonical_name():
    module = _api()
    definition = _definition(module)

    catalog = module.ProcedureCatalog(
        definitions=(definition,),
    )

    assert (
        catalog.resolve_published(
            procedure_id="PROC-A",
            procedure_version="1.0",
            procedure_name="Procedure A",
        )
        is definition
    )

    for name in (
        "procedure a",
        " Procedure A",
        "Procedure A ",
        "Other",
    ):
        with pytest.raises(module.ProcedureIdentityMismatchError):
            catalog.resolve_published(
                procedure_id="PROC-A",
                procedure_version="1.0",
                procedure_name=name,
            )


def test_resolve_published_rejects_draft_and_retired():
    module = _api()

    for lifecycle in (
        "draft",
        "retired",
    ):
        definition = _definition(
            module,
            lifecycle=lifecycle,
        )

        catalog = module.ProcedureCatalog(
            definitions=(definition,),
        )

        with pytest.raises(module.ProcedureNotPublishedError):
            catalog.resolve_published(
                procedure_id="PROC-A",
                procedure_version="1.0",
                procedure_name="Procedure A",
            )


def test_step_membership_is_exact_and_catalog_owned():
    module = _api()
    definition = _definition(module)

    catalog = module.ProcedureCatalog(
        definitions=(definition,),
    )

    assert catalog.contains_step("PROC-A", "1.0", "1") is True
    assert catalog.contains_step("PROC-A", "1.0", "2") is True

    for step_id in (
        "01",
        " 1",
        "1 ",
        "3",
    ):
        assert catalog.contains_step("PROC-A", "1.0", step_id) is False


def test_catalog_is_constructed_once_not_mutated_by_runtime_registration():
    module = _api()

    catalog = module.ProcedureCatalog(
        definitions=(
            _definition(module),
        ),
    )

    assert not hasattr(catalog, "register")


def test_catalog_does_not_duplicate_capability_resolution_or_cloud_authority():
    module = _api()

    assert not hasattr(module.ProcedureCatalog, "resolve_capability")
    assert not hasattr(module.ProcedureCatalog, "resolve_applicable_capability")

    source = inspect.getsource(module)
    tree = ast.parse(textwrap.dedent(source))

    imported_roots = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name
                for alias in node.names
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
        ):
            imported_roots.add(node.module or "")

    forbidden = (
        "agent_framework",
        "azure",
        "microsoft_teams",
        "src.agents",
        "src.channels",
        "src.persistence",
        "src.workflows.incident_resolution.procedure_capability_registry",
    )

    assert not any(
        root == prefix
        or root.startswith(prefix + ".")
        for root in imported_roots
        for prefix in forbidden
    )
