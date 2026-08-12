from __future__ import annotations

import json

from collections.abc import (
    Mapping,
)

from typing import (
    Any,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from src.runtime.procedure.models import (
    NextAction,
    OperationAction,
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

    operation_action: OperationAction | None = None

    #
    # Capability y policy exactas que originaron
    # la operación aprobada.
    #
    capability_id: str | None = None

    hitl_required: bool | None = None

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

    @staticmethod
    def _extract_explicit_mcp_status(
        value: Any,
    ) -> int | None:
        """
        Extrae únicamente un status numérico
        explícito de un resultado MCP.

        No interpreta lenguaje natural.
        No infiere éxito por el nombre de la tool.
        No infiere éxito por ausencia de errores.

        Formas soportadas:

            {"status": 200}

        o la forma observada LIVE:

            [
                {
                    "type": "text",
                    "text": "{\"status\":200,...}"
                }
            ]

        Ante cualquier formato no interpretable,
        devuelve None.
        """

        if value is None:
            return None

        #
        # El output real de Agent Framework puede
        # contener JSON serializado dentro de text.
        #
        if isinstance(
            value,
            str,
        ):
            try:
                parsed = json.loads(
                    value
                )

            except (
                json.JSONDecodeError,
                TypeError,
            ):
                return None

            return (
                OperationEvidence
                ._extract_explicit_mcp_status(
                    parsed
                )
            )

        #
        # FrozenDict implementa Mapping, por lo que
        # funciona también sobre el snapshot ya
        # congelado.
        #
        if isinstance(
            value,
            Mapping,
        ):
            status = value.get(
                "status"
            )

            #
            # bool es subtipo de int en Python.
            # Debe excluirse expresamente.
            #
            if (
                isinstance(
                    status,
                    int,
                )
                and not isinstance(
                    status,
                    bool,
                )
            ):
                return status

            #
            # Forma observada LIVE:
            #
            # {
            #   "type": "text",
            #   "text": "{...JSON...}"
            # }
            #
            if (
                value.get("type")
                == "text"
            ):
                text = value.get(
                    "text"
                )

                if isinstance(
                    text,
                    str,
                ):
                    return (
                        OperationEvidence
                        ._extract_explicit_mcp_status(
                            text
                        )
                    )

            return None

        #
        # FrozenList implementa list.
        #
        if isinstance(
            value,
            (
                list,
                tuple,
            ),
        ):
            statuses: list[int] = []

            for item in value:
                status = (
                    OperationEvidence
                    ._extract_explicit_mcp_status(
                        item
                    )
                )

                if status is not None:
                    statuses.append(
                        status
                    )

            if not statuses:
                return None

            #
            # Dos estados explícitos distintos dentro
            # del mismo resultado son ambiguos.
            #
            if (
                len(set(statuses))
                != 1
            ):
                return None

            return statuses[0]

        return None

    def _derive_tool_technical_success(
        self,
    ) -> bool | None:
        """
        Deriva resultado técnico exclusivamente
        de function tool evidence.
        """

        if (
            not self.tool_calls
            and not self.tool_results
        ):
            return None

        if any(
            result.exception
            is not None
            for result
            in self.tool_results
        ):
            return False

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

    def _derive_mcp_technical_success(
        self,
    ) -> bool | None:
        """
        Deriva resultado técnico de evidencia MCP
        sólo cuando existe prueba estructurada.

        Requisitos:

        - al menos una llamada MCP;
        - al menos un resultado MCP;
        - correspondencia exacta entre call_id
          y result_id;
        - cada resultado debe exponer un status
          numérico explícito.

        Semántica:

            2xx      -> éxito demostrado
            4xx/5xx  -> fallo demostrado
            otro     -> indeterminado

        No se interpreta texto semánticamente.
        """

        if (
            not self.mcp_calls
            and not self.mcp_results
        ):
            return None

        if (
            not self.mcp_calls
            or not self.mcp_results
        ):
            return None

        call_ids = {
            call.mcp_call_id
            for call
            in self.mcp_calls
        }

        result_ids = {
            result.mcp_call_id
            for result
            in self.mcp_results
        }

        #
        # Un resultado de otra llamada jamás puede
        # demostrar el éxito de ésta.
        #
        if (
            call_ids
            != result_ids
        ):
            return None

        statuses: list[int] = []

        for result in self.mcp_results:
            status = (
                self
                ._extract_explicit_mcp_status(
                    result.output
                )
            )

            if status is None:
                return None

            statuses.append(
                status
            )

        #
        # Un error explícito en cualquiera de los
        # resultados demuestra fallo técnico.
        #
        if any(
            400 <= status < 600
            for status
            in statuses
        ):
            return False

        #
        # Todas las llamadas deben demostrar éxito.
        #
        if all(
            200 <= status < 300
            for status
            in statuses
        ):
            return True

        #
        # 1xx, 3xx u otro estado no definido por
        # nuestro contrato sigue siendo desconocido.
        #
        return None

    def derive_technical_success(
        self,
    ) -> bool | None:
        """
        Derivación exclusivamente estructurada.

        True:
            toda la evidencia técnica presente
            demuestra éxito.

        False:
            existe una evidencia explícita de fallo.

        None:
            la evidencia es insuficiente,
            inconsistente o ambigua.
        """

        #
        # Un error estructurado de respuesta tiene
        # prioridad sobre cualquier otra evidencia.
        #
        if self.response_errors:
            return False

        tool_present = bool(
            self.tool_calls
            or self.tool_results
        )

        mcp_present = bool(
            self.mcp_calls
            or self.mcp_results
        )

        if (
            not tool_present
            and not mcp_present
        ):
            return None

        signals: list[
            bool | None
        ] = []

        if tool_present:
            signals.append(
                self
                ._derive_tool_technical_success()
            )

        if mcp_present:
            signals.append(
                self
                ._derive_mcp_technical_success()
            )

        #
        # Una prueba explícita de fallo domina.
        #
        if any(
            signal is False
            for signal
            in signals
        ):
            return False

        #
        # Si cualquiera de los canales utilizados no
        # puede demostrarse, el resultado completo
        # sigue siendo indeterminado.
        #
        if any(
            signal is None
            for signal
            in signals
        ):
            return None

        if (
            signals
            and all(
                signal is True
                for signal
                in signals
            )
        ):
            return True
