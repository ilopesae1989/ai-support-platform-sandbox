from __future__ import annotations

from collections.abc import Mapping

from typing import (
    Any,
    Literal,
    Self,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from .immutable_snapshot import (
    FrozenResolvedParameter,
    freeze_list,
)

from .operation_models import (
    OperationRequest,
    OperationResult,
)


class AzureOperationRequest(
    OperationRequest
):
    """
    Operación Azure candidata.

    No representa autorización.
    """

    pass


class VerifiedResolvedParameter(
    FrozenResolvedParameter
):
    """
    Parámetro aprobado e inmutable.
    """

    pass


class VerifiedAzureOperationRequest(
    AzureOperationRequest
):
    """
    Snapshot de una operación Azure que ha
    atravesado PreCallSecurityVerifier dentro
    de la topología autorizada.

    La clase no constituye por sí misma una
    credencial de autorización.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    required_parameters: list[str] = Field(
        default_factory=list
    )

    resolved_parameters: list[
        VerifiedResolvedParameter
    ] = Field(
        default_factory=list
    )

    security_verified: Literal[
        True
    ]

    verification_source: Literal[
        "pre_call_security_verifier"
    ]

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

    def model_copy(
        self,
        *,
        update: Mapping[
            str,
            Any,
        ] | None = None,
        deep: bool = False,
    ) -> Self:
        if update:
            raise TypeError(
                "VerifiedAzureOperationRequest "
                "no permite model_copy(update=...). "
                "La operación debe volver a pasar "
                "por PreCallSecurityVerifier."
            )

        return super().model_copy(
            update=None,
            deep=deep,
        )


class AzureOperationResult(
    OperationResult
):
    """
    Especialización Azure del resultado común.
    """

    pass
