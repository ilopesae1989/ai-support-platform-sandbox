from __future__ import annotations

from pydantic import (
    model_validator,
)

from src.agents.contracts import (
    ProcedureValidationResult,
)

from src.workflows.incident_resolution.immutable_snapshot import (
    ImmutableSnapshotModel,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)


class ProcedureValidationStep(
    ImmutableSnapshotModel
):
    """
    Snapshot mínimo de la semántica del paso
    necesaria para interpretar el resultado.

    No contiene autoridad de ejecución.
    """

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    description: str
    expected_result: str | None = None
    verification: str | None = None


class ProcedureValidationRequest(
    ImmutableSnapshotModel
):
    """
    Entrada trusted para validación cognitiva.

    OperationEvidence permanece exclusivamente
    dentro de OperationResult para evitar
    duplicar fuentes de verdad.
    """

    operation_result: OperationResult
    step: ProcedureValidationStep

    @model_validator(mode="after")
    def validate_step_identity(
        self,
    ):
        result = (
            self.operation_result
        )

        comparisons = {
            "procedure_id": (
                result.procedure_id,
                self.step.procedure_id,
            ),
            "procedure_version": (
                result.procedure_version,
                self.step.procedure_version,
            ),
            "current_step": (
                result.current_step,
                self.step.current_step,
            ),
            "step_id": (
                result.step_id,
                self.step.step_id,
            ),
        }

        changed_fields = [
            field_name
            for field_name, values
            in comparisons.items()
            if values[0] != values[1]
        ]

        if changed_fields:
            raise ValueError(
                "ProcedureValidationStep no corresponde "
                "a OperationResult. Campos distintos: "
                + ", ".join(
                    changed_fields
                )
            )

        return self


class ProcedureValidationContext(
    ImmutableSnapshotModel
):
    """
    Envelope posterior al Procedure Agent.

    request permanece trusted.
    result es sólo una propuesta cognitiva.
    """

    request: ProcedureValidationRequest
    result: ProcedureValidationResult

    @model_validator(mode="after")
    def validate_operation_identity(
        self,
    ):
        if (
            self.result.operation_id
            !=
            self.request
            .operation_result
            .operation_id
        ):
            raise ValueError(
                "ProcedureValidationResult no corresponde "
                "a la operación solicitada."
            )

        return self

