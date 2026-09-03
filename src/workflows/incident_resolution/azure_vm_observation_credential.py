from __future__ import annotations

from azure.identity import ManagedIdentityCredential

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    AzureVmObservationManagedIdentitySettings,
)


def build_azure_vm_observation_credential(
    settings,
) -> ManagedIdentityCredential:
    if not isinstance(
        settings,
        AzureVmObservationManagedIdentitySettings,
    ):
        raise TypeError(
            "settings debe ser "
            "AzureVmObservationManagedIdentitySettings."
        )

    client_id = (
        settings.managed_identity_client_id
    )

    if client_id is None:
        return ManagedIdentityCredential()

    return ManagedIdentityCredential(
        client_id=client_id
    )
