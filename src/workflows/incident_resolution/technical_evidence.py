from __future__ import annotations

from typing import Any

from pydantic import (
    Field,
    field_validator,
)

from .immutable_snapshot import (
    ImmutableSnapshotModel,
    freeze_payload,
)


class ToolResultEvidence(
    ImmutableSnapshotModel
):
    """
    Resultado observado de una function tool call.

    exception constituye una señal estructurada
    explícita de fallo en Agent Framework 1.13.0.
    """

    tool_call_id: str = Field(
        min_length=1
    )

    result_text: str | None = None

    exception: str | None = None

    source_message_id: str | None = None
    source_message_role: str | None = None


class McpResultEvidence(
    ImmutableSnapshotModel
):
    """
    Resultado observado de una llamada MCP.

    Agent Framework 1.13.0 proporciona output,
    pero no una señal universal normalizada
    de éxito/fallo.
    """

    mcp_call_id: str = Field(
        min_length=1
    )

    output: Any = None

    source_message_id: str | None = None
    source_message_role: str | None = None

    @field_validator(
        "output",
        mode="after",
    )
    @classmethod
    def freeze_output(
        cls,
        value: Any,
    ) -> Any:
        return freeze_payload(
            value
        )


class ResponseErrorEvidence(
    ImmutableSnapshotModel
):
    """
    Error estructurado Content(type="error").
    """

    message: str | None = None

    error_code: str | None = None
    error_details: str | None = None

    source_message_id: str | None = None
    source_message_role: str | None = None
