from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationKind,
)

from .immutable_snapshot import (
    FrozenResolvedParameter,
    ImmutableSnapshotModel,
    freeze_list,
)

from .mcp_evidence import (
    McpCallEvidence,
)

from .technical_evidence import (
    McpResultEvidence,
    ResponseErrorEvidence,
    ToolResultEvidence,
)

from .tool_evidence import (
    ToolCallEvidence,
)


class OperationEvidence(
    ImmutableSnapshotModel
):
    """
    Snapshot profundamente inmutable de evidencia.

    Las listas siguen siendo compatibles con list
    para no modificar los contratos públicos de
    15.9-15.11, pero son FrozenList internamente.
    """

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

    tool_calls: list[
        ToolCallEvidence
    ] = Field(
        default_factory=list
    )

    mcp_calls: list[
        McpCallEvidence
    ] = Field(
        default_factory=list
    )

    tool_results: list[
        ToolResultEvidence
    ] = Field(
        default_factory=list
    )

    mcp_results: list[
        McpResultEvidence
    ] = Field(
        default_factory=list
    )

    response_errors: list[
        ResponseErrorEvidence
    ] = Field(
        default_factory=list
    )

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
        "tool_calls",
        "mcp_calls",
        "tool_results",
        "mcp_results",
        "response_errors",
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
    def validate_call_and_result_ids(
        self,
    ):
        tool_call_ids = [
            item.tool_call_id
            for item
            in self.tool_calls
        ]

        if (
            len(tool_call_ids)
            != len(set(tool_call_ids))
        ):
            raise ValueError(
                "OperationEvidence contiene "
                "tool_call_id duplicados."
            )

        mcp_call_ids = [
            item.mcp_call_id
            for item
            in self.mcp_calls
        ]

        if (
            len(mcp_call_ids)
            != len(set(mcp_call_ids))
        ):
            raise ValueError(
                "OperationEvidence contiene "
                "mcp_call_id duplicados."
            )

        tool_result_ids = [
            item.tool_call_id
            for item
            in self.tool_results
        ]

        if (
            len(tool_result_ids)
            != len(set(tool_result_ids))
        ):
            raise ValueError(
                "OperationEvidence contiene "
                "tool result call_id duplicados."
            )

        mcp_result_ids = [
            item.mcp_call_id
            for item
            in self.mcp_results
        ]

        if (
            len(mcp_result_ids)
            != len(set(mcp_result_ids))
        ):
            raise ValueError(
                "OperationEvidence contiene "
                "MCP result call_id duplicados."
            )

        return self

    def derive_technical_success(
        self,
    ) -> bool | None:
        """
        Derivación exclusivamente estructurada.
        """

        if self.response_errors:
            return False

        if any(
            result.exception
            is not None
            for result
            in self.tool_results
        ):
            return False

        if (
            self.mcp_calls
            or self.mcp_results
        ):
            return None

        if not self.tool_calls:
            return None

        call_ids = {
            call.tool_call_id
            for call
            in self.tool_calls
        }

        result_ids = {
            result.tool_call_id
            for result
            in self.tool_results
        }

        if (
            call_ids
            != result_ids
        ):
            return None

        return True
