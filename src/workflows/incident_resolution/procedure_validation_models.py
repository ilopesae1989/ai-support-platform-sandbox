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

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)

from src.workflows.incident_resolution.operation_models import (
    OperationResult,
)

from src.workflows.incident_resolution.post_operation_observation import (
    AzureVmPowerStateObservation,
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

    post_operation_observation: (
        AzureVmPowerStateObservation | None
    ) = None

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

        observation = (
            self.post_operation_observation
        )

        if observation is not None:
            if (
                result.success is not True
                or result.technical_success is not True
            ):
                raise ValueError(
                    "post-operation observation sólo "
                    "puede acompañar un resultado "
                    "técnicamente exitoso."
                )

            if (
                result.operation_domain != "azure"
                or result.operation_kind
                != OperationKind.WRITE
                or result.operation_action
                != OperationAction.VM_START
                or result.capability_id
                != "azure.vm.start"
                or result.hitl_required is not True
            ):
                raise ValueError(
                    "post-operation observation sólo "
                    "es válida para el VM Start "
                    "Azure gobernado."
                )

            observation_comparisons = {
                "operation_id": (
                    observation.operation_id,
                    result.operation_id,
                ),
                "workflow_id": (
                    observation.workflow_id,
                    result.workflow_id,
                ),
                "approval_id": (
                    observation.approval_id,
                    result.approval_id,
                ),
                "target_resource": (
                    observation.target_resource,
                    result.target_resource,
                ),
            }

            changed_observation_fields = [
                field_name
                for field_name, values
                in observation_comparisons.items()
                if values[0] != values[1]
            ]

            if changed_observation_fields:
                raise ValueError(
                    "post-operation observation no "
                    "corresponde exactamente al "
                    "OperationResult. Campos distintos: "
                    + ", ".join(
                        changed_observation_fields
                    )
                )

            names = [
                parameter.name
                for parameter
                in result.resolved_parameters
            ]

            if len(names) != len(set(names)):
                raise ValueError(
                    "OperationResult contiene "
                    "resolved parameters duplicados."
                )

            resolved = {
                parameter.name:
                    parameter.value
                for parameter
                in result.resolved_parameters
            }

            expected_resolved = {
                "subscription_id": observation.subscription_id,
                "resource_group": observation.resource_group,
                "vm_name": observation.vm_name,
            }

            if resolved != expected_resolved:
                raise ValueError(
                    "post-operation observation no "
                    "corresponde a los parámetros "
                    "resueltos autoritativos."
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
