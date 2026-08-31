from __future__ import annotations

from typing import (
    Literal,
)

from pydantic import (
    field_validator,
    model_validator,
)

from .immutable_snapshot import (
    ImmutableSnapshotModel,
)


class AzureVmPowerStateObservation(
    ImmutableSnapshotModel
):
    """
    Evidencia read-only posterior a una operación
    Azure VM gobernada.

    Representa exclusivamente una observación
    mediante Azure Compute Instance View.

    NO representa:
    - autorización;
    - resultado de la operación WRITE;
    - nueva operación;
    - nuevo dispatch;
    - decisión de procedimiento.
    """

    source: Literal[
        "azure_compute_instance_view"
    ] = "azure_compute_instance_view"

    operation_id: str
    workflow_id: str
    approval_id: str

    target_resource: str

    subscription_id: str
    resource_group: str
    vm_name: str

    success: bool

    power_state: str | None = None
    error: str | None = None

    @field_validator(
        "operation_id",
        "workflow_id",
        "approval_id",
        "target_resource",
        "subscription_id",
        "resource_group",
        "vm_name",
    )
    @classmethod
    def validate_exact_identity_string(
        cls,
        value: str,
    ) -> str:
        if (
            not isinstance(
                value,
                str,
            )
            or not value
            or not value.strip()
            or value != value.strip()
        ):
            raise ValueError(
                "Los campos de identidad deben "
                "ser strings exactos no vacíos."
            )

        return value

    @model_validator(
        mode="after"
    )
    def validate_observation(
        self,
    ):
        expected_target = (
            "/subscriptions/"
            f"{self.subscription_id}"
            "/resourceGroups/"
            f"{self.resource_group}"
            "/providers/Microsoft.Compute/"
            "virtualMachines/"
            f"{self.vm_name}"
        )

        if (
            self.target_resource.casefold()
            != expected_target.casefold()
        ):
            raise ValueError(
                "target_resource no corresponde "
                "a la identidad VM observada."
            )

        if self.success is True:
            if (
                not isinstance(
                    self.power_state,
                    str,
                )
                or not self.power_state.startswith(
                    "PowerState/"
                )
            ):
                raise ValueError(
                    "Una observación satisfactoria "
                    "requiere PowerState/* explícito."
                )

            if self.error is not None:
                raise ValueError(
                    "Una observación satisfactoria "
                    "no puede contener error."
                )

        else:
            if self.power_state is not None:
                raise ValueError(
                    "Una observación fallida no puede "
                    "afirmar un PowerState."
                )

            if (
                not isinstance(
                    self.error,
                    str,
                )
                or not self.error
                or not self.error.strip()
                or self.error != self.error.strip()
            ):
                raise ValueError(
                    "Una observación fallida requiere "
                    "un error exacto no vacío."
                )

        return self
