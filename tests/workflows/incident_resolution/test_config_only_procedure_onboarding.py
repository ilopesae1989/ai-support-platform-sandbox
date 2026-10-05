from __future__ import annotations

import inspect
import json
from pathlib import Path

from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)

from src.workflows.incident_resolution.governed_procedure_admission import (
    GovernedProcedureAdmissionPolicy,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.procedure_admission import (
    ProcedureAdmissionPolicy,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    load_procedure_capability_bindings,
)

from src.workflows.incident_resolution.procedure_catalog import (
    load_procedure_catalog,
)

from src.workflows.incident_resolution.procedure_governance import (
    ProcedureGovernanceApprovalPolicy,
    load_procedure_governance,
)

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)


PROCEDURE_ID = "F25-CONFIG-ONLY-ONBOARD-001"
PROCEDURE_VERSION = "1.0"
PROCEDURE_NAME = "Configuration-only Azure VM start procedure"
STEP_ID = "1"
CAPABILITY_ID = "azure.vm.start"


def _write_json(
    tmp_path: Path,
    name: str,
    payload: object,
) -> Path:
    path = tmp_path / name

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def _configuration(
    tmp_path: Path,
):
    catalog_path = _write_json(
        tmp_path,
        "procedure_catalog.json",
        {
            "schema_version": "1.0",
            "procedures": [
                {
                    "procedure_id": PROCEDURE_ID,
                    "procedure_version": PROCEDURE_VERSION,
                    "procedure_name": PROCEDURE_NAME,
                    "lifecycle": "published",
                    "step_ids": [
                        STEP_ID,
                    ],
                },
            ],
        },
    )

    governance_path = _write_json(
        tmp_path,
        "procedure_governance.json",
        {
            "schema_version": "1.0",
            "procedures": [
                {
                    "procedure_id": PROCEDURE_ID,
                    "procedure_version": PROCEDURE_VERSION,
                    "owner": "team-config-test",
                    "governance_approval_status": "approved",
                    "governance_approval_reference": "GOV-F25-CONFIG-001",
                    "compatible_previous_versions": [],
                    "rollback_version": None,
                },
            ],
        },
    )

    binding_path = _write_json(
        tmp_path,
        "procedure_capability_bindings.json",
        {
            "schema_version": "1.0",
            "bindings": [
                {
                    "procedure_id": PROCEDURE_ID,
                    "procedure_version": PROCEDURE_VERSION,
                    "step_id": STEP_ID,
                    "capability_id": CAPABILITY_ID,
                    "applicability": {
                        "allowed_environments": [
                            "sandbox",
                        ],
                        "allowed_incident_origins": [
                            "observed",
                        ],
                    },
                },
            ],
        },
    )

    return (
        catalog_path,
        governance_path,
        binding_path,
    )


def _compose_from_configuration(
    tmp_path: Path,
):
    catalog_path, governance_path, binding_path = _configuration(
        tmp_path
    )

    catalog = load_procedure_catalog(
        catalog_path
    )

    capability_registry = build_default_capability_registry()

    governance_registry = load_procedure_governance(
        governance_path,
        catalog=catalog,
    )

    binding_registry = load_procedure_capability_bindings(
        binding_path,
        catalog=catalog,
        capability_registry=capability_registry,
    )

    admission_policy = ProcedureAdmissionPolicy(
        catalog=catalog,
        legacy_compatibility=(),
    )

    governance_policy = ProcedureGovernanceApprovalPolicy(
        registry=governance_registry,
    )

    governed_admission = GovernedProcedureAdmissionPolicy(
        admission_policy=admission_policy,
        governance_policy=governance_policy,
    )

    return (
        capability_registry,
        binding_registry,
        governed_admission,
    )


def test_new_procedure_is_onboarded_by_configuration_and_reuses_existing_capability(
    tmp_path,
):
    capability_registry, binding_registry, governed_admission = (
        _compose_from_configuration(
            tmp_path
        )
    )

    admission = governed_admission.admit(
        procedure_id=PROCEDURE_ID,
        procedure_version=PROCEDURE_VERSION,
        procedure_name=PROCEDURE_NAME,
    )

    assert admission.procedure_id == PROCEDURE_ID
    assert admission.procedure_version == PROCEDURE_VERSION
    assert admission.source == "catalog"

    context = OperationalContext(
        alert_id="ALT-F25-CONFIG-001",
        affected_resource="vm-config-only",
        resource_type="Microsoft.Compute/virtualMachines",
        service="Azure Virtual Machines",
        environment="sandbox",
        incident_origin="observed",
        subscription_id="sub-test",
        resource_group="rg-test",
        vm_name="vm-config-only",
        tenant_id=None,
        correlation_id="corr-f25-config-001",
    )

    capability = binding_registry.resolve_applicable_capability(
        procedure_id=PROCEDURE_ID,
        procedure_version=PROCEDURE_VERSION,
        step_id=STEP_ID,
        operational_context=context,
    )

    installed = capability_registry.get(
        CAPABILITY_ID
    )

    assert capability is installed
    assert capability.capability_id == CAPABILITY_ID
    assert capability.hitl_required is True


def test_workflow_composition_exposes_both_configuration_authorities():
    signature = inspect.signature(
        build_incident_resolution_workflow
    )

    for parameter_name in (
        "procedure_capability_registry",
        "governed_procedure_admission_policy",
    ):
        assert parameter_name in signature.parameters
        assert signature.parameters[parameter_name].default is None


def test_config_only_procedure_identity_is_absent_from_product_core():
    repo = Path(__file__).resolve().parents[3]
    src = repo / "src"

    hits = []

    allowed_suffixes = {
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
    }

    for path in src.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in allowed_suffixes:
            continue

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except UnicodeError:
            continue

        if PROCEDURE_ID in content:
            hits.append(
                path.relative_to(
                    repo
                ).as_posix()
            )

    assert hits == []