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
class ProcedureApplicability:
    """
    Restricciones autoritativas del binding.

    La aplicabilidad se evalúa mediante coincidencia
    exacta en Python.

    No existe normalización, wildcard, fallback ni
    autoridad procedente de texto libre.
    """

    allowed_environments: tuple[
        str,
        ...
    ]

    allowed_incident_origins: tuple[
        str,
        ...
    ]

    def __post_init__(
        self,
    ) -> None:

        self._validate_exact_tuple(
            name="allowed_environments",
            values=self.allowed_environments,
        )

        self._validate_exact_tuple(
            name="allowed_incident_origins",
            values=self.allowed_incident_origins,
        )

        allowed_origins = (
            "observed",
            "synthetic_demo",
        )

        for incident_origin in (
            self.allowed_incident_origins
        ):
            if incident_origin not in allowed_origins:
                raise ProcedureCapabilityBindingError(
                    "incident_origin no pertenece "
                    "al contrato permitido."
                )

    @staticmethod
    def _validate_exact_tuple(
        *,
        name: str,
        values: tuple[
            str,
            ...
        ],
    ) -> None:

        if not isinstance(values, tuple):
            raise ProcedureCapabilityBindingError(
                f"{name} debe ser tuple."
            )

        if not values:
            raise ProcedureCapabilityBindingError(
                f"{name} no puede estar vacío."
            )

        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                raise ProcedureCapabilityBindingError(
                    f"{name} sólo admite strings."
                )

            if not value:
                raise ProcedureCapabilityBindingError(
                    f"{name} no admite strings vacíos."
                )

            if value != value.strip():
                raise ProcedureCapabilityBindingError(
                    f"{name} no admite espacios "
                    "al inicio o al final."
                )

            if value in seen:
                raise ProcedureCapabilityBindingError(
                    f"{name} contiene valores duplicados."
                )

            seen.add(value)


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

    applicability: ProcedureApplicability

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

        if not isinstance(
            self.applicability,
            ProcedureApplicability,
        ):
            raise ProcedureCapabilityBindingError(
                "applicability debe ser "
                "ProcedureApplicability."
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