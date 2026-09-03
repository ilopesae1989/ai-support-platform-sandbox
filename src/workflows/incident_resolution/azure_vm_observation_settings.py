from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID


_ENVIRONMENT_NAME = (
    "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID"
)


def _validate_client_id(
    value: object,
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
            "managed_identity_client_id debe ser "
            "un UUID canónico exacto."
        )

    try:
        parsed = UUID(
            value
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        raise ValueError(
            "managed_identity_client_id debe ser "
            "un UUID canónico exacto."
        ) from None

    if str(parsed) != value:
        raise ValueError(
            "managed_identity_client_id debe usar "
            "representación UUID canónica."
        )

    return value


@dataclass(
    frozen=True
)
class AzureVmObservationManagedIdentitySettings:
    managed_identity_client_id: str | None = None

    def __post_init__(
        self,
    ) -> None:
        if (
            self.managed_identity_client_id
            is None
        ):
            return

        _validate_client_id(
            self.managed_identity_client_id
        )


def build_azure_vm_observation_settings(
    environment,
) -> AzureVmObservationManagedIdentitySettings:
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    if _ENVIRONMENT_NAME not in environment:
        return (
            AzureVmObservationManagedIdentitySettings()
        )

    value = environment[
        _ENVIRONMENT_NAME
    ]

    return AzureVmObservationManagedIdentitySettings(
        managed_identity_client_id=(
            _validate_client_id(
                value
            )
        )
    )
