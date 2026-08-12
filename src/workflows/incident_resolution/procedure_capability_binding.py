from __future__ import annotations

from dataclasses import (
    dataclass,
)


class ProcedureCapabilityBindingError(
    ValueError
):
    """
    El binding entre un paso de procedimiento y una
    capability operacional no cumple el contrato
    gobernado por Python.
    """

    pass


@dataclass(
    frozen=True
)
class ProcedureCapabilityBinding:
    """
    Binding autoritativo:

        procedure_id
        procedure_version
        step_id
                ↓
        capability_id

    El LLM no genera este objeto.

    El agente puede identificar el procedimiento y
    el paso que corresponde procesar.

    Python determina qué capability está asociada
    exactamente a ese paso versionado.
    """

    procedure_id: str

    procedure_version: str

    step_id: str

    capability_id: str

    def __post_init__(
        self,
    ) -> None:

        self._validate_exact_string(
            name="procedure_id",
            value=self.procedure_id,
        )

        self._validate_exact_string(
            name="procedure_version",
            value=self.procedure_version,
        )

        self._validate_exact_string(
            name="step_id",
            value=self.step_id,
        )

        self._validate_exact_string(
            name="capability_id",
            value=self.capability_id,
        )

    @staticmethod
    def _validate_exact_string(
        *,
        name: str,
        value: str,
    ) -> None:

        if not isinstance(
            value,
            str,
        ):
            raise (
                ProcedureCapabilityBindingError(
                    f"{name} debe ser string."
                )
            )

        if not value:
            raise (
                ProcedureCapabilityBindingError(
                    f"{name} no puede estar vacío."
                )
            )

        if value != value.strip():
            raise (
                ProcedureCapabilityBindingError(
                    f"{name} no puede contener "
                    "espacios al inicio o al final."
                )
            )