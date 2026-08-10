from __future__ import annotations

from collections.abc import Mapping

from typing import (
    Any,
    Self,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
    ResolvedParameter,
)

from .immutable_snapshot import (
    FrozenResolvedParameter,
    freeze_list,
)

from .operation_evidence import (
    OperationEvidence,
)


class OperationRequest(BaseModel):
    """
    Contrato común vendor-neutral de una operación
    candidata.

    OperationRequest NO representa autorización.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    operation_id: str

    workflow_id: str
    approval_id: str

    alert_id: str

    correlation_id: str | None = None
    conversation_id: str | None = None

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    operation_domain: str
    operation_kind: OperationKind

    next_action: NextAction

    target_resource: str | None = None

    required_parameters: list[str] = Field(
        default_factory=list
    )

    resolved_parameters: list[
        ResolvedParameter
    ] = Field(
        default_factory=list
    )


class OperationResult(BaseModel):
    """
    Snapshot profundamente inmutable del resultado.

    success:
        indica si el executor completó la llamada
        a su backend sin excepción.

    technical_success:
        True  -> éxito demostrado.
        False -> fallo demostrado.
        None  -> indeterminado.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    operation_id: str

    workflow_id: str
    approval_id: str

    alert_id: str

    correlation_id: str | None = None
    conversation_id: str | None = None

    procedure_id: str
    procedure_version: str | None = None

    current_step: int
    step_id: str

    operation_domain: str
    operation_kind: OperationKind

    next_action: NextAction

    target_resource: str | None = None

    required_parameters: list[str] = Field(
        default_factory=list
    )

    resolved_parameters: list[
        FrozenResolvedParameter
    ] = Field(
        default_factory=list
    )

    success: bool

    technical_success: bool | None = None

    response_text: str | None = None
    error: str | None = None

    evidence: OperationEvidence | None = None

    @field_validator(
        "resolved_parameters",
        mode="before",
    )
    @classmethod
    def normalize_resolved_parameters(
        cls,
        value,
    ):
        if value is None:
            return []

        return [
            (
                item.model_dump(
                    mode="python"
                )
                if isinstance(
                    item,
                    BaseModel,
                )
                else item
            )
            for item
            in value
        ]

    @field_validator(
        "required_parameters",
        "resolved_parameters",
        mode="after",
    )
    @classmethod
    def freeze_collections(
        cls,
        value,
    ):
        return freeze_list(
            value
        )

    @model_validator(
        mode="after"
    )
    def validate_result_integrity(
        self,
    ):
        if (
            self.success is False
            and self.technical_success is True
        ):
            raise ValueError(
                "Una invocación fallida no puede "
                "declarar technical_success=True."
            )

        if self.evidence is None:
            if (
                self.success is True
                and self.technical_success
                is not None
            ):
                raise ValueError(
                    "technical_success no puede "
                    "declararse sin evidencia "
                    "técnica cuando success=True."
                )

            return self

        identity_fields = (
            "operation_id",
            "workflow_id",
            "approval_id",
            "alert_id",
            "correlation_id",
            "conversation_id",
            "procedure_id",
            "procedure_version",
            "current_step",
            "step_id",
            "operation_domain",
            "operation_kind",
            "next_action",
            "target_resource",
            "required_parameters",
            "resolved_parameters",
        )

        changed_fields = [
            field_name
            for field_name
            in identity_fields
            if (
                getattr(
                    self.evidence,
                    field_name,
                )
                != getattr(
                    self,
                    field_name,
                )
            )
        ]

        if changed_fields:
            raise ValueError(
                "OperationEvidence no corresponde "
                "a la identidad del resultado. "
                "Campos distintos: "
                + ", ".join(
                    changed_fields
                )
            )

        expected_technical_success = (
            self.evidence
            .derive_technical_success()
        )

        if (
            self.technical_success
            != expected_technical_success
        ):
            raise ValueError(
                "technical_success no corresponde "
                "a la evidencia técnica."
            )

        return self

    def model_copy(
        self,
        *,
        update: Mapping[
            str,
            Any,
        ] | None = None,
        deep: bool = False,
    ) -> Self:
        """
        Cualquier update vuelve a ejecutar
        validación completa.
        """

        if not update:
            return super().model_copy(
                update=None,
                deep=deep,
            )

        payload = self.model_dump(
            mode="python"
        )

        payload.update(
            dict(update)
        )

        return type(self).model_validate(
            payload
        )
