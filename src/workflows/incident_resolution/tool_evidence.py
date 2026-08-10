from __future__ import annotations

from typing import Any

from pydantic import (
    Field,
    field_validator,
)

from .immutable_snapshot import (
    FrozenDict,
    ImmutableSnapshotModel,
    freeze_payload,
)


class ToolCallEvidence(
    ImmutableSnapshotModel
):
    """
    Evidencia inmutable de una solicitud
    function tool.

    FASE 15.9:
    - call id;
    - nombre;
    - argumentos;
    - mensaje de origen.

    No contiene resultado técnico.
    """

    tool_call_id: str = Field(
        min_length=1
    )

    tool_name: str = Field(
        min_length=1
    )

    arguments: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    source_message_id: str | None = None
    source_message_role: str | None = None

    @field_validator(
        "arguments",
        mode="after",
    )
    @classmethod
    def freeze_arguments(
        cls,
        value: dict[
            str,
            Any,
        ],
    ) -> dict[
        str,
        Any,
    ]:
        frozen = freeze_payload(
            value
        )

        if not isinstance(
            frozen,
            FrozenDict,
        ):
            raise ValueError(
                "ToolCallEvidence.arguments "
                "debe ser un mapping."
            )

        return frozen
