import importlib

from pathlib import Path

from src.runtime.procedure.workflow import (
    _allowed_checkpoint_types,
)


EXPECTED_ADDITIONAL_TYPES = {
    "src.agents.contracts:AlertTriageResult",
    "src.agents.contracts:ClassificationResult",
    "src.agents.contracts:EscalationInfo",
    "src.agents.contracts:KnowledgeDocument",
    "src.agents.contracts:KnowledgeResult",
    "src.agents.contracts:ProcedureExecutionReference",
    "src.agents.contracts:ProcedureExecutionResult",
    "src.agents.contracts:ProcedureExecutionStep",
    "src.agents.contracts:ProcedureReference",
    "src.agents.contracts:ProcedureValidationEscalation",
    "src.agents.contracts:ProcedureValidationResult",

    "src.workflows.incident_resolution.alert_models:NormalizedAlert",

    "src.workflows.incident_resolution.azure_operations_models:"
    "AzureOperationResult",

    "src.workflows.incident_resolution.azure_operations_models:"
    "VerifiedAzureOperationRequest",

    "src.workflows.incident_resolution.azure_operations_models:"
    "VerifiedResolvedParameter",

    "src.workflows.incident_resolution.immutable_snapshot:FrozenDict",
    "src.workflows.incident_resolution.immutable_snapshot:FrozenList",
    "src.workflows.incident_resolution.immutable_snapshot:"
    "FrozenResolvedParameter",

    "src.workflows.incident_resolution.mcp_evidence:McpCallEvidence",

    "src.workflows.incident_resolution.operation_evidence:"
    "OperationEvidence",

    "src.workflows.incident_resolution.models:ClassifiedAlertContext",
    "src.workflows.incident_resolution.models:ExecutionIdentity",
    "src.workflows.incident_resolution.models:"
    "KnowledgeEnrichedAlertContext",
    "src.workflows.incident_resolution.models:ProcedureExecutionContext",
    "src.workflows.incident_resolution.models:ProcedureExecutionInput",
    "src.workflows.incident_resolution.models:ProcedureExecutionRequest",
    "src.workflows.incident_resolution.models:TriagedAlertContext",

    "src.workflows.incident_resolution.operation_models:OperationResult",

    "src.workflows.incident_resolution.operational_context:"
    "OperationalContext",

    "src.workflows.incident_resolution.technical_evidence:"
    "McpResultEvidence",

    "src.workflows.incident_resolution.technical_evidence:"
    "ResponseErrorEvidence",

    "src.workflows.incident_resolution.technical_evidence:"
    "ToolResultEvidence",

    "src.workflows.incident_resolution.tool_evidence:"
    "ToolCallEvidence",

    "src.workflows.incident_resolution.post_operation_observation:"
    "AzureVmPowerStateObservation",

    "src.workflows.incident_resolution.procedure_validation_models:"
    "ProcedureValidationContext",

    "src.workflows.incident_resolution.procedure_validation_models:"
    "ProcedureValidationRequest",

    "src.workflows.incident_resolution.procedure_validation_models:"
    "ProcedureValidationStep",
    "src.workflows.incident_resolution.workflow_input:IncidentWorkflowInput",  # TDD_PHASE18_INCIDENT_CHECKPOINT_ALLOWLIST_43
}


def load_module():
    return importlib.import_module(
        "src.workflows.incident_resolution."
        "checkpoint_storage"
    )


def resolve_type_token(
    token: str,
):
    module_name, separator, qualname = (
        token.partition(":")
    )

    assert separator == ":"
    assert module_name
    assert qualname

    value = importlib.import_module(
        module_name
    )

    for part in qualname.split("."):
        value = getattr(
            value,
            part,
        )

    return value


def test_incident_allowlist_extends_existing_contract_exactly():
    module = load_module()

    base = set(
        _allowed_checkpoint_types()
    )

    allowed = set(
        module
        .incident_checkpoint_allowed_types()
    )

    assert len(base) == 15

    assert base <= allowed

    assert (
        allowed - base
        == EXPECTED_ADDITIONAL_TYPES
    )

    assert len(
        EXPECTED_ADDITIONAL_TYPES
    ) == 38

    assert len(allowed) == 53

    assert (
        "src.runtime.procedure.workflow:"
        "ApprovalOutcome"
        in allowed
    )


def test_every_incident_allowlist_entry_resolves_to_real_type():
    module = load_module()

    allowed = (
        module
        .incident_checkpoint_allowed_types()
    )

    assert len(allowed) == 53

    for token in allowed:
        resolved = resolve_type_token(
            token
        )

        assert isinstance(
            resolved,
            type,
        ), token


def test_builder_passes_exact_allowlist_to_file_checkpoint_storage(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    captured = {}

    expected_storage = object()

    def fake_file_checkpoint_storage(
        directory,
        *,
        allowed_checkpoint_types,
    ):
        captured["directory"] = (
            directory
        )

        captured[
            "allowed_checkpoint_types"
        ] = set(
            allowed_checkpoint_types
        )

        return expected_storage

    monkeypatch.setattr(
        module,
        "FileCheckpointStorage",
        fake_file_checkpoint_storage,
    )

    checkpoint_path = (
        tmp_path
        / "incident-checkpoints"
    )

    result = (
        module
        .build_incident_checkpoint_storage(
            checkpoint_path
        )
    )

    assert result is expected_storage

    assert (
        Path(
            captured["directory"]
        )
        == checkpoint_path
    )

    assert (
        captured[
            "allowed_checkpoint_types"
        ]
        == set(
            module
            .incident_checkpoint_allowed_types()
        )
    )

    assert len(
        captured[
            "allowed_checkpoint_types"
        ]
    ) == 53

# TDD_PHASE18_INCIDENT_CHECKPOINT_ADDITIONAL_38

# TDD_PHASE18_INCIDENT_CHECKPOINT_TOTAL_53
