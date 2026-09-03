from __future__ import annotations

from src.workflows.incident_resolution.azure_vm_instance_view import (
    AzureSdkVmPowerStateReader,
    AzureVmPowerStateReader,
)

from src.workflows.incident_resolution.azure_vm_observation_credential import (
    build_azure_vm_observation_credential,
)

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    AzureVmObservationManagedIdentitySettings,
)


def build_azure_vm_observation_reader(
    settings,
) -> AzureVmPowerStateReader:
    if not isinstance(
        settings,
        AzureVmObservationManagedIdentitySettings,
    ):
        raise TypeError(
            "settings debe ser "
            "AzureVmObservationManagedIdentitySettings."
        )

    credential = (
        build_azure_vm_observation_credential(
            settings
        )
    )

    return AzureSdkVmPowerStateReader(
        credential=credential
    )
