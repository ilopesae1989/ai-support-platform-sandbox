from __future__ import annotations

from dataclasses import (
    dataclass,
)

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)


class OperationalCapabilityError(
    ValueError
):
    """
    La definición de una capability operacional
    no cumple el contrato de seguridad de la
    plataforma.
    """

    pass


@dataclass(
    frozen=True
)
class OperationalCapability:
    """
    Capability operacional autorizada por Python.

    Representa algo que la plataforma SABE ejecutar.

    No representa:

    - una alerta;
    - un procedimiento;
    - una decisión del LLM;
    - una aprobación humana concreta.

    Diferentes alertas y procedimientos pueden
    reutilizar la misma capability.
    """

    capability_id: str

    operation_domain: str

    resource_type: str

    operation_kind: OperationKind

    operation_action: OperationAction

    required_parameters: tuple[
        str,
        ...
    ]

    hitl_required: bool

    executor_id: str

    def __post_init__(
        self,
    ) -> None:

        self._validate_exact_string(
            name="capability_id",
            value=self.capability_id,
        )

        self._validate_exact_string(
            name="operation_domain",
            value=self.operation_domain,
        )

        self._validate_exact_string(
            name="resource_type",
            value=self.resource_type,
        )

        self._validate_exact_string(
            name="executor_id",
            value=self.executor_id,
        )

        #
        # Los type hints de dataclass no constituyen
        # validación runtime.
        #
        # La autoridad operacional exige tipos
        # exactos, no strings equivalentes.
        #
        if not isinstance(
            self.operation_kind,
            OperationKind,
        ):
            raise OperationalCapabilityError(
                "operation_kind debe ser "
                "OperationKind."
            )

        if not isinstance(
            self.operation_action,
            OperationAction,
        ):
            raise OperationalCapabilityError(
                "operation_action debe ser "
                "OperationAction."
            )

        #
        # required_parameters forma parte de la
        # identidad inmutable de la capability.
        #
        # No admitimos list aunque contenga los
        # mismos valores.
        #
        if not isinstance(
            self.required_parameters,
            tuple,
        ):
            raise OperationalCapabilityError(
                "required_parameters debe ser "
                "una tuple inmutable."
            )

        if (
            type(
                self.hitl_required
            )
            is not bool
        ):
            raise OperationalCapabilityError(
                "hitl_required debe ser bool."
            )

        if (
            len(
                self.required_parameters
            )
            != len(
                set(
                    self.required_parameters
                )
            )
        ):
            raise OperationalCapabilityError(
                "required_parameters contiene "
                "parámetros duplicados."
            )

        for parameter_name in (
            self.required_parameters
        ):
            self._validate_exact_string(
                name="required_parameter",
                value=parameter_name,
            )

        #
        # Contrato actual de la plataforma:
        #
        # todo WRITE requiere autorización humana.
        #
        if (
            self.operation_kind
            == OperationKind.WRITE
            and not self.hitl_required
        ):
            raise OperationalCapabilityError(
                "Toda capability WRITE requiere "
                "hitl_required=True."
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
            raise OperationalCapabilityError(
                f"{name} debe ser string."
            )

        if not value:
            raise OperationalCapabilityError(
                f"{name} no puede estar vacío."
            )

        if value != value.strip():
            raise OperationalCapabilityError(
                f"{name} no puede contener "
                "espacios al inicio o al final."
            )