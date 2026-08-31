from __future__ import annotations

from pathlib import Path

from agent_framework import (
    FileCheckpointStorage,
)

from src.runtime.procedure.workflow import (
    _allowed_checkpoint_types,
)


_INCIDENT_ADDITIONAL_CHECKPOINT_TYPES = frozenset(
    {
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

        "src.workflows.incident_resolution.alert_models:"
        "NormalizedAlert",

        "src.workflows.incident_resolution.workflow_input:"
        "IncidentWorkflowInput",

        "src.workflows.incident_resolution.azure_operations_models:"
        "AzureOperationResult",

        "src.workflows.incident_resolution.azure_operations_models:"
        "VerifiedAzureOperationRequest",

        "src.workflows.incident_resolution.azure_operations_models:"
        "VerifiedResolvedParameter",

        "src.workflows.incident_resolution.immutable_snapshot:"
        "FrozenDict",

        "src.workflows.incident_resolution.immutable_snapshot:"
        "FrozenList",

        "src.workflows.incident_resolution.immutable_snapshot:"
        "FrozenResolvedParameter",

        "src.workflows.incident_resolution.mcp_evidence:"
        "McpCallEvidence",

        "src.workflows.incident_resolution.operation_evidence:"
        "OperationEvidence",

        "src.workflows.incident_resolution.models:"
        "ClassifiedAlertContext",

        "src.workflows.incident_resolution.models:"
        "ExecutionIdentity",

        "src.workflows.incident_resolution.models:"
        "KnowledgeEnrichedAlertContext",

        "src.workflows.incident_resolution.models:"
        "ProcedureExecutionContext",

        "src.workflows.incident_resolution.models:"
        "ProcedureExecutionInput",

        "src.workflows.incident_resolution.models:"
        "ProcedureExecutionRequest",

        "src.workflows.incident_resolution.models:"
        "TriagedAlertContext",

        "src.workflows.incident_resolution.operation_models:"
        "OperationResult",

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
    }
)


def incident_checkpoint_allowed_types() -> set[str]:
    """
    Devuelve la allowlist explícita del workflow
    incident-resolution.

    Conserva íntegramente el contrato durable del
    workflow de procedimiento y añade únicamente
    los tipos application-specific observados en
    los ciclos APPROVE + REJECT del incidente.

    No descubre tipos dinámicamente.
    No permite módulos por prefijo.
    No permite fallback.
    """

    return (
        set(
            _allowed_checkpoint_types()
        )
        | set(
            _INCIDENT_ADDITIONAL_CHECKPOINT_TYPES
        )
    )


def build_incident_checkpoint_storage(
    checkpoint_path: str | Path,
) -> FileCheckpointStorage:
    """
    Construye FileCheckpointStorage para
    incident-resolution con allowlist explícita.

    El directorio de checkpoint es una trust
    boundary y debe estar protegido por el host.
    """

    if not isinstance(
        checkpoint_path,
        (
            str,
            Path,
        ),
    ):
        raise TypeError(
            "checkpoint_path debe ser str o Path."
        )

    path = Path(
        checkpoint_path
    )

    if (
        not str(path)
        or not str(path).strip()
    ):
        raise ValueError(
            "checkpoint_path no puede estar vacío."
        )

    return FileCheckpointStorage(
        path,
        allowed_checkpoint_types=(
            incident_checkpoint_allowed_types()
        ),
    )
